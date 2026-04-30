// Talentpath popup: grabs active tab's URL + page text, POSTs to /api/jobs/ingest.

const DEFAULT_API = "https://talentpath-app.preview.emergentagent.com";

const $ = (id) => document.getElementById(id);

function showStatus(kind, text) {
    const el = $("status");
    el.className = "status " + kind;
    el.textContent = text;
}

async function loadCfg() {
    const { tp_token, tp_api } = await chrome.storage.local.get(["tp_token", "tp_api"]);
    if (tp_token) $("token").value = tp_token;
    $("api").value = tp_api || DEFAULT_API;
}

async function saveCfg() {
    const token = $("token").value.trim();
    const api = ($("api").value.trim() || DEFAULT_API).replace(/\/+$/, "");
    await chrome.storage.local.set({ tp_token: token, tp_api: api });
    showStatus("ok", "Config saved.");
}

async function scrapeActiveTab() {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) throw new Error("No active tab.");
    // Run a content script inline to scrape the page text + URL.
    const [result] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
            const title = document.title || "";
            const text = document.body?.innerText?.slice(0, 12000) || "";
            return { url: location.href, title, text };
        },
    });
    return result.result;
}

async function addJob() {
    const btn = $("add");
    btn.disabled = true;
    showStatus("", "");
    try {
        const { tp_token, tp_api } = await chrome.storage.local.get(["tp_token", "tp_api"]);
        const token = (tp_token || $("token").value || "").trim();
        const api = ((tp_api || $("api").value || DEFAULT_API).trim()).replace(/\/+$/, "");
        if (!token) throw new Error("Paste your session token and click 'Save config' first.");

        const scraped = await scrapeActiveTab();
        // Send URL if present; otherwise send body text. Backend handles both.
        const input = scraped.url && scraped.url.startsWith("http")
            ? scraped.url
            : `${scraped.title}\n\n${scraped.text}`;

        const resp = await fetch(`${api}/api/jobs/ingest`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ input }),
        });
        if (!resp.ok) {
            let detail = `HTTP ${resp.status}`;
            try {
                const j = await resp.json();
                if (j.detail) detail = j.detail;
            } catch {}
            throw new Error(detail);
        }
        const job = await resp.json();
        showStatus("ok", `Added: ${job.title} @ ${job.company} · ${job.match_pct ?? 0}% match`);
    } catch (e) {
        showStatus("err", "Failed: " + (e.message || e));
    } finally {
        btn.disabled = false;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    loadCfg();
    $("add").addEventListener("click", addJob);
    $("saveCfg").addEventListener("click", saveCfg);
});
