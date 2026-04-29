import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { Skills } from "@/lib/api";
import { toast } from "sonner";
import { Sparkles, RefreshCw } from "lucide-react";

export default function SkillsPage() {
    const [items, setItems] = useState([]);
    const [busy, setBusy] = useState(false);

    const load = async () => setItems(await Skills.list());
    useEffect(() => {
        load();
    }, []);

    const aggregate = async () => {
        setBusy(true);
        try {
            const r = await Skills.aggregate();
            toast.success(`Aggregated ${r.inserted} skills.`);
            await load();
        } catch (e) {
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
                        Skills & gaps
                    </h1>
                    <p className="font-mono text-xs uppercase tracking-wider text-jp-sub mt-1">
                        aggregated from job gaps · Haiku project-swap suggestions
                    </p>
                </div>
                <button
                    data-testid="skills-aggregate-btn"
                    onClick={aggregate}
                    disabled={busy}
                    className="jp-btn inline-flex items-center gap-2"
                    style={{ background: "#a491d3", borderColor: "#8170a9" }}
                >
                    <RefreshCw size={16} /> {busy ? "thinking…" : "Refresh skills"}
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {items.map((s) => (
                    <div key={s.id} className="jp-card p-5" data-testid={`skill-${s.id}`}>
                        <div className="flex items-center justify-between">
                            <div className="font-heading text-lg font-bold capitalize">{s.skill}</div>
                            <span
                                className="jp-pill"
                                style={{ background: "#f5f2b8", borderColor: "#c4c193" }}
                            >
                                seen {s.frequency}×
                            </span>
                        </div>
                        <div
                            className="rounded-lg p-3 mt-3"
                            style={{ background: "#c5dca0", border: "1.5px solid #9db080" }}
                        >
                            <div className="font-mono text-[11px] uppercase tracking-wider mb-1">
                                project swap
                            </div>
                            <div className="text-sm inline-flex items-start gap-2">
                                <Sparkles size={16} className="mt-0.5 shrink-0" />
                                <span>{s.project_swap_suggestion || "—"}</span>
                            </div>
                        </div>
                    </div>
                ))}
                {items.length === 0 ? (
                    <div className="font-mono text-xs text-jp-sub">
                        No skills tracked yet. Click "Refresh skills" after you have scored a few
                        jobs.
                    </div>
                ) : null}
            </div>
        </Layout>
    );
}
