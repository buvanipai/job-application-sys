"""Job Application Pipeline API.
- Auth: Emergent Google Auth (session cookies)
- LLMs: Claude Haiku 4.5 (scoring), Claude Sonnet 4.5 (email/cover letter/LinkedIn)
- Mocked: Playwright scrape, Apify+Hunter prospect find, Gmail SMTP, GCS PDF storage
- Scheduler: APScheduler for follow-up sweeps
"""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

import ai_service
import mock_scraper
import scheduler_service
import gmail_service

# REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="Job Pipeline API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# -------------------- Models --------------------

class User(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None


class SessionRequest(BaseModel):
    session_id: str


class Job(BaseModel):
    id: str
    user_id: str
    title: str
    company: str
    url: Optional[str] = None
    location: Optional[str] = None
    description: str
    # Legacy (still written)
    score: int = 0
    match_reason: str = ""
    gaps: List[str] = []
    # Canonical (per spec)
    match_pct: int = 0
    missing_skills: List[str] = []
    reason_if_low: str = ""
    status: str = "new"  # new, applied, archived
    company_context: str = ""
    interview_answers: Optional[List[dict]] = None
    source: Optional[str] = None  # url|paste|seed|manual
    created_at: str


class Prospect(BaseModel):
    id: str
    user_id: str
    job_id: str
    name: str
    role: str
    company: str
    email: Optional[str] = None
    linkedin: Optional[str] = None
    source: str = "mock"
    confidence: Optional[int] = None
    priority: Optional[int] = None
    created_at: str


class Campaign(BaseModel):
    id: str
    user_id: str
    job_id: str
    prospect_id: Optional[str] = None
    parent_campaign_id: Optional[str] = None
    type: str  # email, cover_letter, linkedin, followup
    subject: Optional[str] = ""
    body: str = ""
    status: str = "draft"  # draft, sent
    sent_at: Optional[str] = None
    followup_done: bool = False
    followup_sent_at: Optional[str] = None
    reply_received: bool = False
    reply_context: str = ""
    reply_status: Optional[str] = None  # ack | progressing | rejected | replied
    replied_at: Optional[str] = None
    provider_receipt: Optional[dict] = None
    artifact_url: Optional[str] = None
    created_at: str


class SkillRow(BaseModel):
    id: str
    user_id: str
    skill: str
    frequency: int
    job_ids: List[str] = []
    project_swap_suggestion: str = ""
    created_at: str


class Resume(BaseModel):
    id: str
    user_id: str
    name: str
    content: str
    is_default: bool = False
    created_at: str


class ResumeIn(BaseModel):
    name: str
    content: str
    is_default: bool = False


class ScrapeRequest(BaseModel):
    limit: int = 6


class JobManualIn(BaseModel):
    title: str
    company: str
    url: Optional[str] = None
    location: Optional[str] = None
    description: str


class GenerateCampaignRequest(BaseModel):
    job_id: str
    prospect_id: Optional[str] = None
    type: str  # email | linkedin
    resume_id: Optional[str] = None


class SendCampaignRequest(BaseModel):
    campaign_id: str


class CoverLetterRequest(BaseModel):
    resume_id: Optional[str] = None
    company_context: Optional[str] = None


class ProspectSearchRequest(BaseModel):
    count: int = 3


class ReplyMarkRequest(BaseModel):
    reply_received: bool = True
    reply_context: str = ""


class SettingsIn(BaseModel):
    followup_days: Optional[int] = None
    apply_after_days: Optional[int] = None
    gmail_poll_minutes: Optional[int] = None
    signature: Optional[str] = None


# -------------------- Auth helpers --------------------

EMERGENT_AUTH_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"


async def _get_user_from_request(request: Request) -> Optional[dict]:
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return None
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        return None
    expires_at = session.get("expires_at")
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at)
        except ValueError:
            return None
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at < datetime.now(timezone.utc):
        return None
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    return user


async def require_user(request: Request) -> dict:
    user = await _get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# -------------------- Profile helper --------------------

async def get_candidate_profile(user_id: str) -> str:
    """Returns the default resume content or a stub if none."""
    resume = await db.resumes.find_one(
        {"user_id": user_id, "is_default": True}, {"_id": 0}
    )
    if not resume:
        resume = await db.resumes.find_one({"user_id": user_id}, {"_id": 0}, sort=[("created_at", -1)])
    if resume:
        return f"{resume.get('name','Candidate')}\n\n{resume.get('content','')}"
    return (
        "Full-stack engineer with 6 years of experience. Python, FastAPI, React, TypeScript, "
        "PostgreSQL, AWS. Comfortable with LLM integration, Playwright, and production CI/CD."
    )


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or datetime.now(timezone.utc)).isoformat()


