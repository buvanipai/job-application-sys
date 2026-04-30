"""Tests for the hub-and-spoke refactor: manual job add, rescore, research,
interview answers, campaign reply mark, settings, computed should_apply_prompt,
cascade delete with skills.job_ids shrinking, and cross-user isolation for new endpoints.
"""
import time
import uuid
from datetime import datetime, timezone, timedelta

import pytest


# -------- Manual job add (POST /api/jobs) + dedup 409 + skills upsert --------
class TestJobsManualAdd:
    def test_add_manual_scores_and_upserts_skills(self, primary_user, base_url, mongo_db):
        c = primary_user["client"]
        url = f"https://example.com/jobs/{uuid.uuid4().hex[:8]}"
        payload = {
            "title": "Staff ML Engineer",
            "company": "TestAcme",
            "url": url,
            "description": "Build LLM-powered features. Kubernetes, Rust, distributed training a plus."
        }
        r = c.post(f"{base_url}/api/jobs", json=payload)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["title"] == payload["title"]
        assert j["company"] == payload["company"]
        assert j["url"] == url
        assert j["status"] == "new"
        assert j["company_context"] == ""
        assert j["interview_answers"] in (None, [])
        assert isinstance(j["score"], int) and 0 <= j["score"] <= 100
        assert isinstance(j["gaps"], list)
        assert "_id" not in j
        # GET round-trip
        g = c.get(f"{base_url}/api/jobs/{j['id']}").json()
        assert g["id"] == j["id"]
        # Skills should have job_id appended for each gap (when there are gaps)
        if j["gaps"]:
            skills = c.get(f"{base_url}/api/skills").json()
            covered = [s for s in skills if j["id"] in (s.get("job_ids") or [])]
            assert covered, "expected skills.job_ids to include the new job for at least one gap"

    def test_add_manual_duplicate_url_returns_409(self, primary_user, base_url):
        c = primary_user["client"]
        url = f"https://example.com/jobs/{uuid.uuid4().hex[:8]}"
        payload = {"title": "Backend Eng", "company": "DupCo", "url": url, "description": "Python FastAPI"}
        r1 = c.post(f"{base_url}/api/jobs", json=payload)
        assert r1.status_code == 200
        r2 = c.post(f"{base_url}/api/jobs", json=payload)
        assert r2.status_code == 409


# -------- Rescore: POST /api/jobs/{id}/score --------
class TestRescore:
    def test_rescore_updates_and_skills_no_dup_job_id(self, primary_user, base_url):
        c = primary_user["client"]
        url = f"https://example.com/jobs/{uuid.uuid4().hex[:8]}"
        r = c.post(f"{base_url}/api/jobs", json={
            "title": "Frontend Eng", "company": "RescoreCo", "url": url,
            "description": "React, TypeScript, GraphQL, Webpack, accessibility"
        })
        assert r.status_code == 200
        jid = r.json()["id"]
        # Rescore
        r2 = c.post(f"{base_url}/api/jobs/{jid}/score")
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert d["id"] == jid
        assert isinstance(d["gaps"], list)
        assert isinstance(d["score"], int)
        # Each skill row referencing this job_id has it ONCE
        skills = c.get(f"{base_url}/api/skills").json()
        for s in skills:
            jids = s.get("job_ids") or []
            assert jids.count(jid) <= 1
            assert s["frequency"] == len(jids)

    def test_rescore_unknown_job_404(self, primary_user, base_url):
        c = primary_user["client"]
        r = c.post(f"{base_url}/api/jobs/nope/score")
        assert r.status_code == 404


# -------- Company research --------
class TestCompanyResearch:
    def test_research_sets_company_context(self, primary_user, base_url):
        c = primary_user["client"]
        jobs = c.get(f"{base_url}/api/jobs").json()
        assert jobs
        jid = jobs[0]["id"]
        r = c.post(f"{base_url}/api/jobs/{jid}/research")
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d.get("company_context"), str) and d["company_context"]
        # persisted
        g = c.get(f"{base_url}/api/jobs/{jid}").json()
        assert g["company_context"] == d["company_context"]

    def test_research_unknown_job_404(self, primary_user, base_url):
        c = primary_user["client"]
        r = c.post(f"{base_url}/api/jobs/nope/research")
        assert r.status_code == 404


