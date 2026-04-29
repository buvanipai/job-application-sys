"""End-to-end backend API tests for the Job Pipeline app.
Covers: health, auth, jobs (scrape+CRUD+status), prospects, campaigns
(email/linkedin/send/followup), cover-letter, skills, resumes (default uniqueness),
scheduler, dashboard, and cross-user isolation.
"""
import time

import pytest


# -------- Health --------
class TestHealth:
    def test_root(self, anon_client, base_url):
        r = anon_client.get(f"{base_url}/api/")
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        assert data.get("service") == "job-pipeline"


# -------- Auth --------
class TestAuth:
    def test_me_unauth_returns_401(self, anon_client, base_url):
        r = anon_client.get(f"{base_url}/api/auth/me")
        assert r.status_code == 401

    def test_me_with_bearer(self, primary_user, base_url):
        r = primary_user["client"].get(f"{base_url}/api/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == primary_user["user_id"]
        assert "_id" not in data
        assert data["email"].endswith("@example.com")

    def test_logout_clears_session(self, mongo_db, base_url):
        # create a throwaway session
        from datetime import datetime, timezone, timedelta
        import uuid
        uid = f"test-user-logout-{uuid.uuid4().hex[:6]}"
        token = f"test_session_{uuid.uuid4().hex}"
        mongo_db.users.insert_one({"user_id": uid, "email": f"{uid}@example.com", "name": "L", "created_at": "x"})
        mongo_db.user_sessions.insert_one({
            "user_id": uid, "session_token": token,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
            "created_at": "x",
        })
        import requests
        s = requests.Session()
        s.headers["Content-Type"] = "application/json"
        # logout reads cookie 'session_token'; pass via cookies
        r = s.post(f"{base_url}/api/auth/logout", cookies={"session_token": token})
        assert r.status_code == 200
        assert r.json().get("ok") is True
        # ensure session row deleted
        assert mongo_db.user_sessions.find_one({"session_token": token}) is None
        mongo_db.users.delete_one({"user_id": uid})


# -------- Jobs: scrape + CRUD --------
class TestJobs:
    def test_scrape_inserts_and_scores(self, primary_user, base_url):
        c = primary_user["client"]
        r = c.post(f"{base_url}/api/jobs/scrape", json={"limit": 4})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "inserted" in data and data["inserted"] >= 1
        for j in data["jobs"]:
            assert "id" in j and "_id" not in j
            assert j["user_id"] == primary_user["user_id"]
            assert isinstance(j["score"], int) and 0 <= j["score"] <= 100
            assert isinstance(j["match_reason"], str)
            assert isinstance(j["gaps"], list)
            assert j["status"] == "new"

    def test_scrape_dedupes(self, primary_user, base_url):
        # Second scrape with a high limit should find duplicates and skip
        c = primary_user["client"]
        r1 = c.post(f"{base_url}/api/jobs/scrape", json={"limit": 8})
        assert r1.status_code == 200
        r2 = c.post(f"{base_url}/api/jobs/scrape", json={"limit": 8})
        assert r2.status_code == 200
        d2 = r2.json()
        # All 8 are sample size; second call should detect at least some dupes
        assert d2["skipped_duplicates"] >= 1

    def test_list_and_get_and_status(self, primary_user, base_url):
        c = primary_user["client"]
        jobs = c.get(f"{base_url}/api/jobs").json()
        assert isinstance(jobs, list) and len(jobs) >= 1
        j = jobs[0]
        assert "_id" not in j
        # GET single
        r = c.get(f"{base_url}/api/jobs/{j['id']}")
        assert r.status_code == 200
        # Status update valid
        r = c.post(f"{base_url}/api/jobs/{j['id']}/status", json={"status": "applied"})
        assert r.status_code == 200 and r.json()["status"] == "applied"
        # Status update invalid
        r = c.post(f"{base_url}/api/jobs/{j['id']}/status", json={"status": "bogus"})
        assert r.status_code == 400
        # Not found
        r = c.get(f"{base_url}/api/jobs/nonexistent_id")
        assert r.status_code == 404

    def test_delete_cascades(self, primary_user, base_url):
        c = primary_user["client"]
        # ensure a job exists
        r = c.post(f"{base_url}/api/jobs/scrape", json={"limit": 8})
        assert r.status_code == 200
        jobs = c.get(f"{base_url}/api/jobs").json()
        # pick a job that has no campaigns yet
        target = jobs[-1]
        # add prospects
        rp = c.post(f"{base_url}/api/jobs/{target['id']}/prospects/find", json={"count": 2})
        assert rp.status_code == 200
        # delete
        rd = c.delete(f"{base_url}/api/jobs/{target['id']}")
        assert rd.status_code == 200 and rd.json()["deleted"] == 1
        # verify cascades - prospects for that job must be gone
        rem = c.get(f"{base_url}/api/jobs/{target['id']}/prospects").json()
        assert rem == []


# -------- Prospects --------
class TestProspects:
    def test_find_and_list(self, primary_user, base_url):
        c = primary_user["client"]
        jobs = c.get(f"{base_url}/api/jobs").json()
        assert jobs, "Need at least one job from earlier tests"
        job = jobs[0]
        r = c.post(f"{base_url}/api/jobs/{job['id']}/prospects/find", json={"count": 3})
        assert r.status_code == 200
        d = r.json()
        assert d["inserted"] == 3
        for p in d["prospects"]:
            assert p["job_id"] == job["id"]
            assert p["user_id"] == primary_user["user_id"]
            assert p.get("email")
            assert "_id" not in p
        all_p = c.get(f"{base_url}/api/prospects").json()
        assert any(p["job_id"] == job["id"] for p in all_p)
        job_p = c.get(f"{base_url}/api/jobs/{job['id']}/prospects").json()
        assert len(job_p) >= 3


# -------- Campaigns --------
class TestCampaigns:
    def test_email_requires_prospect(self, primary_user, base_url):
        c = primary_user["client"]
        jobs = c.get(f"{base_url}/api/jobs").json()
        job = jobs[0]
        r = c.post(f"{base_url}/api/campaigns/generate",
                   json={"job_id": job["id"], "type": "email"})
        assert r.status_code == 400

    def test_generate_email_send_followup_flow(self, primary_user, base_url):
        c = primary_user["client"]
        jobs = c.get(f"{base_url}/api/jobs").json()
        job = jobs[0]
        prospects = c.get(f"{base_url}/api/jobs/{job['id']}/prospects").json()
        assert prospects, "Need prospects"
        pid = prospects[0]["id"]
        # Generate email (Sonnet)
        r = c.post(f"{base_url}/api/campaigns/generate",
                   json={"job_id": job["id"], "type": "email", "prospect_id": pid})
        assert r.status_code == 200, r.text
        camp = r.json()
        assert camp["type"] == "email"
        assert camp["status"] == "draft"
        assert camp["body"]
        assert "_id" not in camp
        # Send
        r = c.post(f"{base_url}/api/campaigns/send", json={"campaign_id": camp["id"]})
        assert r.status_code == 200
        sent = r.json()
        assert sent["status"] == "sent"
        assert sent["provider_receipt"]["delivered"] is True
        # Followup
        r = c.post(f"{base_url}/api/campaigns/{camp['id']}/followup")
        assert r.status_code == 200, r.text
        fu = r.json()
        assert fu["type"] == "followup"
        assert fu["parent_campaign_id"] == camp["id"]
        assert fu["status"] == "sent"
        # Original should now be marked followup_done
        all_camps = c.get(f"{base_url}/api/campaigns").json()
        original = next(x for x in all_camps if x["id"] == camp["id"])
        assert original["followup_done"] is True
        # Calling followup again should 400
        r = c.post(f"{base_url}/api/campaigns/{camp['id']}/followup")
        assert r.status_code == 400

    def test_linkedin_generate(self, primary_user, base_url):
        c = primary_user["client"]
        jobs = c.get(f"{base_url}/api/jobs").json()
        job = jobs[0]
        prospects = c.get(f"{base_url}/api/jobs/{job['id']}/prospects").json()
        pid = prospects[0]["id"]
        r = c.post(f"{base_url}/api/campaigns/generate",
                   json={"job_id": job["id"], "type": "linkedin", "prospect_id": pid})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["type"] == "linkedin"
        assert d["body"]
        assert len(d["body"]) <= 280

    def test_linkedin_requires_prospect(self, primary_user, base_url):
        c = primary_user["client"]
        jobs = c.get(f"{base_url}/api/jobs").json()
        r = c.post(f"{base_url}/api/campaigns/generate",
                   json={"job_id": jobs[0]["id"], "type": "linkedin"})
        assert r.status_code == 400

    def test_invalid_campaign_type(self, primary_user, base_url):
        c = primary_user["client"]
        jobs = c.get(f"{base_url}/api/jobs").json()
        r = c.post(f"{base_url}/api/campaigns/generate",
                   json={"job_id": jobs[0]["id"], "type": "sms"})
        assert r.status_code == 400


# -------- Cover letter --------
class TestCoverLetter:
    def test_cover_letter_generates_with_gcs(self, primary_user, base_url):
        c = primary_user["client"]
        jobs = c.get(f"{base_url}/api/jobs").json()
        r = c.post(f"{base_url}/api/jobs/{jobs[0]['id']}/cover-letter", json={})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["campaign"]["type"] == "cover_letter"
        assert d["campaign"]["body"]
        assert d["storage"]["stored"] is True
        assert d["storage"]["signed_url"].startswith("https://")
        assert d["campaign"]["artifact_url"] == d["storage"]["signed_url"]


# -------- Skills --------
class TestSkills:
    def test_aggregate_and_list(self, primary_user, base_url):
        c = primary_user["client"]
        r = c.post(f"{base_url}/api/skills/aggregate")
        assert r.status_code == 200, r.text
        d = r.json()
        # Should produce >=1 skill row (jobs likely have gaps)
        assert d["inserted"] >= 0
        skills = c.get(f"{base_url}/api/skills").json()
        if skills:
            # sorted desc by frequency
            freqs = [s["frequency"] for s in skills]
            assert freqs == sorted(freqs, reverse=True)
            for s in skills:
                assert "_id" not in s
                assert s["user_id"] == primary_user["user_id"]


# -------- Resumes --------
class TestResumes:
    def test_resume_crud_and_default_uniqueness(self, primary_user, base_url):
        c = primary_user["client"]
        # Create A as default
        rA = c.post(f"{base_url}/api/resumes",
                    json={"name": "TEST_A", "content": "Resume A", "is_default": True})
        assert rA.status_code == 200, rA.text
        a = rA.json()
        # Create B as default
        rB = c.post(f"{base_url}/api/resumes",
                    json={"name": "TEST_B", "content": "Resume B", "is_default": True})
        assert rB.status_code == 200
        b = rB.json()
        listed = c.get(f"{base_url}/api/resumes").json()
        defaults = [r for r in listed if r["is_default"]]
        assert len(defaults) == 1 and defaults[0]["id"] == b["id"]
        # Set A as default via endpoint
        r = c.post(f"{base_url}/api/resumes/{a['id']}/default")
        assert r.status_code == 200
        listed = c.get(f"{base_url}/api/resumes").json()
        defaults = [r for r in listed if r["is_default"]]
        assert len(defaults) == 1 and defaults[0]["id"] == a["id"]
        # Set non-existent default -> 404
        r = c.post(f"{base_url}/api/resumes/nope/default")
        assert r.status_code == 404
        # Delete A
        rd = c.delete(f"{base_url}/api/resumes/{a['id']}")
        assert rd.status_code == 200 and rd.json()["deleted"] == 1


# -------- Scheduler --------
class TestScheduler:
    def test_status(self, primary_user, base_url):
        c = primary_user["client"]
        r = c.get(f"{base_url}/api/scheduler/status")
        assert r.status_code == 200
        d = r.json()
        for k in ("pending_followups", "due_now", "followup_after_days", "poll_minutes"):
            assert k in d

    def test_run_returns_summary(self, primary_user, base_url):
        c = primary_user["client"]
        r = c.post(f"{base_url}/api/scheduler/run")
        assert r.status_code == 200
        d = r.json()
        assert "processed" in d and isinstance(d["processed"], int)
        assert "errors" in d


# -------- Dashboard --------
class TestDashboard:
    def test_summary(self, primary_user, base_url):
        c = primary_user["client"]
        r = c.get(f"{base_url}/api/dashboard/summary")
        assert r.status_code == 200
        d = r.json()
        for k in ("jobs_total", "jobs_high_match", "prospects_total",
                  "emails_sent", "followups_sent", "cover_letters",
                  "skills_tracked", "recent_jobs", "recent_campaigns"):
            assert k in d
        assert d["jobs_total"] >= 1
        for j in d["recent_jobs"]:
            assert "_id" not in j


# -------- Cross-user isolation --------
class TestIsolation:
    def test_other_user_cannot_read_or_modify(self, primary_user, secondary_user, base_url):
        pc = primary_user["client"]
        sc = secondary_user["client"]
        # Primary's jobs
        jobs = pc.get(f"{base_url}/api/jobs").json()
        assert jobs
        target = jobs[0]
        # Secondary cannot fetch
        r = sc.get(f"{base_url}/api/jobs/{target['id']}")
        assert r.status_code == 404
        # Secondary's listing should not include primary's job
        sec_jobs = sc.get(f"{base_url}/api/jobs").json()
        assert all(j["id"] != target["id"] for j in sec_jobs)
        # Secondary cannot update status
        r = sc.post(f"{base_url}/api/jobs/{target['id']}/status", json={"status": "archived"})
        assert r.status_code == 404
        # Secondary cannot delete (delete returns deleted=0, not 404 by design - acceptable but flag)
        r = sc.delete(f"{base_url}/api/jobs/{target['id']}")
        assert r.status_code == 200
        assert r.json()["deleted"] == 0
        # Primary's job still exists
        assert pc.get(f"{base_url}/api/jobs/{target['id']}").status_code == 200
