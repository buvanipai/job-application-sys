import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { Jobs } from "@/lib/api";
import { useNavigate } from "react-router-dom";
import { Plus, Play, Trash2, ExternalLink, RefreshCw } from "lucide-react";
import { toast } from "sonner";

export default function JobsPage() {
    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(false);
    const [adding, setAdding] = useState(false);
    const [showAdd, setShowAdd] = useState(false);
    const [form, setForm] = useState({ title: "", company: "", url: "", location: "", description: "" });
    const navigate = useNavigate();

    const load = async () => setJobs(await Jobs.list());
    useEffect(() => {
        load();
    }, []);

    const addJob = async () => {
        if (!form.title.trim() || !form.company.trim() || !form.description.trim()) {
            toast.error("Title, company, and JD are required.");
            return;
        }
        setAdding(true);
        try {
            await Jobs.add(form);
            toast.success("Job added and scored.");
            setForm({ title: "", company: "", url: "", location: "", description: "" });
            setShowAdd(false);
            await load();
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Add failed.");
        } finally {
            setAdding(false);
        }
    };

    const scrape = async () => {
        setLoading(true);
        try {
            const res = await Jobs.scrape(6);
            toast.success(`Added ${res.inserted} sample jobs · skipped ${res.skipped_duplicates}.`);
            await load();
        } catch {
            toast.error("Seed failed.");
        } finally {
            setLoading(false);
        }
    };

    const rescore = async (id) => {
        try {
            await Jobs.rescore(id);
            toast.success("Rescored.");
            await load();
        } catch {
            toast.error("Rescore failed.");
        }
    };

    const del = async (id) => {
        await Jobs.del(id);
        await load();
    };

    const high = jobs.filter((j) => j.score >= 65);
    const low = jobs.filter((j) => j.score < 65);

    return (
        <Layout>
            <div className="flex items-start justify-between gap-4 mb-6">
                <div>
                    <h1 className="font-heading text-4xl sm:text-5xl font-extrabold tracking-tight">
                        Jobs
                    </h1>
                    <p className="font-mono text-xs uppercase tracking-wider text-jp-sub mt-1">
                        paste JDs · scored vs your default resume (Haiku 4.5)
                    </p>
                </div>
                <div className="flex gap-2">
                    <button
                        data-testid="jobs-add-toggle"
                        onClick={() => setShowAdd((v) => !v)}
                        className="jp-btn inline-flex items-center gap-2"
                        style={{ background: "#a491d3", borderColor: "#8170a9" }}
                    >
                        <Plus size={16} />
                        {showAdd ? "Close" : "Add job"}
                    </button>
                    <button
                        data-testid="jobs-scrape-btn"
                        onClick={scrape}
                        disabled={loading}
                        className="jp-btn inline-flex items-center gap-2"
                        style={{ background: "#f5f2b8", borderColor: "#c4c193" }}
                    >
                        <Play size={16} /> {loading ? "seeding…" : "Seed samples"}
                    </button>
                </div>
            </div>

            {showAdd ? (
                <div
                    className="jp-card p-5 mb-6"
                    style={{ background: "#f5f2b8", borderColor: "#c4c193" }}
                    data-testid="add-job-form"
                >
                    <div className="font-mono text-[11px] uppercase tracking-wider mb-2">
                        new job
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <input
                            data-testid="job-title"
                            className="jp-input"
                            placeholder="Title"
                            value={form.title}
                            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                        />
                        <input
                            data-testid="job-company"
                            className="jp-input"
                            placeholder="Company"
                            value={form.company}
                            onChange={(e) => setForm((f) => ({ ...f, company: e.target.value }))}
                        />
                        <input
                            data-testid="job-url"
                            className="jp-input"
                            placeholder="Job URL (optional)"
                            value={form.url}
                            onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
                        />
                        <input
                            data-testid="job-location"
                            className="jp-input"
                            placeholder="Location (optional)"
                            value={form.location}
                            onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))}
                        />
                    </div>
                    <textarea
                        data-testid="job-description"
                        className="jp-input mt-3 min-h-[160px]"
                        placeholder="Paste the full job description here…"
                        value={form.description}
                        onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                    />
                    <button
                        data-testid="job-add-submit"
                        onClick={addJob}
                        disabled={adding}
                        className="jp-btn inline-flex items-center gap-2 mt-3"
                        style={{ background: "#a491d3", borderColor: "#8170a9" }}
                    >
                        <Plus size={14} /> {adding ? "scoring…" : "Add + score"}
                    </button>
                </div>
            ) : null}

            <PrioritySection
                title="Priority list — high match (≥65%)"
                subtitle="what's still missing to close the gap"
                tone="high"
                items={high}
                onOpen={(id) => navigate(`/jobs/${id}`)}
                onDelete={del}
                onRescore={rescore}
            />
            <PrioritySection
                title="Lower match (<65%)"
                subtitle="1-line reason shown — consider rewriting resume or skipping"
                tone="low"
                items={low}
                onOpen={(id) => navigate(`/jobs/${id}`)}
                onDelete={del}
                onRescore={rescore}
            />

            {jobs.length === 0 ? (
                <div className="jp-card p-10 text-center font-mono text-sm text-jp-sub">
                    No jobs yet. Click <b>Add job</b> to paste a JD, or <b>Seed samples</b> for demo
                    data. Make sure to set a default resume in Settings first.
                </div>
            ) : null}
        </Layout>
    );
}

