# Talentpath — Hub-and-Spoke Job Pipeline (PRD, iteration 3)

## Original problem statement
Full-stack job application pipeline — hub-and-spoke: 5 tabs, every action logs immediately, user can jump to any tab in any order. Non-blocking.
Gmail inbox monitoring auto-classifies replies. Single-input Add Job form. Chrome extension for one-click capture from any job board.

## Architecture
- DB: MongoDB — users, user_sessions, jobs, prospects, campaigns, skills, resumes, user_settings, **gmail_replies**
- LLMs via Emergent Universal Key: Haiku 4.5 for scoring, routing, gap extraction, JD field extraction; Sonnet 4.5 for email/cover-letter/LinkedIn/follow-up/interview answers
- Keyword-based (NO LLM) reply classifier: ack | rejected | progressing | replied
- Auth: Emergent-managed Google Auth (cookie + localStorage Bearer fallback, 7-day session)
- Scheduler: APScheduler — follow-up sweep (per-user `followup_days`), Gmail inbox poll (every 15m, stub until real OAuth)
- MOCKED: Playwright URL fetch, Apify + Hunter + Vibe Prospecting MCP, Gmail inbox polling, Gmail SMTP send, GCS PDF storage, Company research
- Chrome Extension (MV3): scrapes active tab → POSTs to `/api/jobs/ingest` with Bearer token

## Job model (MongoDB sample)
```json
{
  "id": "job_9aa85a0bbd44",
  "user_id": "user_abc123",
  "title": "Senior Backend Engineer",
  "company": "Parallax Systems",
  "url": "https://jobs.parallax.io/senior-backend-engineer",
  "location": "Remote • US",
  "description": "Build high-throughput Python services...",
  "status": "new",
  "source": "url",  // url | paste | seed | manual
  "created_at": "2026-04-30T03:25:32+00:00",

  // Canonical (per spec)
  "match_pct": 88,
  "missing_skills": ["Kafka", "Distributed systems at scale", "Mentorship track record"],
  "reason_if_low": "",  // empty when match_pct >= 65

  // Optional
  "company_context": "",
  "interview_answers": null,

  // Legacy aliases (still written for backward compat)
  "score": 88, "gaps": [...], "match_reason": "Strong fit..."
}
```

## Endpoints (new this iteration)
- `POST /api/jobs/ingest` — single-input: URL → mock Playwright fetch; text → Haiku extracts {title, company, location, description}. Scores + upserts skills.
- `POST /api/gmail/poll` — per-user trigger; returns `{fetched, processed, mocked:true}` until real OAuth.
- `POST /api/gmail/simulate-reply` — dev helper; body `{campaign_id, status: ack|rejected|progressing|replied, body?}`; classifies & applies.
- `GET /api/gmail/replies` — audit log of all processed inbox replies (user-scoped).

## Chrome Extension (`/app/extension/`)
- `manifest.json` (MV3), `popup.html`, `popup.js`, `content.js` (placeholder), `icon.png`, `README.md`
- User pastes session token once (stored in `chrome.storage.local`). Click button → scrape URL + body text → POST /api/jobs/ingest → green toast with title/company/match %.

## Testing
- **62/62 pytest pass (100%)** across `test_backend_api.py`, `test_backend_refactor.py`, `test_backend_ingest_gmail.py`.

## Prioritized backlog
### P1
- Real Gmail API integration (OAuth keys → implement `fetch_replies_for_user`)
- Rate-limit Claude-backed endpoints
- Admin-only `/api/scheduler/run`

### P2
- Real Apify / Hunter / Vibe Prospecting MCP / GCS
- "Copy extension token" button in Settings (one-click provisioning)
- Webhook-based reply detection (Gmail push) → eliminate polling

## Next tasks
- Provide Apify/Hunter/Vibe/Gmail OAuth/GCS keys to go live
- Consider Stripe (SaaS: free=10 jobs/mo; Pro=unlimited + real integrations)
