# Jobpath — Job Application Pipeline (PRD)

## Original problem statement
Full-stack job application pipeline app with pastel flat UI:
- Playwright scrape → Haiku score → insert jobs
- Aggregate gaps → skills + project-swap suggestions
- Apify + Hunter → prospects
- Gmail SMTP send → campaigns
- APScheduler follow-up after N days
- Optional Sonnet cover letter → GCS PDF per job_id

## Architecture decisions
- DB: MongoDB (platform-native) — collections: users, user_sessions, jobs, prospects, campaigns, skills, resumes
- LLMs via Emergent Universal Key (emergentintegrations): Haiku 4.5 (scoring, swaps), Sonnet 4.5 (email, LinkedIn, cover letter, follow-up)
- Auth: Emergent-managed Google Auth (httpOnly cookie + Bearer fallback, 7-day expiry)
- Scheduler: APScheduler, 5-min poll, 3-day follow-up threshold
- MOCKED integrations: Playwright scrape (8 sample JDs), Apify+Hunter prospects, Gmail SMTP send, GCS PDF storage

## User persona
Single job-seeker / founder driving their own pipeline end-to-end, multi-user support for teams/collaboration.

## Core requirements
- Multi-user Google login
- One-click scrape → score → insert pipeline
- Per-job detail: JD, match score, gaps, prospects, campaigns, cover letter
- Campaign composer (email / LinkedIn) + sender + follow-up
- Skills dashboard with project-swap suggestions
- Resume vault with default-resume selector
- Scheduler status + manual sweep trigger

## What's implemented (2026-02)
- ✅ Full backend (13 /api routes tested, 21/21 pytest pass)
- ✅ Auth (cookie + Bearer, cross-user isolation verified)
- ✅ Jobs: scrape+Haiku scoring, dedup by URL, CRUD, status, cascade delete
- ✅ Prospects: per-job + global listing
- ✅ Campaigns: generate (email/linkedin via Sonnet), send (mock Gmail), manual + scheduled follow-up
- ✅ Cover letter: Sonnet + mock GCS signed URL
- ✅ Skills: aggregate + project-swap suggestions via Haiku
- ✅ Resumes: CRUD, default selection
- ✅ Scheduler: APScheduler 5-min sweep + manual trigger + status
- ✅ Dashboard summary endpoint
- ✅ Frontend: Login (Google), Dashboard w/ pipeline visualization, Jobs, JobDetail, Prospects, Campaigns, Skills, Resumes
- ✅ Pastel flat UI (Sora / DM Sans / JetBrains Mono), no shadows, 1.5px borders, 8px radius, color-coded pipeline stages

## Prioritized backlog
### P0
- Swap MOCKED integrations for real ones when keys arrive (Apify, Hunter.io, Gmail SMTP, GCS)

### P1
- Scope /api/scheduler/run to caller or admin-only (currently global)
- 404 on DELETE /api/jobs/{id} when not found (consistency)
- Auth logout to honor Bearer header
- Rate-limit Claude-backed endpoints

### P2
- Real Playwright scraper (target boards + selectors)
- Gmail OAuth instead of SMTP app-password
- Bulk "apply + generate all" action
- Analytics: reply-rate, time-to-response, funnel conversion
- Webhook for reply detection → auto-stop follow-up sequence
- Team/workspace multi-user sharing

## Next tasks
- Wire up real Apify actor + Hunter.io API when user provides keys
- Real Gmail SMTP or OAuth flow
- Replace mock GCS with real object storage (our built-in object storage is available)
