"""APScheduler: query campaigns WHERE followup_done=false AND sent_at > N days → follow-up."""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import ai_service
import mock_scraper

logger = logging.getLogger(__name__)

FOLLOWUP_DAYS = 3  # after N days without reply, send follow-up
POLL_MINUTES = 5


def _now():
    return datetime.now(timezone.utc)


def _parse_iso(val):
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val)
        except ValueError:
            return None
    return val


async def run_followup_sweep(db) -> dict:
    """Find campaigns due for follow-up and send one. Returns summary."""
    cutoff = _now() - timedelta(days=FOLLOWUP_DAYS)
    # Only top-level outreach emails are eligible (not follow-ups themselves)
    cursor = db.campaigns.find(
        {"followup_done": False, "type": "email", "status": "sent"},
        {"_id": 0},
    )
    processed = 0
    errors = 0
    async for camp in cursor:
        sent_at = _parse_iso(camp.get("sent_at"))
        if not sent_at:
            continue
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        if sent_at > cutoff:
            continue
        try:
            job = await db.jobs.find_one({"id": camp.get("job_id")}, {"_id": 0}) or {}
            prospect = await db.prospects.find_one({"id": camp.get("prospect_id")}, {"_id": 0}) or {}
            original = {"subject": camp.get("subject"), "body": camp.get("body")}
            gen = await ai_service.generate_followup_email(original, job, prospect)
            receipt = mock_scraper.mock_send_email(prospect.get("email", ""), gen["subject"], gen["body"])
            now = _now().isoformat()
            followup_doc = {
                "id": f"camp_{uuid.uuid4().hex[:12]}",
                "user_id": camp.get("user_id"),
                "job_id": camp.get("job_id"),
                "prospect_id": camp.get("prospect_id"),
                "parent_campaign_id": camp.get("id"),
                "type": "followup",
                "subject": gen["subject"],
                "body": gen["body"],
                "status": "sent",
                "sent_at": now,
                "provider_receipt": receipt,
                "followup_done": True,
                "followup_sent_at": None,
                "created_at": now,
            }
            await db.campaigns.insert_one(dict(followup_doc))
            await db.campaigns.update_one(
                {"id": camp.get("id")},
                {"$set": {"followup_done": True, "followup_sent_at": now}},
            )
            processed += 1
        except Exception as e:
            errors += 1
            logger.exception("Follow-up failed for campaign %s: %s", camp.get("id"), e)
    summary = {"processed": processed, "errors": errors, "ran_at": _now().isoformat()}
    logger.info("Follow-up sweep: %s", summary)
    return summary


def start_scheduler(db) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_followup_sweep,
        "interval",
        minutes=POLL_MINUTES,
        kwargs={"db": db},
        id="followup_sweep",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("APScheduler started (follow-up sweep every %d min)", POLL_MINUTES)
    return scheduler