# -------- Interview answers (Sonnet) --------
class TestInterviewAnswers:
    def test_interview_answers_persists(self, primary_user, base_url):
        c = primary_user["client"]
        jobs = c.get(f"{base_url}/api/jobs").json()
        jid = jobs[0]["id"]
        r = c.post(f"{base_url}/api/jobs/{jid}/interview-answers")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "interview_answers" in d
        assert "company_context" in d and d["company_context"]
        assert isinstance(d["interview_answers"], list)
        for qa in d["interview_answers"]:
            assert "q" in qa and "a" in qa
        # persisted on job
        g = c.get(f"{base_url}/api/jobs/{jid}").json()
        assert g.get("interview_answers") == d["interview_answers"]
        assert g.get("company_context") == d["company_context"]


# -------- Campaign reply mark --------
class TestCampaignReply:
    def test_mark_reply_toggle(self, primary_user, base_url):
        c = primary_user["client"]
        # Need an existing email campaign — reuse list (created in earlier suite)
        camps = c.get(f"{base_url}/api/campaigns").json()
        email_camp = next((x for x in camps if x["type"] == "email"), None)
        if not email_camp:
            # Create one quickly
            jobs = c.get(f"{base_url}/api/jobs").json()
            jid = jobs[0]["id"]
            prospects = c.get(f"{base_url}/api/jobs/{jid}/prospects").json()
            if not prospects:
                p = c.post(f"{base_url}/api/jobs/{jid}/prospects/find", json={"count": 1}).json()
                prospects = p["prospects"]
            pid = prospects[0]["id"]
            email_camp = c.post(f"{base_url}/api/campaigns/generate",
                                json={"job_id": jid, "type": "email", "prospect_id": pid}).json()
        cid = email_camp["id"]
        # Mark reply received
        r = c.post(f"{base_url}/api/campaigns/{cid}/reply",
                   json={"reply_received": True, "reply_context": "Yes please send referral"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["reply_received"] is True
        assert d["reply_context"] == "Yes please send referral"
        assert d["replied_at"] is not None
        # Toggle off
        r2 = c.post(f"{base_url}/api/campaigns/{cid}/reply",
                    json={"reply_received": False, "reply_context": ""})
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["reply_received"] is False
        assert d2["replied_at"] is None

    def test_mark_reply_unknown_404(self, primary_user, base_url):
        c = primary_user["client"]
        r = c.post(f"{base_url}/api/campaigns/nope/reply", json={"reply_received": True})
        assert r.status_code == 404


# -------- Settings GET/POST --------
class TestSettings:
    def test_get_returns_defaults(self, secondary_user, base_url):
        c = secondary_user["client"]
        r = c.get(f"{base_url}/api/settings")
        assert r.status_code == 200
        d = r.json()
        assert d == {"followup_days": 3, "apply_after_days": 7, "signature": ""}

    def test_post_upserts_and_persists(self, secondary_user, base_url):
        c = secondary_user["client"]
        r = c.post(f"{base_url}/api/settings", json={
            "followup_days": 5, "apply_after_days": 10, "signature": "— Test"
        })
        assert r.status_code == 200
        d = r.json()
        assert d["followup_days"] == 5
        assert d["apply_after_days"] == 10
        assert d["signature"] == "— Test"
        # GET reflects
        d2 = c.get(f"{base_url}/api/settings").json()
        assert d2 == d
        # Scheduler echoes updated days
        s = c.get(f"{base_url}/api/scheduler/status").json()
        assert s["followup_after_days"] == 5
        assert s["apply_after_days"] == 10


# -------- Computed should_apply_prompt on /api/campaigns --------
class TestShouldApplyPrompt:
    def test_should_apply_true_when_followup_old_enough(self, primary_user, base_url, mongo_db):
        c = primary_user["client"]
        uid = primary_user["user_id"]
        # Set apply_after_days low
        c.post(f"{base_url}/api/settings", json={"apply_after_days": 1})
        # Insert a synthetic email campaign in Mongo, followup_done with old followup_sent_at
        cid = f"camp_test_{uuid.uuid4().hex[:8]}"
        old = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        mongo_db.campaigns.insert_one({
            "id": cid, "user_id": uid, "job_id": "job_x", "prospect_id": None,
            "parent_campaign_id": None, "type": "email", "subject": "s", "body": "b",
            "status": "sent", "sent_at": old, "followup_done": True,
            "followup_sent_at": old, "reply_received": False, "reply_context": "",
            "replied_at": None, "provider_receipt": None, "artifact_url": None,
            "created_at": old,
        })
        try:
            camps = c.get(f"{base_url}/api/campaigns").json()
            mine = next(x for x in camps if x["id"] == cid)
            assert mine["should_apply_prompt"] is True
            # If reply_received -> false
            mongo_db.campaigns.update_one({"id": cid}, {"$set": {"reply_received": True}})
            camps = c.get(f"{base_url}/api/campaigns").json()
            mine = next(x for x in camps if x["id"] == cid)
            assert mine["should_apply_prompt"] is False
        finally:
            mongo_db.campaigns.delete_one({"id": cid})
            # restore default
            c.post(f"{base_url}/api/settings", json={"apply_after_days": 7})


# -------- Cascade delete shrinks skills.job_ids and removes empty rows --------
class TestCascadeDeleteShrinks:
    def test_delete_job_shrinks_skills(self, primary_user, base_url):
        c = primary_user["client"]
        # Create a job with unique gaps via manual add (deterministic gaps not guaranteed,
        # so instead: create -> capture gaps -> delete -> assert job_id no longer in any skill row)
        url = f"https://example.com/jobs/{uuid.uuid4().hex[:8]}"
        r = c.post(f"{base_url}/api/jobs", json={
            "title": "Embedded Eng", "company": "ShrinkCo", "url": url,
            "description": "C++, RTOS, FreeRTOS, hardware bring-up, oscilloscope debugging."
        })
        assert r.status_code == 200
        jid = r.json()["id"]
        # Delete
        rd = c.delete(f"{base_url}/api/jobs/{jid}")
        assert rd.status_code == 200 and rd.json()["deleted"] == 1
        # No skill row should reference this job_id
        skills = c.get(f"{base_url}/api/skills").json()
        for s in skills:
            assert jid not in (s.get("job_ids") or [])
            assert s["frequency"] == len(s.get("job_ids") or [])

    def test_delete_unknown_job_404(self, primary_user, base_url):
        c = primary_user["client"]
        r = c.delete(f"{base_url}/api/jobs/nope")
        assert r.status_code == 404


# -------- Cross-user isolation for new endpoints --------
class TestNewEndpointIsolation:
    def test_settings_isolated(self, primary_user, secondary_user, base_url):
        primary_user["client"].post(f"{base_url}/api/settings", json={"followup_days": 9})
        s = secondary_user["client"].get(f"{base_url}/api/settings").json()
        # secondary may have customized to 5 in its own test; just assert != 9
        assert s["followup_days"] != 9
        # restore
        primary_user["client"].post(f"{base_url}/api/settings", json={"followup_days": 3})

    def test_research_other_user_404(self, primary_user, secondary_user, base_url):
        jobs = primary_user["client"].get(f"{base_url}/api/jobs").json()
        if not jobs:
            pytest.skip("no jobs in primary")
        jid = jobs[0]["id"]
        r = secondary_user["client"].post(f"{base_url}/api/jobs/{jid}/research")
        assert r.status_code == 404

    def test_interview_answers_other_user_404(self, primary_user, secondary_user, base_url):
        jobs = primary_user["client"].get(f"{base_url}/api/jobs").json()
        if not jobs:
            pytest.skip("no jobs in primary")
        jid = jobs[0]["id"]
        r = secondary_user["client"].post(f"{base_url}/api/jobs/{jid}/interview-answers")
        assert r.status_code == 404

    def test_reply_other_user_404(self, primary_user, secondary_user, base_url):
        camps = primary_user["client"].get(f"{base_url}/api/campaigns").json()
        if not camps:
            pytest.skip("no campaigns in primary")
        cid = camps[0]["id"]
        r = secondary_user["client"].post(f"{base_url}/api/campaigns/{cid}/reply",
                                           json={"reply_received": True})
        assert r.status_code == 404
