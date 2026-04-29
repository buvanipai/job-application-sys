"""Job Application Pipeline API.
- Auth: Emergent Google Auth (session cookies)
- LLMs: Claude Haiku 4.5 (scoring), Claude Sonnet 4.5 (email/cover letter/LinkedIn)
- Mocked: Playwright scrape, Apify+Hunter prospect find, Gmail SMTP, GCS PDF storage
- Scheduler: APScheduler for follow-up sweeps
"""
import os
import uuid
import logging
from datetime import datetime, timezone
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
    score: int = 0
    match_reason: str = ""
    gaps: List[str] = []
    status: str = "new"  # new, applied, archived
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
    provider_receipt: Optional[dict] = None
    artifact_url: Optional[str] = None
    created_at: str


class SkillRow(BaseModel):
    id: str
    user_id: str
    skill: str
    frequency: int
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

    expires_at = datetime.now(timezone.utc).replace(microsecond=0)
    from datetime import timedelta as _td
    expires_at = expires_at + _td(days=7)
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

@api.post("/jobs/scrape")
async def scrape_jobs(body: ScrapeRequest, user: dict = Depends(require_user)):
    scraped = mock_scraper.mock_scrape_jobs(limit=body.limit)
    profile = await get_candidate_profile(user["user_id"])

    # Dedup (no LLM) against existing jobs by url
    existing_urls = set()
    async for j in db.jobs.find({"user_id": user["user_id"]}, {"_id": 0, "url": 1}):
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
        doc = {
            "id": f"job_{uuid.uuid4().hex[:12]}",
            "user_id": user["user_id"],
            "title": j["title"],
            "company": j["company"],
            "url": j.get("url"),
            "location": j.get("location"),
            "description": j["description"],
            "score": int(s.get("score", 0)),
            "match_reason": s.get("match_reason", ""),
            "gaps": s.get("gaps", []),
            "status": "new",
            "created_at": now,
        }
        await db.jobs.insert_one(dict(doc))
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
    res = await db.jobs.delete_one({"id": job_id, "user_id": user["user_id"]})
    await db.prospects.delete_many({"job_id": job_id, "user_id": user["user_id"]})
    await db.campaigns.delete_many({"job_id": job_id, "user_id": user["user_id"]})
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


@api.get("/campaigns")
async def list_campaigns(user: dict = Depends(require_user)):
    items = await db.campaigns.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(1000)
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
        "provider_receipt": None,
        "artifact_url": gcs.get("signed_url"),
        "created_at": now,
    }
    await db.campaigns.insert_one(dict(doc))
    return {"campaign": doc, "storage": gcs}


# -------------------- Skills & gaps --------------------

@api.post("/skills/aggregate")
async def aggregate_skills(user: dict = Depends(require_user)):
    """Aggregate gap frequency across user's jobs, then get Haiku project-swap suggestions."""
    freq: dict[str, int] = {}
    async for j in db.jobs.find({"user_id": user["user_id"]}, {"_id": 0, "gaps": 1}):
        for g in j.get("gaps", []) or []:
            key = (g or "").strip().lower()
            if not key:
                continue
            freq[key] = freq.get(key, 0) + 1
    if not freq:
        return {"inserted": 0, "skills": []}
    top = sorted(freq.items(), key=lambda x: -x[1])[:12]
    payload = [{"skill": s, "frequency": n} for s, n in top]
    swaps = await ai_service.suggest_project_swaps(payload)
    swap_map = {(s.get("skill") or "").strip().lower(): s.get("project_swap_suggestion", "") for s in swaps}

    # Clear previous and reinsert fresh snapshot
    await db.skills.delete_many({"user_id": user["user_id"]})
    now = _iso()
    rows = []
    for skill, n in top:
        doc = {
            "id": f"skill_{uuid.uuid4().hex[:10]}",
            "user_id": user["user_id"],
            "skill": skill,
            "frequency": n,
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
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=scheduler_service.FOLLOWUP_DAYS)
    pending = 0
    due = 0
    async for c in db.campaigns.find(
        {"user_id": user["user_id"], "followup_done": False, "type": "email", "status": "sent"},
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
        "followup_after_days": scheduler_service.FOLLOWUP_DAYS,
        "poll_minutes": scheduler_service.POLL_MINUTES,
    }


@api.post("/scheduler/run")
async def scheduler_run(user: dict = Depends(require_user)):
    summary = await scheduler_service.run_followup_sweep(db)
    return summary


# -------------------- Dashboard summary --------------------

@api.get("/dashboard/summary")
async def dashboard_summary(user: dict = Depends(require_user)):
    uid = user["user_id"]
    jobs_total = await db.jobs.count_documents({"user_id": uid})
    jobs_high = await db.jobs.count_documents({"user_id": uid, "score": {"$gte": 70}})
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
