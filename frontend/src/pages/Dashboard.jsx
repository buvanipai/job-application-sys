import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import PipelineFlow from "@/components/PipelineFlow";
import { Dashboard, Jobs, Scheduler } from "@/lib/api";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { Play, Clock, TrendingUp } from "lucide-react";

export default function DashboardPage() {
    const [summary, setSummary] = useState(null);
    const [sched, setSched] = useState(null);
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    const load = async () => {
        try {
            const [s, sc] = await Promise.all([Dashboard.summary(), Scheduler.status()]);
            setSummary(s);
            setSched(sc);
        } catch (e) {
            console.error(e);
        }
    };

    useEffect(() => {
        load();
    }, []);

    const scrape = async () => {
        setLoading(true);
        try {
            const res = await Jobs.scrape(6);
            toast.success(
                `Scraped ${res.inserted} new jobs (skipped ${res.skipped_duplicates} dupes).`
            );
            await load();
        } catch (e) {
            toast.error("Scrape failed: " + (e?.response?.data?.detail || e.message));
        } finally {
            setLoading(false);
        }
    };

    const runSweep = async () => {
        try {
            const res = await Scheduler.run();
            toast.success(`Follow-up sweep: ${res.processed} processed.`);
            await load();
        } catch (e) {
            toast.error("Sweep failed.");
        }
    };

    const counts = {
        scrape: summary?.jobs_total ?? 0,
        score: summary?.jobs_total ?? 0,
        db: summary?.jobs_total ?? 0,
        skills: summary?.skills_tracked ?? 0,
        prospects: summary?.prospects_total ?? 0,
        write: (summary?.emails_sent ?? 0) + (summary?.cover_letters ?? 0),
        send: summary?.emails_sent ?? 0,
        followup: summary?.followups_sent ?? 0,
    };

    return (
        <Layout>
            <div className="flex items-start justify-between gap-4 mb-6">
                <div>
                    <h1 className="font-heading text-4xl sm:text-5xl font-extrabold tracking-tight">
                        Pipeline
                    </h1>
                    <p className="font-mono text-xs uppercase tracking-wider text-jp-sub mt-1">
                        live stages · color-coded by responsibility
                    </p>
                </div>
                <div className="flex gap-2">
                    <button
                        data-testid="run-scrape-btn"
                        onClick={scrape}
                        disabled={loading}
                        className="jp-btn inline-flex items-center gap-2"
                        style={{ background: "#a491d3", borderColor: "#8170a9" }}
                    >
                        <Play size={16} />
                        {loading ? "scraping…" : "Run scrape"}
                    </button>
                    <button
                        data-testid="run-sweep-btn"
                        onClick={runSweep}
                        className="jp-btn inline-flex items-center gap-2"
                        style={{ background: "#f9dad0", borderColor: "#c7aea6" }}
                    >
                        <Clock size={16} />
                        Run follow-up sweep
                    </button>
                </div>
            </div>

            <PipelineFlow counts={counts} />

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
                <Stat label="Jobs scraped" value={summary?.jobs_total} fill="#f5f2b8" border="#c4c193" />
                <Stat label="High-match (≥70)" value={summary?.jobs_high_match} fill="#c5dca0" border="#9db080" />
                <Stat label="Prospects" value={summary?.prospects_total} fill="#818aa3" border="#656c82" />
                <Stat label="Emails sent" value={summary?.emails_sent} fill="#a491d3" border="#8170a9" />
                <Stat label="Follow-ups sent" value={summary?.followups_sent} fill="#f9dad0" border="#c7aea6" />
                <Stat label="Cover letters" value={summary?.cover_letters} fill="#c5dca0" border="#9db080" />
                <Stat label="Skills tracked" value={summary?.skills_tracked} fill="#a491d3" border="#8170a9" />
                <Stat
                    label="Pending follow-ups"
                    value={sched?.pending_followups}
                    sub={`${sched?.due_now ?? 0} due now`}
                    fill="#f9dad0"
                    border="#c7aea6"
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-6">
                <div className="jp-card p-6">
                    <div className="flex items-center justify-between mb-3">
                        <div>
                            <div className="font-mono text-[11px] uppercase tracking-wider text-jp-sub">
                                recent jobs
                            </div>
                            <h3 className="font-heading text-xl font-bold">Latest scraped</h3>
                        </div>
                        <TrendingUp size={18} />
                    </div>
                    <div className="space-y-2">
                        {(summary?.recent_jobs || []).map((j) => (
                            <button
                                key={j.id}
                                data-testid={`recent-job-${j.id}`}
                                onClick={() => navigate(`/jobs/${j.id}`)}
                                className="w-full text-left rounded-lg p-3 flex items-center justify-between transition-colors hover:bg-black/5"
                                style={{ border: "1.5px solid #E0E0E0" }}
                            >
                                <div className="min-w-0">
                                    <div className="font-heading font-semibold truncate">{j.title}</div>
                                    <div className="font-mono text-xs text-jp-sub truncate">
                                        {j.company} · {j.location || "remote"}
                                    </div>
                                </div>
                                <ScoreBadge score={j.score} />
                            </button>
                        ))}
                        {summary && summary.recent_jobs?.length === 0 ? (
                            <Empty msg="No jobs yet. Click Run scrape." />
                        ) : null}
                    </div>
                </div>

                <div className="jp-card p-6">
                    <div className="mb-3">
                        <div className="font-mono text-[11px] uppercase tracking-wider text-jp-sub">
                            recent campaigns
                        </div>
                        <h3 className="font-heading text-xl font-bold">Outreach activity</h3>
                    </div>
                    <div className="space-y-2">
                        {(summary?.recent_campaigns || []).map((c) => (
                            <div
                                key={c.id}
                                className="rounded-lg p-3"
                                style={{ border: "1.5px solid #E0E0E0" }}
                            >
                                <div className="flex items-center justify-between">
                                    <span
                                        className="jp-pill"
                                        style={campaignTypeStyle(c.type)}
                                    >
                                        {c.type}
                                    </span>
                                    <span className="font-mono text-[11px] text-jp-sub">
                                        {c.status}
                                        {c.sent_at ? ` · ${new Date(c.sent_at).toLocaleDateString()}` : ""}
                                    </span>
                                </div>
                                <div className="font-heading font-semibold mt-1 truncate">
                                    {c.subject || "(no subject)"}
                                </div>
                                <div className="font-mono text-xs text-jp-sub line-clamp-2 mt-1 whitespace-pre-wrap">
                                    {(c.body || "").slice(0, 180)}
                                </div>
                            </div>
                        ))}
                        {summary && summary.recent_campaigns?.length === 0 ? (
                            <Empty msg="No campaigns yet. Open a job to generate outreach." />
                        ) : null}
                    </div>
                </div>
            </div>
        </Layout>
    );
}

