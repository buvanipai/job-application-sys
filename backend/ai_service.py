"""LLM helpers for Haiku (scoring/routing/dedup) and Sonnet (content generation)."""
import os
import json
import uuid
import re
import logging
from pathlib import Path
from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage

# Ensure backend/.env is loaded before reading EMERGENT_LLM_KEY (this module may
# be imported before server.py calls load_dotenv).
load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger(__name__)


def _llm_key() -> str:
    return os.environ.get("EMERGENT_LLM_KEY", "")

HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-5-20250929"


def _extract_json(text: str):
    """Extract first JSON object or array from a model response."""
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidate = fence.group(1).strip() if fence else text.strip()
    # Try object first, then array
    for pattern in (r"\{.*\}", r"\[.*\]"):
        m = re.search(pattern, candidate, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


async def _chat(model: str, system: str, user: str, session_id: str | None = None) -> str:
    chat = LlmChat(
        api_key=_llm_key(),
        session_id=session_id or f"jp-{uuid.uuid4().hex[:10]}",
        system_message=system,
    ).with_model("anthropic", model)
    resp = await chat.send_message(UserMessage(text=user))
    return resp if isinstance(resp, str) else str(resp)


# -------------------- Haiku: scoring, dedup, routing --------------------

async def score_jobs_batch(jobs: list[dict], profile: str) -> list[dict]:
    """Score a batch of jobs against the user's profile. Returns list aligned with input."""
    system = (
        "You are a strict JD-to-candidate match scorer. Given a candidate profile and a list of "
        "job descriptions, return JSON array with objects: {index, score (0-100 integer), "
        "match_reason (1 short sentence), gaps (list of 1-5 short skill/topic strings missing). "
        "Respond with ONLY a JSON array, no prose."
    )
    job_payload = [
        {"index": i, "title": j.get("title", ""), "company": j.get("company", ""),
         "description": (j.get("description", "") or "")[:1500]}
        for i, j in enumerate(jobs)
    ]
    user_msg = (
        f"CANDIDATE PROFILE:\n{profile[:2000]}\n\n"
        f"JOBS:\n{json.dumps(job_payload, ensure_ascii=False)}\n\n"
        "Return JSON array now."
    )
    raw = await _chat(HAIKU, system, user_msg)
    parsed = _extract_json(raw)
    results = []
    if isinstance(parsed, list):
        by_idx = {int(item.get("index", i)): item for i, item in enumerate(parsed)}
        for i in range(len(jobs)):
            item = by_idx.get(i, {})
            results.append({
                "score": int(item.get("score", 0) or 0),
                "match_reason": item.get("match_reason", "") or "",
                "gaps": item.get("gaps", []) or [],
            })
    else:
        logger.warning("Haiku scoring returned non-list; defaulting. Raw: %s", raw[:200])
        for _ in jobs:
            results.append({"score": 0, "match_reason": "scoring unavailable", "gaps": []})
    return results


async def suggest_project_swaps(skill_gaps: list[dict]) -> list[dict]:
    """For each aggregated skill gap, suggest a project swap idea (via Haiku)."""
    if not skill_gaps:
        return []
    system = (
        "You are a career coach. Given a list of frequently missing skills from job applications, "
        "suggest ONE concrete side project per skill that a candidate could build to demonstrate it. "
        "Return JSON array: [{skill, project_swap_suggestion (1-2 sentences)}]. JSON only."
    )
    user_msg = f"GAPS:\n{json.dumps(skill_gaps, ensure_ascii=False)}\n\nReturn JSON now."
    raw = await _chat(HAIKU, system, user_msg)
    parsed = _extract_json(raw)
    if isinstance(parsed, list):
        return parsed
    return [{"skill": g.get("skill", ""), "project_swap_suggestion": ""} for g in skill_gaps]


# -------------------- Sonnet: content generation --------------------

async def generate_outreach_email(job: dict, prospect: dict, profile: str) -> dict:
    system = (
        "You write concise, personalized cold outreach emails to referral prospects for a job. "
        "Return JSON: {subject, body}. Body 120-160 words, warm but professional, 1 specific "
        "reason about the company/role, 1 CTA. Plain text body. JSON only."
    )
    user_msg = (
        f"JOB: {job.get('title')} at {job.get('company')}\n"
        f"JD SNIPPET: {(job.get('description','') or '')[:800]}\n"
        f"PROSPECT: {prospect.get('name')} — {prospect.get('role')}\n"
        f"CANDIDATE PROFILE:\n{profile[:1500]}\n\nReturn JSON now."
    )
    raw = await _chat(SONNET, system, user_msg)
    parsed = _extract_json(raw)
    if isinstance(parsed, dict) and "subject" in parsed and "body" in parsed:
        return parsed
    return {"subject": f"Interested in {job.get('title')} at {job.get('company')}", "body": raw.strip()}


async def generate_linkedin_note(job: dict, prospect: dict, profile: str) -> dict:
    system = (
        "You write LinkedIn connection note requests. Max 280 characters. Warm, specific to role. "
        "Return JSON: {body}. JSON only."
    )
    user_msg = (
        f"JOB: {job.get('title')} at {job.get('company')}\n"
        f"PROSPECT: {prospect.get('name')} — {prospect.get('role')}\n"
        f"PROFILE:\n{profile[:1000]}\n\nReturn JSON."
    )
    raw = await _chat(SONNET, system, user_msg)
    parsed = _extract_json(raw)
    body = parsed.get("body") if isinstance(parsed, dict) else raw.strip()
    return {"subject": "", "body": (body or "")[:280]}


async def generate_cover_letter(job: dict, company_context: str, profile: str) -> dict:
    system = (
        "You write tailored cover letters (300-400 words). Use concrete examples. "
        "Return JSON: {subject, body}. JSON only."
    )
    user_msg = (
        f"JOB: {job.get('title')} at {job.get('company')}\n"
        f"JD:\n{(job.get('description','') or '')[:1500]}\n\n"
        f"COMPANY CONTEXT:\n{(company_context or '')[:1200]}\n\n"
        f"CANDIDATE PROFILE:\n{profile[:2000]}\n\nReturn JSON now."
    )
    raw = await _chat(SONNET, system, user_msg)
    parsed = _extract_json(raw)
    if isinstance(parsed, dict) and "body" in parsed:
        return parsed
    return {"subject": f"Cover Letter — {job.get('title')} at {job.get('company')}", "body": raw.strip()}


async def generate_followup_email(original: dict, job: dict, prospect: dict) -> dict:
    system = (
        "You write short, polite follow-up emails to a prior outreach. 60-90 words. "
        "Reference the prior email subject lightly. Return JSON: {subject, body}. JSON only."
    )
    user_msg = (
        f"JOB: {job.get('title')} at {job.get('company')}\n"
        f"PROSPECT: {prospect.get('name')} — {prospect.get('role')}\n"
        f"PRIOR SUBJECT: {original.get('subject','')}\n"
        f"PRIOR BODY:\n{(original.get('body','') or '')[:800]}\n\nReturn JSON."
    )
    raw = await _chat(SONNET, system, user_msg)
    parsed = _extract_json(raw)
    if isinstance(parsed, dict) and "body" in parsed:
        if not parsed.get("subject"):
            parsed["subject"] = "Re: " + (original.get("subject", "") or "Following up")
        return parsed
    return {"subject": "Re: " + (original.get("subject", "") or "Following up"), "body": raw.strip()}
