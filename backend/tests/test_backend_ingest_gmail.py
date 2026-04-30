"""Tests for new endpoints in iteration 3:
- POST /api/jobs/ingest (URL + raw text + 400 empty + 409 dup URL)
- Canonical scored fields (match_pct/missing_skills/reason_if_low) on every insert/update
- Dashboard summary jobs_high_match uses match_pct >= 65
- Gmail endpoints: /api/gmail/poll, /api/gmail/simulate-reply, /api/gmail/replies
- gmail_service.classify_reply unit cases
- Settings now includes gmail_poll_minutes
- Cross-user isolation on new endpoints
"""
import sys
import uuid
from pathlib import Path

import pytest

# So we can import gmail_service for unit tests
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gmail_service  # noqa: E402


# -------- Unit: classify_reply --------
class TestClassifyReply:
    def test_ack(self):
        assert gmail_service.classify_reply("Thank you for applying to Acme!") == "ack"

    def test_rejected(self):
        assert gmail_service.classify_reply(
            "After review we have decided to move forward with other candidates."
        ) == "rejected"

    def test_progressing(self):
        assert gmail_service.classify_reply(
            "Could you share your availability for next steps?"
        ) == "progressing"

    def test_replied_default(self):
        assert gmail_service.classify_reply("Random unrelated text about weather.") == "replied"


# -------- POST /api/jobs/ingest --------
class TestJobsIngest:
    def test_ingest_empty_returns_400(self, primary_user, base_url):
        c = primary_user["client"]
        r = c.post(f"{base_url}/api/jobs/ingest", json={"input": ""})
        assert r.status_code == 400
        r2 = c.post(f"{base_url}/api/jobs/ingest", json={})
        assert r2.status_code == 400

    def test_ingest_url_inserts_scores_and_canonical_fields(self, primary_user, base_url):
        c = primary_user["client"]
        url = f"https://example.com/jobs/ingest-url-{uuid.uuid4().hex[:8]}"
        r = c.post(f"{base_url}/api/jobs/ingest", json={"input": url})
        assert r.status_code == 200, r.text
        j = r.json()
        # Source set to url
        assert j["source"] == "url"
        assert j["url"] == url
        # Both legacy + canonical fields populated
        for k in ("score", "match_pct", "match_reason", "reason_if_low",
                  "gaps", "missing_skills"):
            assert k in j
        assert isinstance(j["match_pct"], int) and 0 <= j["match_pct"] <= 100
        assert j["match_pct"] == j["score"]
        assert isinstance(j["missing_skills"], list)
        assert j["missing_skills"] == j["gaps"]
        # reason_if_low rule: '' when match_pct >= 65 else equals match_reason
        if j["match_pct"] >= 65:
            assert j["reason_if_low"] == ""
        else:
            assert j["reason_if_low"] == j["match_reason"]
        # Skills upsert: at least one skill row references this job_id (if gaps>0)
        if j["missing_skills"]:
            skills = c.get(f"{base_url}/api/skills").json()
            covered = [s for s in skills if j["id"] in (s.get("job_ids") or [])]
            assert covered, "skills.job_ids should contain the new job"

    def test_ingest_url_dup_returns_409(self, primary_user, base_url):
        c = primary_user["client"]
        url = f"https://example.com/jobs/ingest-dup-{uuid.uuid4().hex[:8]}"
        r1 = c.post(f"{base_url}/api/jobs/ingest", json={"input": url})
        assert r1.status_code == 200
        r2 = c.post(f"{base_url}/api/jobs/ingest", json={"input": url})
        assert r2.status_code == 409

    def test_ingest_paste_extracts_and_scores(self, primary_user, base_url):
        c = primary_user["client"]
        jd = (
            "Senior Backend Engineer at Acme Robotics — Berlin (remote)\n\n"
            "We need a senior backend engineer with strong Python, FastAPI, PostgreSQL, "
            "and Kubernetes experience. You will own latency-critical APIs and mentor "
            "junior engineers. 5+ years required."
        )
        r = c.post(f"{base_url}/api/jobs/ingest", json={"input": jd})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["source"] == "paste"
        assert j["url"] is None
        assert isinstance(j["title"], str) and j["title"]
        assert isinstance(j["company"], str) and j["company"]
        assert isinstance(j["description"], str) and j["description"]
        assert isinstance(j["match_pct"], int)
        assert j["match_pct"] == j["score"]
        if j["match_pct"] >= 65:
            assert j["reason_if_low"] == ""
        else:
            assert j["reason_if_low"] == j["match_reason"]


