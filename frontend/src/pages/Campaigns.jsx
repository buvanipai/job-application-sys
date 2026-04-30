import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { Campaigns, Scheduler } from "@/lib/api";
import { toast } from "sonner";
import { Clock, Send, Check, X, AlertTriangle } from "lucide-react";

export const campaignTypeStyle = (type) => {
    if (type === "email") return { background: "#a491d3", borderColor: "#8170a9" };
    if (type === "linkedin") return { background: "#f9dad0", borderColor: "#c7aea6" };
    if (type === "cover_letter") return { background: "#c5dca0", borderColor: "#9db080" };
    if (type === "followup") return { background: "#f9dad0", borderColor: "#c7aea6" };
    return { background: "#f5f2b8", borderColor: "#c4c193" };
};

export default function CampaignsPage() {
    const [items, setItems] = useState([]);
    const [sched, setSched] = useState(null);

    const load = async () => {
        const [c, s] = await Promise.all([Campaigns.list(), Scheduler.status()]);
        setItems(c);
        setSched(s);
    };
    useEffect(() => {
        load();
    }, []);

    const send = async (id) => {
        await Campaigns.send(id);
        toast.success("Sent (mock Gmail).");
        await load();
    };
    const followup = async (id) => {
        try {
            await Campaigns.followup(id);
            toast.success("Follow-up sent.");
            await load();
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Failed.");
        }
    };
    const runSweep = async () => {
        const r = await Scheduler.run();
        toast.success(`Sweep: ${r.processed} follow-ups sent.`);
        await load();
    };
    const markReply = async (c, yes) => {
        const ctx = yes ? window.prompt("Reply context (summary):", c.reply_context || "") : "";
        if (yes && ctx === null) return;
        try {
            await Campaigns.markReply(c.id, { reply_received: yes, reply_context: ctx || "" });
            toast.success(yes ? "Marked as replied." : "Reset to no-reply.");
            await load();
        } catch {
            toast.error("Failed.");
        }
    };

    return (
        <Layout>
            <div className="flex items-start justify-between gap-4 mb-6">
                <div>
                    <h1 className="font-heading text-4xl sm:text-5xl font-extrabold tracking-tight">
                        Campaigns
                    </h1>
                    <p className="font-mono text-xs uppercase tracking-wider text-jp-sub mt-1">
                        sonnet drafts · gmail sends (mock) · auto-followups every{" "}
                        {sched?.followup_after_days ?? 3}d · apply-prompt after{" "}
                        {sched?.apply_after_days ?? 7}d w/ no reply
                    </p>
                </div>
                <button
                    data-testid="camp-run-sweep"
                    onClick={runSweep}
                    className="jp-btn inline-flex items-center gap-2"
                    style={{ background: "#f9dad0", borderColor: "#c7aea6" }}
                >
                    <Clock size={16} /> Run follow-up sweep
                </button>
            </div>

            {sched ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
                    <Mini label="pending followups" value={sched.pending_followups} fill="#f9dad0" border="#c7aea6" />
                    <Mini label="due now" value={sched.due_now} fill="#a491d3" border="#8170a9" />
                    <Mini label="followup days" value={sched.followup_after_days} fill="#f5f2b8" border="#c4c193" />
                    <Mini label="apply-prompt days" value={sched.apply_after_days} fill="#c5dca0" border="#9db080" />
                </div>
            ) : null}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {items.map((c) => (
                    <div key={c.id} className="jp-card p-5" data-testid={`campaign-${c.id}`}>
                        {c.should_apply_prompt ? (
                            <div
                                className="rounded-lg px-3 py-2 mb-3 inline-flex items-center gap-2"
                                style={{ background: "#a491d3", border: "1.5px solid #8170a9" }}
                                data-testid={`apply-prompt-${c.id}`}
                            >
                                <AlertTriangle size={14} />
                                <span className="font-mono text-xs">
                                    No reply — time to apply directly.
                                </span>
                            </div>
                        ) : null}

                        <div className="flex items-center justify-between mb-2">
                            <span className="jp-pill" style={campaignTypeStyle(c.type)}>
                                {c.type}
                            </span>
                            <span
                                className="jp-pill"
                                style={
                                    c.status === "sent"
                                        ? { background: "#c5dca0", borderColor: "#9db080" }
                                        : { background: "#f5f2b8", borderColor: "#c4c193" }
                                }
                            >
                                {c.status}
                                {c.sent_at ? ` · ${new Date(c.sent_at).toLocaleDateString()}` : ""}
                            </span>
                        </div>

                        <div className="font-heading font-bold">{c.subject || "(no subject)"}</div>
                        <div className="font-mono text-xs text-[#1A1A1A]/80 whitespace-pre-wrap mt-2 line-clamp-6">
                            {c.body}
                        </div>

                        {/* Reply tracking */}
                        {c.type === "email" && c.status === "sent" ? (
                            <div
                                className="mt-3 rounded-lg p-3"
                                style={{ background: "#f5f2b8", border: "1.5px solid #c4c193" }}
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <span className="font-mono text-[11px] uppercase tracking-wider">
                                        reply
                                    </span>
                                    <div className="flex gap-2">
                                        <button
                                            data-testid={`reply-yes-${c.id}`}
                                            onClick={() => markReply(c, true)}
                                            className="jp-btn text-sm inline-flex items-center gap-1"
                                            style={
                                                c.reply_received
                                                    ? { background: "#c5dca0", borderColor: "#9db080" }
                                                    : { background: "#FFFFFF", borderColor: "#E0E0E0" }
                                            }
                                        >
                                            <Check size={12} /> replied
                                        </button>
                                        <button
                                            data-testid={`reply-no-${c.id}`}
                                            onClick={() => markReply(c, false)}
                                            className="jp-btn text-sm inline-flex items-center gap-1"
                                            style={{ background: "#FFFFFF", borderColor: "#E0E0E0" }}
                                        >
                                            <X size={12} /> no reply
                                        </button>
                                    </div>
                                </div>
                                {c.reply_received && c.reply_context ? (
                                    <div className="font-mono text-xs mt-2 text-[#1A1A1A]/80 whitespace-pre-wrap">
                                        {c.reply_context}
                                    </div>
                                ) : null}
                            </div>
                        ) : null}

                        <div className="flex gap-2 mt-3 flex-wrap">
                            {c.status !== "sent" && c.type !== "cover_letter" ? (
                                <button
                                    data-testid={`camp-send-${c.id}`}
                                    onClick={() => send(c.id)}
                                    className="jp-btn inline-flex items-center gap-1 text-sm"
                                    style={{ background: "#a491d3", borderColor: "#8170a9" }}
                                >
                                    <Send size={14} /> Send
                                </button>
                            ) : null}
                            {c.type === "email" && c.status === "sent" && !c.followup_done ? (
                                <button
                                    data-testid={`camp-followup-${c.id}`}
                                    onClick={() => followup(c.id)}
                                    className="jp-btn inline-flex items-center gap-1 text-sm"
                                    style={{ background: "#f9dad0", borderColor: "#c7aea6" }}
                                >
                                    <Clock size={14} /> Follow-up now
                                </button>
                            ) : null}
                            {c.followup_done && c.type === "email" ? (
                                <span
                                    className="jp-pill"
                                    style={{ background: "#c5dca0", borderColor: "#9db080" }}
                                >
                                    followup ✓
                                </span>
                            ) : null}
                            {c.artifact_url ? (
                                <a
                                    href={c.artifact_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="jp-btn text-sm"
                                    style={{ background: "#FFFFFF", borderColor: "#E0E0E0" }}
                                >
                                    artifact
                                </a>
                            ) : null}
                        </div>
                    </div>
                ))}
                {items.length === 0 ? (
                    <div className="font-mono text-xs text-jp-sub col-span-2">
                        No campaigns. Open a job and click "Email" on a prospect.
                    </div>
                ) : null}
            </div>
        </Layout>
    );
}

function Mini({ label, value, fill, border }) {
    return (
        <div
            className="rounded-lg p-4"
            style={{ background: fill, border: `1.5px solid ${border}` }}
        >
            <div className="font-mono text-[11px] uppercase tracking-wider opacity-70">{label}</div>
            <div className="font-heading text-2xl font-extrabold mt-1">{value ?? "–"}</div>
        </div>
    );
}