function Stat({ label, value, sub, fill, border }) {
    return (
        <div
            data-testid={`stat-${label.toLowerCase().replace(/\s+/g, "-")}`}
            className="rounded-lg p-4"
            style={{ background: fill, border: `1.5px solid ${border}` }}
        >
            <div className="font-mono text-[11px] uppercase tracking-wider opacity-70">{label}</div>
            <div className="font-heading text-3xl font-extrabold mt-1">{value ?? "–"}</div>
            {sub ? <div className="font-mono text-[11px] mt-1 opacity-70">{sub}</div> : null}
        </div>
    );
}

export function ScoreBadge({ score }) {
    const n = Number(score || 0);
    const style =
        n >= 80
            ? { background: "#c5dca0", borderColor: "#9db080" }
            : n >= 60
                ? { background: "#f5f2b8", borderColor: "#c4c193" }
                : n >= 40
                    ? { background: "#f9dad0", borderColor: "#c7aea6" }
                    : { background: "#ffffff", borderColor: "#E0E0E0" };
    return (
        <span className="jp-pill" style={style}>
            {n}
        </span>
    );
}

function Empty({ msg }) {
    return (
        <div className="font-mono text-xs text-jp-sub py-6 text-center">{msg}</div>
    );
}

export function campaignTypeStyle(type) {
    if (type === "email") return { background: "#a491d3", borderColor: "#8170a9" };
    if (type === "linkedin") return { background: "#f9dad0", borderColor: "#c7aea6" };
    if (type === "cover_letter") return { background: "#c5dca0", borderColor: "#9db080" };
    if (type === "followup") return { background: "#f9dad0", borderColor: "#c7aea6" };
    return { background: "#f5f2b8", borderColor: "#c4c193" };
}