DEFAULT_SETTINGS = {"followup_days": 3, "apply_after_days": 7, "gmail_poll_minutes": 15, "signature": ""}


async def _get_user_settings(user_id: str) -> dict:
    doc = await db.user_settings.find_one({"user_id": user_id}, {"_id": 0})
    if not doc:
        return dict(DEFAULT_SETTINGS)
    return {**DEFAULT_SETTINGS, **{k: v for k, v in doc.items() if k in DEFAULT_SETTINGS}}


# -------------------- Auth routes --------------------

@api.get("/")
async def root():
    return {"ok": True, "service": "job-pipeline"}


@api.post("/auth/session")
async def auth_session(body: SessionRequest, response: Response):
    async with httpx.AsyncClient(timeout=20) as hc:
        r = await hc.get(EMERGENT_AUTH_URL, headers={"X-Session-ID": body.session_id})
    if r.status_code != 200:
        logger.warning("Emergent auth session-data failed: status=%s body=%s", r.status_code, r.text[:200])
        raise HTTPException(status_code=401, detail=f"Emergent auth rejected session_id (upstream {r.status_code})")
    data = r.json()
    email = data.get("email")
    name = data.get("name") or email
    picture = data.get("picture")
    session_token = data.get("session_token")
    if not email or not session_token:
        raise HTTPException(status_code=401, detail="Invalid session data")

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": name, "picture": picture, "last_login": _iso()}},
        )
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "created_at": _iso(),
            "last_login": _iso(),
        })

    expires_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at,
        "created_at": _iso(),
    })

    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60,
    )
    return {
        "user_id": user_id,
        "email": email,
        "name": name,
        "picture": picture,
        "session_token": session_token,
    }


@api.get("/auth/me")
async def auth_me(user: dict = Depends(require_user)):
    return {k: user.get(k) for k in ("user_id", "email", "name", "picture")}


