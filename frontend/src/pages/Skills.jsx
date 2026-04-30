import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { Skills, Jobs } from "@/lib/api";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { Sparkles, RefreshCw, ArrowUpRight } from "lucide-react";

export default function SkillsPage() {
    const [items, setItems] = useState([]);
    const [jobMap, setJobMap] = useState({});
    const [busy, setBusy] = useState(false);
    const navigate = useNavigate();

    const load = async () => {
        const [s, j] = await Promise.all([Skills.list(), Jobs.list()]);
        setItems(s);
        const map = {};
        j.forEach((x) => {
            map[x.id] = x;
        });
        setJobMap(map);
    };
    useEffect(() => {
        load();
    }, []);

    const aggregate = async () => {
        setBusy(true);
        try {
            const r = await Skills.aggregate();
            toast.success(`Aggregated ${r.inserted} skills with project swaps.`);
            await load();
        } catch {
            toast.error("Aggregation failed.");
        } finally {
            setBusy(false);
        }
    };

    return (
        <Layout>
            <div className="flex items-start justify-between gap-4 mb-6">
                <div>
                    <h1 className="font-heading text-4xl sm:text-5xl font-extrabold tracking-tight">
                        Skills
                    </h1>
                    <p className="font-mono text-xs uppercase tracking-wider text-jp-sub mt-1">
                        your upgrading roadmap · gaps aggregated from every scored job
                    </p>
                </div>
                <button
                    data-testid="skills-aggregate-btn"
                    onClick={aggregate}
                    disabled={busy}
                    className="jp-btn inline-flex items-center gap-2"
                    style={{ background: "#a491d3", borderColor: "#8170a9" }}
                >
                    <RefreshCw size={16} /> {busy ? "thinking…" : "Refresh + project swaps"}
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {items.map((s, idx) => (
                    <div key={s.id} className="jp-card p-5" data-testid={`skill-${s.id}`}>
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <span
                                    className="jp-pill"
                                    style={{ background: "#818aa3", borderColor: "#656c82" }}
                                >
                                    #{idx + 1}
                                </span>
                                <div className="font-heading text-lg font-bold capitalize">
                                    {s.skill}
                                </div>
                            </div>
                            <span
                                className="jp-pill"
                                style={{ background: "#f5f2b8", borderColor: "#c4c193" }}
                            >
                                seen {s.frequency}×
                            </span>
                        </div>

                        {s.project_swap_suggestion ? (
                            <div
                                className="rounded-lg p-3 mt-3"
                                style={{ background: "#c5dca0", border: "1.5px solid #9db080" }}
                            >
                                <div className="font-mono text-[11px] uppercase tracking-wider mb-1">
                                    project swap suggestion
                                </div>
                                <div className="text-sm inline-flex items-start gap-2">
                                    <Sparkles size={16} className="mt-0.5 shrink-0" />
                                    <span>{s.project_swap_suggestion}</span>
                                </div>
                            </div>
                        ) : null}

                        <div className="mt-3">
                            <div className="font-mono text-[11px] uppercase tracking-wider text-jp-sub mb-1">
                                jobs demanding this
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                                {(s.job_ids || []).map((jid) => {
                                    const j = jobMap[jid];
                                    return (
                                        <button
                                            key={jid}
                                            data-testid={`skill-job-${jid}`}
                                            onClick={() => navigate(`/jobs/${jid}`)}
                                            className="jp-pill inline-flex items-center gap-1"
                                            style={{ background: "#FFFFFF", borderColor: "#E0E0E0" }}
                                        >
                                            {j ? `${j.company} · ${j.title}` : jid}
                                            <ArrowUpRight size={12} />
                                        </button>
                                    );
                                })}
                                {(s.job_ids || []).length === 0 ? (
                                    <span className="font-mono text-xs text-jp-sub">no jobs linked</span>
                                ) : null}
                            </div>
                        </div>
                    </div>
                ))}
                {items.length === 0 ? (
                    <div className="font-mono text-xs text-jp-sub col-span-2">
                        No skills tracked yet. Score a few jobs, then click "Refresh + project
                        swaps".
                    </div>
                ) : null}
            </div>
        </Layout>
    );
}