# -------- Canonical fields on manual add + rescore --------
class TestCanonicalScoredFields:
    def test_manual_add_writes_both_legacy_and_canonical(self, primary_user, base_url):
        c = primary_user["client"]
        url = f"https://example.com/jobs/canon-{uuid.uuid4().hex[:8]}"
        r = c.post(f"{base_url}/api/jobs", json={
            "title": "Backend Eng", "company": "CanonCo", "url": url,
            "description": "Python, FastAPI, Postgres."
        })
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["match_pct"] == j["score"]
        assert j["missing_skills"] == j["gaps"]
        if j["match_pct"] >= 65:
            assert j["reason_if_low"] == ""
        else:
            assert j["reason_if_low"] == j["match_reason"]

    def test_rescore_writes_canonical(self, primary_user, base_url):
        c = primary_user["client"]
        url = f"https://example.com/jobs/canon-rescore-{uuid.uuid4().hex[:8]}"
        r = c.post(f"{base_url}/api/jobs", json={
            "title": "Frontend Eng", "company": "ReCanon", "url": url,
            "description": "React, TypeScript."
        })
        jid = r.json()["id"]
        r2 = c.post(f"{base_url}/api/jobs/{jid}/score")
        assert r2.status_code == 200
        d = r2.json()
        assert d["match_pct"] == d["score"]
        assert d["missing_skills"] == d["gaps"]
        if d["match_pct"] >= 65:
            assert d["reason_if_low"] == ""
        else:
            assert d["reason_if_low"] == d["match_reason"]


# -------- Dashboard summary jobs_high_match uses match_pct >= 65 --------
class TestDashboardHighMatch:
    def test_jobs_high_match_uses_match_pct(self, primary_user, base_url, mongo_db):
        uid = primary_user["user_id"]
        # Insert 2 jobs with match_pct >=65, 1 below
        for pct in (70, 80):
            mongo_db.jobs.insert_one({
                "id": f"job_high_{uuid.uuid4().hex[:8]}",
                "user_id": uid,
                "title": "x", "company": "y", "description": "z",
                "score": pct, "match_pct": pct, "match_reason": "ok",
                "reason_if_low": "", "gaps": [], "missing_skills": [],
                "status": "new", "company_context": "",
                "interview_answers": None, "created_at": "2026-01-01T00:00:00+00:00",
            })
        mongo_db.jobs.insert_one({
            "id": f"job_low_{uuid.uuid4().hex[:8]}",
            "user_id": uid,
            "title": "x", "company": "y", "description": "z",
            "score": 40, "match_pct": 40, "match_reason": "low",
            "reason_if_low": "low", "gaps": [], "missing_skills": [],
            "status": "new", "company_context": "",
            "interview_answers": None, "created_at": "2026-01-01T00:00:00+00:00",
        })
        d = primary_user["client"].get(f"{base_url}/api/dashboard/summary").json()
        # Must have at least the 2 we inserted
        assert d["jobs_high_match"] >= 2


