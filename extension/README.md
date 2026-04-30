# Talentpath Chrome Extension (MV3)

Adds a toolbar button that scrapes the current tab and POSTs it to the Talentpath
`/api/jobs/ingest` endpoint. Backend auto-extracts title / company / location /
description and scores the job against your default resume.

## Install (dev mode)
1. Open `chrome://extensions`
2. Turn on **Developer mode** (top-right)
3. Click **Load unpacked**
4. Select this `/app/extension` folder
5. Pin the extension to your toolbar

## First-time setup
1. Click the Talentpath icon → paste your **session token** (get from your
   browser's DevTools → Application → Local Storage → `jp_session_token`).
2. (Optional) Change the **Backend URL** if you self-host.
3. Click **Save config**.

## Use
1. Navigate to any job posting (LinkedIn, Greenhouse, Lever, company careers page…).
2. Click the Talentpath toolbar button → **Add to Talentpath**.
3. You'll see a green status with the job title, company, and match %.
4. Open the app → the job appears in your priority list.

## Files
- `manifest.json` — MV3 manifest. `host_permissions` is `<all_urls>` so the
  popup can scrape any job page.
- `popup.html` / `popup.js` — the single-button UI + scrape + POST.
- `content.js` — placeholder for future inline features.

## Security note
The session token is stored in `chrome.storage.local`, which is scoped to the
extension and not accessible to websites. Rotate it if you lose the device.
