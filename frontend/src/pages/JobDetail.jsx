import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { Jobs, Campaigns } from "@/lib/api";
import { useParams, useNavigate } from "react-router-dom";
import { ScoreBadge, campaignTypeStyle } from "@/pages/Dashboard";
import { Search, Mail, Linkedin, FileText, Send, Clock, ArrowLeft, Check } from "lucide-react";
import { toast } from "sonner";

export default function JobDetail() {
    const { id } = useParams();
    const navigate = useNavigate();
    const [job, setJob] = useState(null);
    const [prospects, setProspects] = useState([]);
    const [camps, setCamps] = useState([]);
    const [busy, setBusy] = useState(false);

    const load = async () => {
        const j = await Jobs.get(id);
        setJob(j);
        const [p, c] = await Promise.all([Jobs.prospects(id), Jobs.campaigns(id)]);
        setProspects(p);
        setCamps(c);
    };

    useEffect(() => {
        load();
    }, [id]);

    const findProspects = async () => {
        setBusy(true);
        try {
            const res = await Jobs.findProspects(id, 3);
            toast.success(`Found ${res.inserted} prospects.`);
            await load();
        } catch {
            toast.error("Prospect search failed.");
        } finally {
            setBusy(false);
        }
    };

    const generate = async (prospectId, type) => {
        setBusy(true);
        try {
            await Campaigns.generate({ job_id: id, prospect_id: prospectId, type });
            toast.success(`${type} draft created (Sonnet 4.5).`);
            await load();
        } catch (e) {
            toast.error("Generation failed: " + (e?.response?.data?.detail || e.message));
        } finally {
            setBusy(false);
        }
    };

    const coverLetter = async () => {
        setBusy(true);
        try {
            const res = await Jobs.coverLetter(id, {});
            toast.success("Cover letter generated and stored in mock GCS.");
            console.log("GCS:", res.storage);
            await load();
        } catch {
            toast.error("Cover letter failed.");
        } finally {
            setBusy(false);
        }
    };

    const sendCamp = async (cid) => {
        await Campaigns.send(cid);
        toast.success("Sent (mock Gmail SMTP).");
        await load();
    };

    const followup = async (cid) => {
        try {
            await Campaigns.followup(cid);
            toast.success("Follow-up sent.");
            await load();
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Follow-up failed.");
        }
    };

    const markApplied = async () => {
        await Jobs.setStatus(id, "applied");
        toast.success("Marked applied.");
        await load();
    };

    if (!job) return <Layout><div className="font-mono text-sm text-jp-sub">loading…</div></Layout>;

    return (
        <Layout>
            <button
                data-testid="back-btn"
                onClick={() => navigate("/jobs")}
                className="jp-btn inline-flex items-center gap-2 mb-4"
                style={{ background: "#FFFFFF", borderColor: "#E0E0E0" }}
            >
                <ArrowLeft size={14} /> Back
            </button>

            <div
                className="jp-card p-6 mb-4"
                style={{ background: "#f5f2b8", borderColor: "#c4c193" }}
                data-testid="job-header"
            >
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <div className="font-mono text-[11px] uppercase tracking-wider mb-2">job · input stage</div>
                        <h1 className="font-heading text-4xl font-extrabold tracking-tight">{job.title}</h1>
                        <div className="font-mono text-sm mt-2">
                            {job.company} · {job.location || "remote"}
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <ScoreBadge score={job.score} />
                        <button
                            data-testid="mark-applied-btn"
                            onClick={markApplied}
                            className="jp-btn inline-flex items-center gap-1"
                            style={{ background: "#c5dca0", borderColor: "#9db080" }}
                        >
                            <Check size={14} /> Applied
                        </button>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="jp-card p-6 lg:col-span-2">
                    <div className="font-mono text-[11px] uppercase tracking-wider text-jp-sub">
                        job description
                    </div>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{job.description}</p>
                </div>

                <div className="jp-card p-6" style={{ background: "#818aa3", borderColor: "#656c82" }}>
                    <div className="font-mono text-[11px] uppercase tracking-wider">Haiku · match</div>
                    <h3 className="font-heading text-xl font-bold mt-1">Why it fits</h3>
                    <p className="text-sm mt-2">{job.match_reason || "—"}</p>
                    <div className="font-mono text-[11px] uppercase tracking-wider mt-4">gaps</div>
                    <div className="flex flex-wrap gap-2 mt-2">
                        {(job.gaps || []).map((g, i) => (
                            <span
                                key={i}
                                className="jp-pill"
                                style={{ background: "#f9dad0", borderColor: "#c7aea6" }}
                            >
                                {g}
                            </span>
                        ))}
                        {(job.gaps || []).length === 0 ? (
                            <span className="font-mono text-xs">no gaps detected</span>
                        ) : null}
                    </div>
                </div>
            </div>

            <div className="flex items-center justify-between mt-8 mb-3">
                <h2 className="font-heading text-2xl font-bold">Prospects</h2>
                <div className="flex gap-2">
                    <button
                        data-testid="find-prospects-btn"
                        onClick={findProspects}
                        disabled={busy}
                        className="jp-btn inline-flex items-center gap-2"
                        style={{ background: "#818aa3", borderColor: "#656c82" }}
                    >
                        <Search size={16} /> {busy ? "searching…" : "Find prospects"}
                    </button>
                    <button
                        data-testid="cover-letter-btn"
                        onClick={coverLetter}
                        disabled={busy}
                        className="jp-btn inline-flex items-center gap-2"
                        style={{ background: "#c5dca0", borderColor: "#9db080" }}
                    >
                        <FileText size={16} /> Generate cover letter
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {prospects.map((p) => (
                    <div key={p.id} className="jp-card p-5" data-testid={`prospect-card-${p.id}`}>
                        <div className="font-heading font-bold">{p.name}</div>
                        <div className="font-mono text-xs text-jp-sub">{p.role}</div>
                        <div className="font-mono text-xs mt-2 break-all">{p.email}</div>
                        <div className="flex gap-2 mt-4">
                            <button
                                data-testid={`gen-email-${p.id}`}
                                onClick={() => generate(p.id, "email")}
                                disabled={busy}
                                className="jp-btn inline-flex items-center gap-1 text-sm"
                                style={{ background: "#a491d3", borderColor: "#8170a9" }}
                            >
                                <Mail size={14} /> Email
                            </button>
                            <button
                                data-testid={`gen-li-${p.id}`}
                                onClick={() => generate(p.id, "linkedin")}
                                disabled={busy}
                                className="jp-btn inline-flex items-center gap-1 text-sm"
                                style={{ background: "#f9dad0", borderColor: "#c7aea6" }}
                            >
                                <Linkedin size={14} /> LinkedIn
                            </button>
                        </div>
                    </div>
                ))}
                {prospects.length === 0 ? (
                    <div className="font-mono text-xs text-jp-sub">No prospects. Click "Find prospects".</div>
                ) : null}
            </div>

            <h2 className="font-heading text-2xl font-bold mt-8 mb-3">Campaigns for this job</h2>
            <div className="grid grid-cols-1 gap-3">
                {camps.map((c) => (
                    <div key={c.id} className="jp-card p-5" data-testid={`camp-card-${c.id}`}>
                        <div className="flex items-center justify-between gap-3 mb-2">
                            <span className="jp-pill" style={campaignTypeStyle(c.type)}>
                                {c.type}
                            </span>
                            <div className="flex items-center gap-2">
                                <span
                                    className="jp-pill"
                                    style={
                                        c.status === "sent"
                                            ? { background: "#c5dca0", borderColor: "#9db080" }
                                            : { background: "#f5f2b8", borderColor: "#c4c193" }
                                    }
                                >
                                    {c.status}
                                </span>
                                {c.status !== "sent" && c.type !== "cover_letter" ? (
                                    <button
                                        data-testid={`send-${c.id}`}
                                        onClick={() => sendCamp(c.id)}
                                        className="jp-btn inline-flex items-center gap-1 text-sm"
                                        style={{ background: "#a491d3", borderColor: "#8170a9" }}
                                    >
                                        <Send size={14} /> Send
                                    </button>
                                ) : null}
                                {c.type === "email" && c.status === "sent" && !c.followup_done ? (
                                    <button
                                        data-testid={`followup-${c.id}`}
                                        onClick={() => followup(c.id)}
                                        className="jp-btn inline-flex items-center gap-1 text-sm"
                                        style={{ background: "#f9dad0", borderColor: "#c7aea6" }}
                                    >
                                        <Clock size={14} /> Follow-up now
                                    </button>
                                ) : null}
                            </div>
                        </div>
                        {c.subject ? (
                            <div className="font-heading font-semibold">{c.subject}</div>
                        ) : null}
                        <div className="font-mono text-xs whitespace-pre-wrap text-[#1A1A1A]/85 mt-2">
                            {c.body}
                        </div>
                        {c.artifact_url ? (
                            <a
                                href={c.artifact_url}
                                target="_blank"
                                rel="noreferrer"
                                className="font-mono text-xs underline mt-2 inline-block break-all"
                            >
                                stored artifact → {c.artifact_url}
                            </a>
                        ) : null}
                    </div>
                ))}
                {camps.length === 0 ? (
                    <div className="font-mono text-xs text-jp-sub">
                        No campaigns yet. Generate one above.
                    </div>
                ) : null}
            </div>
        </Layout>
    );
}
