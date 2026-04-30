"""APScheduler: per-user follow-up sweep driven by user_settings.followup_days."""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import ai_service
import mock_scraper

logger = logging.getLogger(__name__)

# Global defaults (used only if a user has no settings row).
FOLLOWUP_DAYS = 3
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


async def _get_followup_days(db, user_id: str) -> int:
    s = await db.user_settings.find_one({"user_id": user_id}, {"_id": 0, "followup_days": 1})
    if s and isinstance(s.get("followup_days"), int):
        return s["followup_days"]
    return FOLLOWUP_DAYS


async def run_followup_sweep(db) -> dict:
    """For each eligible campaign, check that user's followup_days and send a follow-up if due."""
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
        followup_days = await _get_followup_days(db, camp.get("user_id", ""))
        cutoff = _now() - timedelta(days=followup_days)
        if sent_at > cutoff:
            continue
        try:
            uid = camp.get("user_id")
            job = await db.jobs.find_one({"id": camp.get("job_id"), "user_id": uid}, {"_id": 0}) or {}
            prospect = await db.prospects.find_one(
                {"id": camp.get("prospect_id"), "user_id": uid}, {"_id": 0}
            ) or {}
            original = {"subject": camp.get("subject"), "body": camp.get("body")}
            gen = await ai_service.generate_followup_email(original, job, prospect)
            receipt = mock_scraper.mock_send_email(prospect.get("email", ""), gen["subject"], gen["body"])
            now = _now().isoformat()
            followup_doc = {
                "id": f"camp_{uuid.uuid4().hex[:12]}",
                "user_id": uid,
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
                "reply_received": False,
                "reply_context": "",
                "replied_at": None,
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