@api.post("/auth/logout")
async def auth_logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
    if token:
        await db.user_sessions.delete_many({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


# -------------------- Jobs --------------------

def _scored_fields(s: dict) -> dict:
    """Canonical scored fields written on every job insert/update.
    Keeps legacy (score/gaps/match_reason) alongside new canonical names
    (match_pct/missing_skills/reason_if_low) so both are always populated."""
    score = int(s.get("score", 0) or 0)
    reason = s.get("match_reason", "") or ""
    gaps = s.get("gaps", []) or []
    return {
        "score": score,
        "match_pct": score,
        "match_reason": reason,
        "reason_if_low": reason if score < 65 else "",
        "gaps": gaps,
        "missing_skills": gaps,
    }


async def _upsert_skills_for_gaps(user_id: str, job_id: str, gaps: list):
    """Incrementally update `skills` collection when a job is (re)scored.
    No LLM involved here — just DB writes."""
    for g in gaps or []:
        key = (g or "").strip().lower()
        if not key:
            continue
        existing = await db.skills.find_one(
            {"user_id": user_id, "skill": key}, {"_id": 0}
        )
        if existing:
            job_ids = list({*(existing.get("job_ids") or []), job_id})
            await db.skills.update_one(
                {"user_id": user_id, "skill": key},
                {"$set": {"frequency": len(job_ids), "job_ids": job_ids}},
            )
        else:
            await db.skills.insert_one({
                "id": f"skill_{uuid.uuid4().hex[:10]}",
                "user_id": user_id,
                "skill": key,
                "frequency": 1,
                "job_ids": [job_id],
                "project_swap_suggestion": "",
                "created_at": _iso(),
            })


async def _remove_job_from_skills(user_id: str, job_id: str):
    """When a job is deleted, remove it from skills.job_ids and recompute frequency."""
    async for s in db.skills.find({"user_id": user_id, "job_ids": job_id}, {"_id": 0}):
        job_ids = [jid for jid in (s.get("job_ids") or []) if jid != job_id]
        if not job_ids:
            await db.skills.delete_one({"user_id": user_id, "skill": s["skill"]})
        else:
            await db.skills.update_one(
                {"user_id": user_id, "skill": s["skill"]},
                {"$set": {"job_ids": job_ids, "frequency": len(job_ids)}},
            )


@api.post("/jobs")
async def add_job_manual(body: JobManualIn, user: dict = Depends(require_user)):
    """Add a single job manually with explicit fields. Use POST /api/jobs/ingest for URL/paste."""
    uid = user["user_id"]
    if body.url:
        existing = await db.jobs.find_one({"user_id": uid, "url": body.url}, {"_id": 0})
        if existing:
            raise HTTPException(status_code=409, detail="Job with this URL already exists")
    profile = await get_candidate_profile(uid)
    payload = [{
        "title": body.title, "company": body.company, "description": body.description,
    }]
    scores = await ai_service.score_jobs_batch(payload, profile)
    s = scores[0] if scores else {"score": 0, "match_reason": "", "gaps": []}
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    doc = {
        "id": job_id,
        "user_id": uid,
        "title": body.title,
        "company": body.company,
        "url": body.url,
        "location": body.location,
        "description": body.description,
        "status": "new",
        "company_context": "",
        "interview_answers": None,
        "created_at": _iso(),
        **_scored_fields(s),
    }
    await db.jobs.insert_one(dict(doc))
    await _upsert_skills_for_gaps(uid, job_id, doc["missing_skills"])
    return doc


@api.post("/jobs/ingest")
async def ingest_job(body: dict, user: dict = Depends(require_user)):
    """Single-input add: pastes a URL OR raw JD text.
    - URL → Playwright fetch (mocked) → Haiku extract if title/company missing
    - Raw text → Haiku extract {title, company, location, description}
    Then score with Haiku + auto-upsert skills.
    """
    uid = user["user_id"]
    raw = (body.get("input") or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="input is required")

    url: Optional[str] = None
    scraped_text: str = ""
    if raw.startswith("http://") or raw.startswith("https://"):
        # URL branch (mocked Playwright)
        url = raw.split()[0]
        fetched = mock_scraper.mock_fetch_url(url)
        scraped_text = fetched.get("text", "")
        # Dedup by URL
        existing = await db.jobs.find_one({"user_id": uid, "url": url}, {"_id": 0})
        if existing:
            raise HTTPException(status_code=409, detail="Job with this URL already exists")
    else:
        scraped_text = raw

    extracted = await ai_service.extract_job_fields(scraped_text)
    title = extracted.get("title") or "Untitled role"
    company = extracted.get("company") or "Unknown company"
    location = extracted.get("location") or None
    description = extracted.get("description") or scraped_text[:4000]

    profile = await get_candidate_profile(uid)
    scores = await ai_service.score_jobs_batch(
        [{"title": title, "company": company, "description": description}], profile
    )
    s = scores[0] if scores else {"score": 0, "match_reason": "", "gaps": []}
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    doc = {
        "id": job_id,
        "user_id": uid,
        "title": title,
        "company": company,
        "url": url,
        "location": location,
        "description": description,
        "status": "new",
        "company_context": "",
        "interview_answers": None,
        "source": "url" if url else "paste",
        "created_at": _iso(),
        **_scored_fields(s),
    }
    await db.jobs.insert_one(dict(doc))
    await _upsert_skills_for_gaps(uid, job_id, doc["missing_skills"])
    return doc


@api.post("/jobs/{job_id}/score")
async def rescore_job(job_id: str, user: dict = Depends(require_user)):
    uid = user["user_id"]
    job = await db.jobs.find_one({"id": job_id, "user_id": uid}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    profile = await get_candidate_profile(uid)
    await _remove_job_from_skills(uid, job_id)
    payload = [{
        "title": job.get("title", ""), "company": job.get("company", ""),
        "description": job.get("description", ""),
    }]
    scores = await ai_service.score_jobs_batch(payload, profile)
    s = scores[0] if scores else {"score": 0, "match_reason": "", "gaps": []}
    updates = _scored_fields(s)
    await db.jobs.update_one({"id": job_id, "user_id": uid}, {"$set": updates})
    await _upsert_skills_for_gaps(uid, job_id, updates["missing_skills"])
    return {**job, **updates}


@api.post("/jobs/scrape")
async def scrape_jobs(body: ScrapeRequest, user: dict = Depends(require_user)):
    """Bulk-add sample jobs (kept for demo/testing). In production, users would add jobs manually via POST /api/jobs."""
    uid = user["user_id"]
    scraped = mock_scraper.mock_scrape_jobs(limit=body.limit)
    profile = await get_candidate_profile(uid)

    # Dedup (no LLM) against existing jobs by url
    existing_urls = set()
    async for j in db.jobs.find({"user_id": uid}, {"_id": 0, "url": 1}):
        if j.get("url"):
            existing_urls.add(j["url"])
    fresh = [j for j in scraped if j.get("url") not in existing_urls]
    if not fresh:
        return {"inserted": 0, "skipped_duplicates": len(scraped), "jobs": []}

    # Haiku batch score
    scores = await ai_service.score_jobs_batch(fresh, profile)

    inserted = []
    now = _iso()
    for j, s in zip(fresh, scores):
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        doc = {
            "id": job_id,
            "user_id": uid,
            "title": j["title"],
            "company": j["company"],
            "url": j.get("url"),
            "location": j.get("location"),
            "description": j["description"],
            "status": "new",
            "company_context": "",
            "interview_answers": None,
            "source": "seed",
            "created_at": now,
            **_scored_fields(s),
        }
        await db.jobs.insert_one(dict(doc))
        await _upsert_skills_for_gaps(uid, job_id, doc["missing_skills"])
        inserted.append(doc)
    return {
        "inserted": len(inserted),
        "skipped_duplicates": len(scraped) - len(fresh),
        "jobs": inserted,
    }


@api.get("/jobs")
async def list_jobs(user: dict = Depends(require_user)):
    jobs = await db.jobs.find({"user_id": user["user_id"]}, {"_id": 0}).sort("score", -1).to_list(500)
    return jobs


@api.get("/jobs/{job_id}")
async def get_job(job_id: str, user: dict = Depends(require_user)):
    job = await db.jobs.find_one({"id": job_id, "user_id": user["user_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@api.delete("/jobs/{job_id}")
async def delete_job(job_id: str, user: dict = Depends(require_user)):
    uid = user["user_id"]
    res = await db.jobs.delete_one({"id": job_id, "user_id": uid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    await db.prospects.delete_many({"job_id": job_id, "user_id": uid})
    await db.campaigns.delete_many({"job_id": job_id, "user_id": uid})
    await _remove_job_from_skills(uid, job_id)
    return {"deleted": res.deleted_count}


@api.post("/jobs/{job_id}/status")
async def update_job_status(job_id: str, body: dict, user: dict = Depends(require_user)):
    status = body.get("status", "new")
    if status not in {"new", "applied", "archived"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    res = await db.jobs.update_one(
        {"id": job_id, "user_id": user["user_id"]},
        {"$set": {"status": status}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True, "status": status}


@api.post("/jobs/{job_id}/research")
async def research_company(job_id: str, user: dict = Depends(require_user)):
    """Fetch (mocked) company vision/mission → stored in job.company_context."""
    uid = user["user_id"]
    job = await db.jobs.find_one({"id": job_id, "user_id": uid}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    context = mock_scraper.mock_company_context(job["company"])
    await db.jobs.update_one(
        {"id": job_id, "user_id": uid},
        {"$set": {"company_context": context}},
    )
    return {"company_context": context}


@api.post("/jobs/{job_id}/interview-answers")
async def interview_answers(job_id: str, user: dict = Depends(require_user)):
    """Generate suggested interview answers via Sonnet using stored company_context + JD + resume."""
    uid = user["user_id"]
    job = await db.jobs.find_one({"id": job_id, "user_id": uid}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    profile = await get_candidate_profile(uid)
    context = job.get("company_context") or mock_scraper.mock_company_context(job["company"])
    qas = await ai_service.generate_interview_answers(job, context, profile)
    await db.jobs.update_one(
        {"id": job_id, "user_id": uid},
        {"$set": {"interview_answers": qas, "company_context": context}},
    )
    return {"interview_answers": qas, "company_context": context}


# -------------------- Prospects --------------------

@api.post("/jobs/{job_id}/prospects/find")
async def find_prospects(job_id: str, body: ProspectSearchRequest, user: dict = Depends(require_user)):
    job = await db.jobs.find_one({"id": job_id, "user_id": user["user_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    found = mock_scraper.mock_find_prospects(job["company"], n=body.count)
    inserted = []
    now = _iso()
    for p in found:
        doc = {
            "id": f"prosp_{uuid.uuid4().hex[:12]}",
            "user_id": user["user_id"],
            "job_id": job_id,
            "name": p["name"],
            "role": p["role"],
            "company": p["company"],
            "email": p.get("email"),
            "linkedin": p.get("linkedin"),
            "source": p.get("source", "mock"),
            "confidence": p.get("confidence"),
            "priority": p.get("priority"),
            "created_at": now,
        }
        await db.prospects.insert_one(dict(doc))
        inserted.append(doc)
    return {"inserted": len(inserted), "prospects": inserted}


@api.get("/prospects")
async def list_prospects(user: dict = Depends(require_user)):
    items = await db.prospects.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return items


@api.get("/jobs/{job_id}/prospects")
async def job_prospects(job_id: str, user: dict = Depends(require_user)):
    items = await db.prospects.find(
        {"user_id": user["user_id"], "job_id": job_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    return items


# -------------------- Campaigns --------------------

@api.post("/campaigns/generate")
async def generate_campaign(body: GenerateCampaignRequest, user: dict = Depends(require_user)):
    job = await db.jobs.find_one({"id": body.job_id, "user_id": user["user_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    prospect = None
    if body.prospect_id:
        prospect = await db.prospects.find_one(
            {"id": body.prospect_id, "user_id": user["user_id"]}, {"_id": 0}
        )
        if not prospect:
            raise HTTPException(status_code=404, detail="Prospect not found")
    profile = await get_candidate_profile(user["user_id"])

    if body.type == "email":
        if not prospect:
            raise HTTPException(status_code=400, detail="prospect_id required for email")
        content = await ai_service.generate_outreach_email(job, prospect, profile)
    elif body.type == "linkedin":
        if not prospect:
            raise HTTPException(status_code=400, detail="prospect_id required for linkedin")
        content = await ai_service.generate_linkedin_note(job, prospect, profile)
    else:
        raise HTTPException(status_code=400, detail="type must be email or linkedin")

    now = _iso()
    doc = {
        "id": f"camp_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "job_id": body.job_id,
        "prospect_id": body.prospect_id,
        "parent_campaign_id": None,
        "type": body.type,
        "subject": content.get("subject", ""),
        "body": content.get("body", ""),
        "status": "draft",
        "sent_at": None,
        "followup_done": False,
        "followup_sent_at": None,
        "reply_received": False,
        "reply_context": "",
        "replied_at": None,
        "provider_receipt": None,
        "artifact_url": None,
        "created_at": now,
    }
    await db.campaigns.insert_one(dict(doc))
    return doc


@api.post("/campaigns/send")
async def send_campaign(body: SendCampaignRequest, user: dict = Depends(require_user)):
    camp = await db.campaigns.find_one({"id": body.campaign_id, "user_id": user["user_id"]}, {"_id": 0})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp["status"] == "sent":
        return camp
    prospect = None
    if camp.get("prospect_id"):
        prospect = await db.prospects.find_one({"id": camp["prospect_id"]}, {"_id": 0})
    to_email = (prospect or {}).get("email", "unknown@example.com")
    receipt = mock_scraper.mock_send_email(to_email, camp.get("subject", ""), camp.get("body", ""))
    now = _iso()
    await db.campaigns.update_one(
        {"id": camp["id"]},
        {"$set": {"status": "sent", "sent_at": now, "provider_receipt": receipt}},
    )
    camp.update({"status": "sent", "sent_at": now, "provider_receipt": receipt})
    return camp


@api.post("/campaigns/{campaign_id}/followup")
async def manual_followup(campaign_id: str, user: dict = Depends(require_user)):
    camp = await db.campaigns.find_one({"id": campaign_id, "user_id": user["user_id"]}, {"_id": 0})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp.get("followup_done"):
        raise HTTPException(status_code=400, detail="Follow-up already sent")
    job = await db.jobs.find_one({"id": camp["job_id"]}, {"_id": 0}) or {}
    prospect = await db.prospects.find_one({"id": camp.get("prospect_id")}, {"_id": 0}) or {}
    gen = await ai_service.generate_followup_email(
        {"subject": camp.get("subject"), "body": camp.get("body")}, job, prospect
    )
    receipt = mock_scraper.mock_send_email(prospect.get("email", ""), gen["subject"], gen["body"])
    now = _iso()
    doc = {
        "id": f"camp_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "job_id": camp["job_id"],
        "prospect_id": camp.get("prospect_id"),
        "parent_campaign_id": camp["id"],
        "type": "followup",
        "subject": gen["subject"],
        "body": gen["body"],
        "status": "sent",
        "sent_at": now,
        "followup_done": True,
        "followup_sent_at": None,
        "reply_received": False,
        "reply_context": "",
        "replied_at": None,
        "provider_receipt": receipt,
        "artifact_url": None,
        "created_at": now,
    }
    await db.campaigns.insert_one(dict(doc))
    await db.campaigns.update_one(
        {"id": camp["id"]},
        {"$set": {"followup_done": True, "followup_sent_at": now}},
    )
    return doc


@api.post("/campaigns/{campaign_id}/reply")
async def mark_reply(campaign_id: str, body: ReplyMarkRequest, user: dict = Depends(require_user)):
    """Mark whether a prospect replied to this campaign + store reply context."""
    uid = user["user_id"]
    camp = await db.campaigns.find_one({"id": campaign_id, "user_id": uid}, {"_id": 0})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    now = _iso()
    updates = {
        "reply_received": bool(body.reply_received),
        "reply_context": body.reply_context or "",
        "replied_at": now if body.reply_received else None,
    }
    await db.campaigns.update_one({"id": campaign_id, "user_id": uid}, {"$set": updates})
    return {**camp, **updates}


@api.get("/campaigns")
async def list_campaigns(user: dict = Depends(require_user)):
    uid = user["user_id"]
    items = await db.campaigns.find({"user_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    settings = await _get_user_settings(uid)
    apply_after = settings.get("apply_after_days", 7)
    cutoff = datetime.now(timezone.utc) - timedelta(days=apply_after)
    for c in items:
        c["should_apply_prompt"] = False
        if c.get("reply_status") == "rejected":
            c["should_apply_prompt"] = True
            continue
        if (
            c.get("type") == "email"
            and c.get("followup_done")
            and c.get("followup_sent_at")
            and not c.get("reply_received")
        ):
            try:
                fs = datetime.fromisoformat(c["followup_sent_at"])
                if fs.tzinfo is None:
                    fs = fs.replace(tzinfo=timezone.utc)
                if fs < cutoff:
                    c["should_apply_prompt"] = True
            except (ValueError, TypeError):
                pass
    return items


@api.get("/jobs/{job_id}/campaigns")
async def job_campaigns(job_id: str, user: dict = Depends(require_user)):
    items = await db.campaigns.find(
        {"user_id": user["user_id"], "job_id": job_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    return items


# -------------------- Cover letter (Sonnet + mock GCS) --------------------

@api.post("/jobs/{job_id}/cover-letter")
async def create_cover_letter(job_id: str, body: CoverLetterRequest, user: dict = Depends(require_user)):
    job = await db.jobs.find_one({"id": job_id, "user_id": user["user_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    profile = await get_candidate_profile(user["user_id"])
    company_context = body.company_context or mock_scraper.mock_company_context(job["company"])
    content = await ai_service.generate_cover_letter(job, company_context, profile)
    gcs = mock_scraper.mock_gcs_put_pdf(job_id, content.get("body", ""))
    now = _iso()
    doc = {
        "id": f"camp_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "job_id": job_id,
        "prospect_id": None,
        "parent_campaign_id": None,
        "type": "cover_letter",
        "subject": content.get("subject", ""),
        "body": content.get("body", ""),
        "status": "draft",
        "sent_at": None,
        "followup_done": True,  # cover letters don't trigger follow-ups
        "followup_sent_at": None,
        "reply_received": False,
        "reply_context": "",
        "replied_at": None,
        "provider_receipt": None,
        "artifact_url": gcs.get("signed_url"),
        "created_at": now,
    }
    await db.campaigns.insert_one(dict(doc))
    # Persist company_context on the job for reuse (interview answers)
    await db.jobs.update_one(
        {"id": job_id, "user_id": user["user_id"]},
        {"$set": {"company_context": company_context}},
    )
    return {"campaign": doc, "storage": gcs}


# -------------------- Skills & gaps --------------------

@api.post("/skills/aggregate")
async def aggregate_skills(user: dict = Depends(require_user)):
    """Rebuild skills from current jobs (preserves job_ids[]) and runs Haiku for project-swap suggestions."""
    uid = user["user_id"]
    # Build skill → {count, job_ids} from current jobs
    tally: dict[str, dict] = {}
    async for j in db.jobs.find({"user_id": uid}, {"_id": 0, "id": 1, "gaps": 1}):
        for g in j.get("gaps", []) or []:
            key = (g or "").strip().lower()
            if not key:
                continue
            entry = tally.setdefault(key, {"count": 0, "job_ids": []})
            entry["count"] += 1
            if j["id"] not in entry["job_ids"]:
                entry["job_ids"].append(j["id"])
    if not tally:
        await db.skills.delete_many({"user_id": uid})
        return {"inserted": 0, "skills": []}
    top = sorted(tally.items(), key=lambda x: -x[1]["count"])[:12]
    payload = [{"skill": s, "frequency": v["count"]} for s, v in top]
    swaps = await ai_service.suggest_project_swaps(payload)
    swap_map = {(s.get("skill") or "").strip().lower(): s.get("project_swap_suggestion", "") for s in swaps}

    await db.skills.delete_many({"user_id": uid})
    now = _iso()
    rows = []
    for skill, v in top:
        doc = {
            "id": f"skill_{uuid.uuid4().hex[:10]}",
            "user_id": uid,
            "skill": skill,
            "frequency": v["count"],
            "job_ids": v["job_ids"],
            "project_swap_suggestion": swap_map.get(skill, ""),
            "created_at": now,
        }
        await db.skills.insert_one(dict(doc))
        rows.append(doc)
    return {"inserted": len(rows), "skills": rows}


@api.get("/skills")
async def list_skills(user: dict = Depends(require_user)):
    items = await db.skills.find({"user_id": user["user_id"]}, {"_id": 0}).sort("frequency", -1).to_list(100)
    return items


# -------------------- Resumes --------------------

@api.post("/resumes")
async def create_resume(body: ResumeIn, user: dict = Depends(require_user)):
    now = _iso()
    if body.is_default:
        await db.resumes.update_many({"user_id": user["user_id"]}, {"$set": {"is_default": False}})
    doc = {
        "id": f"res_{uuid.uuid4().hex[:10]}",
        "user_id": user["user_id"],
        "name": body.name,
        "content": body.content,
        "is_default": body.is_default,
        "created_at": now,
    }
    await db.resumes.insert_one(dict(doc))
    return doc


@api.get("/resumes")
async def list_resumes(user: dict = Depends(require_user)):
    items = await db.resumes.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return items


@api.delete("/resumes/{resume_id}")
async def delete_resume(resume_id: str, user: dict = Depends(require_user)):
    res = await db.resumes.delete_one({"id": resume_id, "user_id": user["user_id"]})
    return {"deleted": res.deleted_count}


@api.post("/resumes/{resume_id}/default")
async def set_default_resume(resume_id: str, user: dict = Depends(require_user)):
    target = await db.resumes.find_one({"id": resume_id, "user_id": user["user_id"]}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Resume not found")
    await db.resumes.update_many({"user_id": user["user_id"]}, {"$set": {"is_default": False}})
    await db.resumes.update_one({"id": resume_id}, {"$set": {"is_default": True}})
    return {"ok": True}


# -------------------- Scheduler --------------------

@api.get("/scheduler/status")
async def scheduler_status(user: dict = Depends(require_user)):
    uid = user["user_id"]
    settings = await _get_user_settings(uid)
    followup_days = settings.get("followup_days", 3)
    cutoff = datetime.now(timezone.utc) - timedelta(days=followup_days)
    pending = 0
    due = 0
    async for c in db.campaigns.find(
        {"user_id": uid, "followup_done": False, "type": "email", "status": "sent"},
        {"_id": 0, "sent_at": 1},
    ):
        pending += 1
        sent_at = c.get("sent_at")
        if isinstance(sent_at, str):
            try:
                sent_at = datetime.fromisoformat(sent_at)
            except ValueError:
                sent_at = None
        if sent_at:
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)
            if sent_at < cutoff:
                due += 1
    return {
        "pending_followups": pending,
        "due_now": due,
        "followup_after_days": followup_days,
        "apply_after_days": settings.get("apply_after_days", 7),
        "poll_minutes": scheduler_service.POLL_MINUTES,
    }


@api.post("/scheduler/run")
async def scheduler_run(user: dict = Depends(require_user)):
    summary = await scheduler_service.run_followup_sweep(db)
    return summary


# -------------------- Settings --------------------

@api.get("/settings")
async def get_settings(user: dict = Depends(require_user)):
    return await _get_user_settings(user["user_id"])


@api.post("/settings")
async def update_settings(body: SettingsIn, user: dict = Depends(require_user)):
    uid = user["user_id"]
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items() if k in DEFAULT_SETTINGS}
    if not updates:
        return await _get_user_settings(uid)
    await db.user_settings.update_one(
        {"user_id": uid},
        {"$set": {"user_id": uid, **updates, "updated_at": _iso()}},
        upsert=True,
    )
    return await _get_user_settings(uid)


# -------------------- Gmail inbox monitoring --------------------

class GmailSimulateRequest(BaseModel):
    campaign_id: str
    status: str = "progressing"  # ack | rejected | progressing | replied
    body: Optional[str] = None


@api.post("/gmail/poll")
async def gmail_poll_manual(user: dict = Depends(require_user)):
    """Manually trigger the Gmail inbox poll for THIS user only."""
    uid = user["user_id"]
    replies = await gmail_service.fetch_replies_for_user(db, uid)
    processed = 0
    for r in replies:
        res = await gmail_service.process_incoming_reply(db, r)
        if res.get("matched"):
            processed += 1
    return {"fetched": len(replies), "processed": processed}


@api.post("/gmail/simulate-reply")
async def gmail_simulate_reply(body: GmailSimulateRequest, user: dict = Depends(require_user)):
    """Dev/test helper: inject a synthetic inbound reply for a specific campaign.
    Real Gmail polling will replace this once OAuth keys are available."""
    uid = user["user_id"]
    if body.status not in {"ack", "rejected", "progressing", "replied"}:
        raise HTTPException(status_code=400, detail="invalid status")
    camp = await db.campaigns.find_one({"id": body.campaign_id, "user_id": uid}, {"_id": 0})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    prospect = await db.prospects.find_one(
        {"id": camp.get("prospect_id"), "user_id": uid}, {"_id": 0}
    )
    if not prospect:
        raise HTTPException(status_code=400, detail="Campaign has no prospect")
    if body.body:
        reply = {
            "from_email": prospect.get("email", ""),
            "to_email": "you@example.com",
            "subject": "Re: " + (camp.get("subject") or ""),
            "body": body.body,
            "received_at": _iso(),
        }
    else:
        reply = mock_scraper.mock_gmail_synthesize_reply(prospect, camp, body.status)
    result = await gmail_service.process_incoming_reply(db, reply)
    return {"reply_injected": reply, "result": result}


@api.get("/gmail/replies")
async def list_gmail_replies(user: dict = Depends(require_user)):
    items = await db.gmail_replies.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("received_at", -1).to_list(200)
    return items


# -------------------- Dashboard summary --------------------

@api.get("/dashboard/summary")
async def dashboard_summary(user: dict = Depends(require_user)):
    uid = user["user_id"]
    jobs_total = await db.jobs.count_documents({"user_id": uid})
    jobs_high = await db.jobs.count_documents({"user_id": uid, "match_pct": {"$gte": 65}})
    prospects_total = await db.prospects.count_documents({"user_id": uid})
    emails_sent = await db.campaigns.count_documents({"user_id": uid, "type": "email", "status": "sent"})
    followups_sent = await db.campaigns.count_documents({"user_id": uid, "type": "followup"})
    cover_letters = await db.campaigns.count_documents({"user_id": uid, "type": "cover_letter"})
    skills = await db.skills.count_documents({"user_id": uid})
    recent_jobs = await db.jobs.find({"user_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(5)
    recent_campaigns = await db.campaigns.find({"user_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(5)
    return {
        "jobs_total": jobs_total,
        "jobs_high_match": jobs_high,
        "prospects_total": prospects_total,
        "emails_sent": emails_sent,
        "followups_sent": followups_sent,
        "cover_letters": cover_letters,
        "skills_tracked": skills,
        "recent_jobs": recent_jobs,
        "recent_campaigns": recent_campaigns,
    }


# -------------------- Mount --------------------

app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


scheduler = None


@app.on_event("startup")
async def _startup():
    global scheduler
    try:
        scheduler = scheduler_service.start_scheduler(db)
    except Exception as e:
        logger.exception("Scheduler failed to start: %s", e)


@app.on_event("shutdown")
async def _shutdown():
    global scheduler
    if scheduler:
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass
    client.close()
