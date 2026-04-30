# Talentpath — Hub-and-Spoke Job Application Pipeline (PRD)

## Original problem statement
Full-stack job application pipeline — refactored from sequential pipeline to hub-and-spoke.
5 tabs (Jobs, Prospects, Campaigns, Skills, Company Research). Every action logs to DB.
User can jump to any tab in any order. Non-blocking.

## Architecture
- DB: MongoDB — collections: users, user_sessions, jobs, prospects, campaigns, skills, resumes, user_settings
- LLMs via Emergent Universal Key: Haiku 4.5 (scoring, swaps, routing — non-LLM work is DB/scraping/scheduling), Sonnet 4.5 (email, cover letter, LinkedIn notes, interview answers)
- Auth: Emergent-managed Google Auth, cookie + localStorage Bearer fallback, 7-day session
- Scheduler: APScheduler per-user `followup_days` (defaults 3), `apply_after_days` (defaults 7) — triggers follow-up then flags `should_apply_prompt`
- MOCKED: Playwright scraping, Apify + Hunter.io + Vibe Prospecting MCP, Gmail SMTP send, GCS PDF storage, Company research

## Data model (extended)
- `jobs`: id, user_id, title, company, url, location, description, score, match_reason, gaps[], status, **company_context**, **interview_answers[]**, created_at
- `prospects`: id, user_id, **job_id**, name, role, company, email, linkedin, source, confidence, **priority**, created_at
- `campaigns`: id, user_id, **job_id, prospect_id**, parent_campaign_id, type (email|linkedin|cover_letter|followup), subject, body, status, sent_at, followup_done, followup_sent_at, **reply_received, reply_context, replied_at**, artifact_url, provider_receipt, created_at — plus computed `should_apply_prompt`
- `skills`: id, user_id, skill, frequency, **job_ids[]**, project_swap_suggestion, created_at
- `resumes`: id, user_id, name, content, is_default, created_at
- `user_settings` (new): user_id, followup_days (3), apply_after_days (7), signature, updated_at

## Implemented (2026-02, v2 refactor)
- ✅ Manual job add via `POST /api/jobs` (URL+JD → Haiku scores → auto-upserts skills.job_ids[])
- ✅ Rescore existing job (`POST /api/jobs/{id}/score`) — recomputes skills
- ✅ Company research (`POST /api/jobs/{id}/research`) — stores context on job
- ✅ Interview Q&A (`POST /api/jobs/{id}/interview-answers`) — Sonnet, uses context+JD+resume
- ✅ Reply tracking (`POST /api/campaigns/{id}/reply`) — toggle, context, replied_at
- ✅ User-configurable follow-up days & apply-prompt days (`GET/POST /api/settings`)
- ✅ Computed `should_apply_prompt` in `GET /api/campaigns` (email + followup_done + !reply + old)
- ✅ Skills auto-upsert on every scoring (no full rebuild unless you run /skills/aggregate for project swaps)
- ✅ Frontend: 5 tabs, Add Job form, priority split ≥65 / <65, Settings dialog (resumes + follow-up config), Skills with clickable job chips, Campaigns with reply+apply-prompt UI, Company Research tab w/ per-job vision/mission + interview Q&A
- ✅ Backend: 39/39 pytest pass (regression + new endpoints), cross-user isolation verified

## Prioritized backlog
### P1
- Restrict `/api/scheduler/run` to admin or scope to caller
- Rate-limit Claude-backed endpoints
- DELETE /api/resumes/{id} → 404 on missing + auto-promote new default
- Add user_id filter to prospect lookups in /campaigns/send, /campaigns/{id}/followup, scheduler sweep

### P2
- Swap MOCKED integrations for real ones when API keys arrive: Apify, Hunter.io, Vibe Prospecting MCP, Gmail OAuth, GCS
- Webhook-based reply detection (auto-mark reply_received)
- Analytics: funnel conversion, reply rate, time-to-response
- Team/workspace multi-user sharing

## Next tasks
- Provide real API keys for Apify / Hunter / Vibe Prospecting / Gmail / GCS to go live
- Consider Stripe billing (SaaS: free=10 jobs/mo, Pro=unlimited + real integrations)
