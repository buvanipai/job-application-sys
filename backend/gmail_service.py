"""Gmail inbox monitoring.

- Keyword-based classification (NO LLM — per spec).
- Matches replies to campaigns by prospect email address.
- Updates campaigns.reply_received, reply_context, reply_status, replied_at.
- Real Gmail integration: implement `fetch_replies_for_user(...)` against the Gmail API
  once OAuth is wired up. Until then, `mock_fetch_replies` is used (exposed via an admin
  endpoint so tests/dev can inject a reply for any campaign on demand).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# Keyword buckets — ordered by priority (first match wins).
CLASSIFIERS = [
    ("ack", [
        "thank you for applying",
        "received your application",
        "we have received your",
        "application has been received",
        "thanks for your interest — we got your application",
    ]),
    ("rejected", [
        "moving forward with other",
        "not a fit",
        "decided to move forward with other candidates",
        "decided to proceed with other candidates",
        "we have decided not to",
        "unfortunately",
        "will not be moving forward",
    ]),
    ("progressing", [
        "next steps",
        "schedule a call",
        "assessment",
        "take-home",
        "take home",
        "interview",
        "availability",
        "would love to chat",
        "meet with",
    ]),
]


def classify_reply(body: str, subject: Optional[str] = "") -> str:
    """Return one of: ack | rejected | progressing | replied (default)."""
    text = f"{subject or ''}\n{body or ''}".lower()
    for status, phrases in CLASSIFIERS:
        for p in phrases:
            if p in text:
                return status
    return "replied"


async def process_incoming_reply(db, reply: dict, user_id: Optional[str] = None) -> dict:
    """Match an incoming reply (from Gmail) to a campaign by prospect email + update it.
    If `user_id` is provided, restrict prospect/campaign lookups to that user
    (required once real Gmail OAuth is wired so replies attribute to the correct tenant).
    Returns a summary dict: {matched: bool, campaign_id, reply_status, ...}.
    """
    from_email = (reply.get("from_email") or "").strip().lower()
    if not from_email:
        return {"matched": False, "reason": "no from_email"}
    prospect_q = {"email": from_email}
    if user_id:
        prospect_q["user_id"] = user_id
    prospect = await db.prospects.find_one(prospect_q, {"_id": 0}, sort=[("created_at", -1)])
    if not prospect:
        return {"matched": False, "reason": "no prospect"}
    camp = await db.campaigns.find_one(
        {
            "user_id": prospect["user_id"],
            "prospect_id": prospect["id"],
            "type": "email",
            "status": "sent",
        },
        {"_id": 0},
        sort=[("sent_at", -1)],
    )
    if not camp:
        return {"matched": False, "reason": "no sent campaign"}
    status = classify_reply(reply.get("body", ""), reply.get("subject", ""))
    now = datetime.now(timezone.utc).isoformat()
    await db.campaigns.update_one(
        {"id": camp["id"], "user_id": camp["user_id"]},
        {
            "$set": {
                "reply_received": True,
                "reply_context": (reply.get("body") or "")[:2000],
                "reply_status": status,
                "replied_at": reply.get("received_at") or now,
            }
        },
    )
    await db.gmail_replies.insert_one({
        "user_id": prospect["user_id"],
        "campaign_id": camp["id"],
        "prospect_id": prospect["id"],
        "from_email": from_email,
        "subject": reply.get("subject", ""),
        "body": reply.get("body", ""),
        "received_at": reply.get("received_at") or now,
        "reply_status": status,
    })
    return {
        "matched": True,
        "campaign_id": camp["id"],
        "user_id": prospect["user_id"],
        "prospect_id": prospect["id"],
        "reply_status": status,
    }


async def fetch_replies_for_user(db, user_id: str) -> list[dict]:
    """Return new inbox replies for a user since last poll.
    REAL IMPLEMENTATION (requires Gmail OAuth keys + refresh tokens):
        from googleapiclient.discovery import build
        creds = load_user_credentials(db, user_id)
        svc = build('gmail', 'v1', credentials=creds)
        msgs = svc.users().messages().list(userId='me', q='is:unread newer_than:1d').execute()
        ...
    For now returns []; dev uses POST /api/gmail/simulate-reply to inject test replies.
    """
    return []


async def run_gmail_poll(db) -> dict:
    """Scheduler-driven sweep: poll each user's inbox, classify & update campaigns."""
    processed = 0
    errors = 0
    async for u in db.users.find({}, {"_id": 0, "user_id": 1}):
        uid = u.get("user_id")
        if not uid:
            continue
        try:
            replies = await fetch_replies_for_user(db, uid)
            for r in replies:
                res = await process_incoming_reply(db, r, user_id=uid)
                if res.get("matched"):
                    processed += 1
        except Exception as e:
            errors += 1
            logger.exception("Gmail poll failed for %s: %s", uid, e)
    summary = {
        "processed": processed,
        "errors": errors,
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("Gmail poll: %s", summary)
    return summary