function PrioritySection({ title, subtitle, tone, items, onOpen, onDelete, onRescore }) {
    if (!items.length) return null;
    const styles =
        tone === "high"
            ? { background: "#c5dca0", borderColor: "#9db080" }
            : { background: "#f9dad0", borderColor: "#c7aea6" };
    return (
        <section className="mb-6">
            <div
                className="rounded-lg px-4 py-3 mb-3 flex items-center justify-between"
                style={{ background: styles.background, border: `1.5px solid ${styles.borderColor}` }}
            >
                <div>
                    <div className="font-heading font-bold">{title}</div>
                    <div className="font-mono text-[11px] opacity-70">{subtitle}</div>
                </div>
                <div
                    className="jp-pill"
                    style={{ background: "#FFFFFF", borderColor: "#E0E0E0" }}
                    data-testid={`count-${tone}`}
                >
                    {items.length} jobs
                </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {items.map((j) => (
                    <JobCard
                        key={j.id}
                        j={j}
                        tone={tone}
                        onOpen={() => onOpen(j.id)}
                        onDelete={() => onDelete(j.id)}
                        onRescore={() => onRescore(j.id)}
                    />
                ))}
            </div>
        </section>
    );
}

function JobCard({ j, tone, onOpen, onDelete, onRescore }) {
    return (
        <div
            data-testid={`job-card-${j.id}`}
            className="jp-card p-4 cursor-pointer transition-colors hover:bg-black/5"
            onClick={onOpen}
        >
            <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                    <div className="font-heading font-bold truncate">{j.title}</div>
                    <div className="font-mono text-xs text-jp-sub truncate">
                        {j.company} · {j.location || "remote"}
                    </div>
                </div>
                <span
                    className="jp-pill"
                    style={
                        tone === "high"
                            ? { background: "#c5dca0", borderColor: "#9db080" }
                            : { background: "#f9dad0", borderColor: "#c7aea6" }
                    }
                >
                    {j.score}%
                </span>
            </div>

            {tone === "high" ? (
                <div className="mt-3">
                    <div className="font-mono text-[11px] uppercase tracking-wider text-jp-sub mb-1">
                        what's missing
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                        {(j.gaps || []).slice(0, 6).map((g, i) => (
                            <span
                                key={i}
                                className="jp-pill"
                                style={{ background: "#f5f2b8", borderColor: "#c4c193" }}
                            >
                                {g}
                            </span>
                        ))}
                        {(j.gaps || []).length === 0 ? (
                            <span className="font-mono text-xs text-jp-sub">no gaps detected</span>
                        ) : null}
                    </div>
                </div>
            ) : (
                <div className="mt-3 font-mono text-xs text-[#1A1A1A]/80 line-clamp-2">
                    {j.match_reason || "No reason provided."}
                </div>
            )}

            <div className="flex items-center gap-2 mt-3" onClick={(e) => e.stopPropagation()}>
                <button
                    data-testid={`rescore-${j.id}`}
                    onClick={onRescore}
                    className="jp-btn text-sm inline-flex items-center gap-1"
                    style={{ background: "#818aa3", borderColor: "#656c82" }}
                >
                    <RefreshCw size={12} /> rescore
                </button>
                {j.url ? (
                    <a
                        href={j.url}
                        target="_blank"
                        rel="noreferrer"
                        data-testid={`jd-open-${j.id}`}
                        className="jp-btn text-sm inline-flex items-center gap-1"
                        style={{ background: "#FFFFFF", borderColor: "#E0E0E0" }}
                    >
                        <ExternalLink size={12} /> JD
                    </a>
                ) : null}
                <button
                    data-testid={`delete-job-${j.id}`}
                    onClick={onDelete}
                    className="jp-btn text-sm ml-auto"
                    style={{ background: "#FFFFFF", borderColor: "#E0E0E0" }}
                >
                    <Trash2 size={12} />
                </button>
            </div>
        </div>
    );
}