# -------- Gmail endpoints --------
class TestGmailEndpoints:
    def _make_email_campaign(self, c, base_url):
        """Create an email campaign for the primary user."""
        jobs = c.get(f"{base_url}/api/jobs").json()
        if not jobs:
            c.post(f"{base_url}/api/jobs/scrape", json={"limit": 4})
            jobs = c.get(f"{base_url}/api/jobs").json()
        jid = jobs[0]["id"]
        prospects = c.get(f"{base_url}/api/jobs/{jid}/prospects").json()
        if not prospects:
            prospects = c.post(
                f"{base_url}/api/jobs/{jid}/prospects/find", json={"count": 1}
            ).json()["prospects"]
        pid = prospects[0]["id"]
        camp = c.post(f"{base_url}/api/campaigns/generate",
                      json={"job_id": jid, "type": "email", "prospect_id": pid}).json()
        # Send so we have a sent_at
        c.post(f"{base_url}/api/campaigns/send", json={"campaign_id": camp["id"]})
        return camp["id"]

    def test_poll_returns_zero_zero(self, primary_user, base_url):
        r = primary_user["client"].post(f"{base_url}/api/gmail/poll")
        assert r.status_code == 200
        d = r.json()
        assert d == {"fetched": 0, "processed": 0}

    def test_simulate_reply_404_unknown_campaign(self, primary_user, base_url):
        r = primary_user["client"].post(
            f"{base_url}/api/gmail/simulate-reply",
            json={"campaign_id": "nope", "status": "ack"},
        )
        assert r.status_code == 404

    def test_simulate_reply_400_invalid_status(self, primary_user, base_url):
        cid = self._make_email_campaign(primary_user["client"], base_url)
        r = primary_user["client"].post(
            f"{base_url}/api/gmail/simulate-reply",
            json={"campaign_id": cid, "status": "garbage"},
        )
        assert r.status_code == 400

    def test_simulate_reply_400_when_no_prospect(self, primary_user, base_url, mongo_db):
        uid = primary_user["user_id"]
        # Manufacture a campaign with no prospect_id
        cid = f"camp_noprospect_{uuid.uuid4().hex[:8]}"
        mongo_db.campaigns.insert_one({
            "id": cid, "user_id": uid, "job_id": "j", "prospect_id": None,
            "parent_campaign_id": None, "type": "email", "subject": "s", "body": "b",
            "status": "sent", "sent_at": "2026-01-01T00:00:00+00:00",
            "followup_done": False, "followup_sent_at": None,
            "reply_received": False, "reply_context": "",
            "replied_at": None, "provider_receipt": None, "artifact_url": None,
            "created_at": "2026-01-01T00:00:00+00:00",
        })
        try:
            r = primary_user["client"].post(
                f"{base_url}/api/gmail/simulate-reply",
                json={"campaign_id": cid, "status": "ack"},
            )
            assert r.status_code == 400
        finally:
            mongo_db.campaigns.delete_one({"id": cid})

    def test_simulate_reply_rejected_flips_should_apply_prompt(self, primary_user, base_url):
        c = primary_user["client"]
        cid = self._make_email_campaign(c, base_url)
        r = c.post(f"{base_url}/api/gmail/simulate-reply",
                   json={"campaign_id": cid, "status": "rejected"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["result"]["matched"] is True
        assert d["result"]["reply_status"] == "rejected"
        # Verify campaign updated + should_apply_prompt
        camps = c.get(f"{base_url}/api/campaigns").json()
        mine = next(x for x in camps if x["id"] == cid)
        assert mine["reply_received"] is True
        assert mine["reply_status"] == "rejected"
        assert mine["reply_context"]
        assert mine["should_apply_prompt"] is True

    def test_simulate_reply_each_status(self, primary_user, base_url):
        c = primary_user["client"]
        for status in ("ack", "progressing", "replied"):
            cid = self._make_email_campaign(c, base_url)
            r = c.post(f"{base_url}/api/gmail/simulate-reply",
                       json={"campaign_id": cid, "status": status})
            assert r.status_code == 200, r.text
            assert r.json()["result"]["reply_status"] == status

    def test_simulate_reply_custom_body_classified(self, primary_user, base_url):
        c = primary_user["client"]
        cid = self._make_email_campaign(c, base_url)
        body = "We have decided to move forward with other candidates this round."
        r = c.post(f"{base_url}/api/gmail/simulate-reply",
                   json={"campaign_id": cid, "status": "progressing", "body": body})
        assert r.status_code == 200, r.text
        d = r.json()
        # custom body wins classification regardless of `status` param
        assert d["result"]["reply_status"] == "rejected"
        assert d["reply_injected"]["body"] == body

    def test_replies_listing_user_scoped_and_sorted(self, primary_user, secondary_user, base_url):
        pc = primary_user["client"]
        # Trigger a couple of replies
        cid1 = self._make_email_campaign(pc, base_url)
        pc.post(f"{base_url}/api/gmail/simulate-reply",
                json={"campaign_id": cid1, "status": "ack"})
        cid2 = self._make_email_campaign(pc, base_url)
        pc.post(f"{base_url}/api/gmail/simulate-reply",
                json={"campaign_id": cid2, "status": "progressing"})
        r = pc.get(f"{base_url}/api/gmail/replies")
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 2
        # All belong to primary
        for it in items:
            assert it["user_id"] == primary_user["user_id"]
            assert "_id" not in it
        # Sorted by received_at desc
        recs = [i["received_at"] for i in items]
        assert recs == sorted(recs, reverse=True)
        # Secondary should not see primary's replies
        sr = secondary_user["client"].get(f"{base_url}/api/gmail/replies").json()
        for it in sr:
            assert it["user_id"] == secondary_user["user_id"]


# -------- Settings includes gmail_poll_minutes --------
class TestSettingsGmailPoll:
    def test_default_includes_gmail_poll_minutes(self, primary_user, base_url, mongo_db):
        # Reset settings for primary
        mongo_db.user_settings.delete_many({"user_id": primary_user["user_id"]})
        d = primary_user["client"].get(f"{base_url}/api/settings").json()
        assert d.get("gmail_poll_minutes") == 15

    def test_post_persists_gmail_poll_minutes(self, primary_user, base_url):
        c = primary_user["client"]
        r = c.post(f"{base_url}/api/settings", json={"gmail_poll_minutes": 30})
        assert r.status_code == 200
        assert r.json()["gmail_poll_minutes"] == 30
        # GET reflects
        d = c.get(f"{base_url}/api/settings").json()
        assert d["gmail_poll_minutes"] == 30
        # restore
        c.post(f"{base_url}/api/settings", json={"gmail_poll_minutes": 15})


# -------- Cross-user isolation on new endpoints --------
class TestNewEndpointIsolation:
    def test_simulate_reply_other_user_404(self, primary_user, secondary_user, base_url):
        # Create campaign on primary
        jobs = primary_user["client"].get(f"{base_url}/api/jobs").json()
        if not jobs:
            primary_user["client"].post(f"{base_url}/api/jobs/scrape", json={"limit": 2})
            jobs = primary_user["client"].get(f"{base_url}/api/jobs").json()
        jid = jobs[0]["id"]
        prospects = primary_user["client"].get(f"{base_url}/api/jobs/{jid}/prospects").json()
        if not prospects:
            prospects = primary_user["client"].post(
                f"{base_url}/api/jobs/{jid}/prospects/find", json={"count": 1}
            ).json()["prospects"]
        camp = primary_user["client"].post(f"{base_url}/api/campaigns/generate", json={
            "job_id": jid, "type": "email", "prospect_id": prospects[0]["id"]
        }).json()
        # Secondary tries to simulate-reply on primary's campaign
        r = secondary_user["client"].post(
            f"{base_url}/api/gmail/simulate-reply",
            json={"campaign_id": camp["id"], "status": "ack"},
        )
        assert r.status_code == 404

    def test_ingest_unauth_401(self, anon_client, base_url):
        r = anon_client.post(f"{base_url}/api/jobs/ingest", json={"input": "https://x.y/z"})
        assert r.status_code == 401
