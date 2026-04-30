import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { Jobs } from "@/lib/api";
import { Building2, Sparkles, RefreshCw, MessageSquare } from "lucide-react";
import { toast } from "sonner";

export default function CompanyResearch() {
    const [jobs, setJobs] = useState([]);
    const [activeId, setActiveId] = useState(null);
    const [busy, setBusy] = useState(false);

    const load = async () => {
        const list = await Jobs.list();
        setJobs(list);
        if (!activeId && list.length) setActiveId(list[0].id);
    };
    useEffect(() => {
        load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const active = jobs.find((j) => j.id === activeId);

    const fetchContext = async () => {
        if (!active) return;
        setBusy(true);
        try {
            const { company_context } = await Jobs.research(active.id);
            setJobs((js) => js.map((j) => (j.id === active.id ? { ...j, company_context } : j)));
            toast.success("Company context refreshed.");
        } catch {
            toast.error("Research failed.");
        } finally {
            setBusy(false);
        }
    };

    const generateQas = async () => {
        if (!active) return;
        setBusy(true);
        try {
            const { interview_answers, company_context } = await Jobs.interviewAnswers(active.id);
            setJobs((js) =>
                js.map((j) =>
                    j.id === active.id
                        ? { ...j, interview_answers, company_context: company_context || j.company_context }
                        : j
                )
            );
            toast.success("Interview answers drafted (Sonnet).");
        } catch {
            toast.error("Generation failed.");
        } finally {
            setBusy(false);
        }
    };

    return (
        <Layout>
            <div className="mb-6">
                <h1 className="font-heading text-4xl sm:text-5xl font-extrabold tracking-tight">
                    Company Research
                </h1>
                <p className="font-mono text-xs uppercase tracking-wider text-jp-sub mt-1">
                    optional per job · feeds cover letter + interview answers
                </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-[280px,1fr] gap-4">
                <aside className="jp-card p-3 max-h-[70vh] overflow-y-auto">
                    <div className="font-mono text-[11px] uppercase tracking-wider text-jp-sub px-2 py-1">
                        jobs
                    </div>
                    {jobs.map((j) => (
                        <button
                            key={j.id}
                            data-testid={`cr-select-${j.id}`}
                            onClick={() => setActiveId(j.id)}
                            className="w-full text-left rounded-lg p-3 mt-1 transition-colors"
                            style={
                                j.id === activeId
                                    ? { background: "#a491d3", border: "1.5px solid #8170a9" }
                                    : { background: "#FFFFFF", border: "1.5px solid #E0E0E0" }
                            }
                        >
                            <div className="font-heading font-semibold text-sm truncate">{j.title}</div>
                            <div className="font-mono text-xs text-jp-sub truncate">
                                {j.company}
                            </div>
                            {j.company_context ? (
                                <div
                                    className="jp-pill mt-1"
                                    style={{ background: "#c5dca0", borderColor: "#9db080" }}
                                >
                                    researched
                                </div>
                            ) : null}
                        </button>
                    ))}
                    {jobs.length === 0 ? (
                        <div className="font-mono text-xs text-jp-sub p-3">
                            No jobs yet. Add some in the Jobs tab first.
                        </div>
                    ) : null}
                </aside>

                <section>
                    {active ? (
                        <div className="space-y-4">
                            <div className="jp-card p-6" style={{ background: "#f5f2b8", borderColor: "#c4c193" }}>
                                <div className="flex items-start justify-between gap-3">
                                    <div>
                                        <div className="font-mono text-[11px] uppercase tracking-wider mb-1">
                                            target
                                        </div>
                                        <h2 className="font-heading text-2xl font-bold">
                                            {active.company}
                                        </h2>
                                        <div className="font-mono text-xs">{active.title}</div>
                                    </div>
                                    <button
                                        data-testid="cr-fetch-btn"
                                        onClick={fetchContext}
                                        disabled={busy}
                                        className="jp-btn inline-flex items-center gap-2"
                                        style={{ background: "#818aa3", borderColor: "#656c82" }}
                                    >
                                        <RefreshCw size={14} />
                                        {active.company_context ? "Refresh research" : "Fetch research"}
                                    </button>
                                </div>
                            </div>

                            <div className="jp-card p-6">
                                <div className="flex items-center gap-2 mb-2">
                                    <Building2 size={16} />
                                    <h3 className="font-heading text-lg font-bold">Vision / mission</h3>
                                </div>
                                <p className="text-sm whitespace-pre-wrap">
                                    {active.company_context ||
                                        "No context yet. Click \"Fetch research\" to populate."}
                                </p>
                            </div>

                            <div className="jp-card p-6" style={{ background: "#c5dca0", borderColor: "#9db080" }}>
                                <div className="flex items-center justify-between gap-3 mb-3">
                                    <div className="flex items-center gap-2">
                                        <MessageSquare size={16} />
                                        <h3 className="font-heading text-lg font-bold">
                                            Suggested interview Q&amp;A
                                        </h3>
                                    </div>
                                    <button
                                        data-testid="cr-interview-btn"
                                        onClick={generateQas}
                                        disabled={busy}
                                        className="jp-btn inline-flex items-center gap-2"
                                        style={{ background: "#a491d3", borderColor: "#8170a9" }}
                                    >
                                        <Sparkles size={14} />
                                        {busy ? "thinking…" : "Generate (Sonnet)"}
                                    </button>
                                </div>
                                {(active.interview_answers || []).length === 0 ? (
                                    <div className="font-mono text-xs">
                                        No answers yet. Click <b>Generate</b> — uses the company
                                        context + JD + your default resume.
                                    </div>
                                ) : (
                                    <div className="space-y-3">
                                        {(active.interview_answers || []).map((qa, i) => (
                                            <div
                                                key={i}
                                                className="rounded-lg p-3 bg-white"
                                                style={{ border: "1.5px solid #E0E0E0" }}
                                                data-testid={`qa-${i}`}
                                            >
                                                <div className="font-heading font-semibold">
                                                    Q. {qa.q}
                                                </div>
                                                <div className="font-mono text-xs text-[#1A1A1A]/85 mt-1 whitespace-pre-wrap">
                                                    A. {qa.a}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    ) : (
                        <div className="jp-card p-10 text-center font-mono text-sm text-jp-sub">
                            Select a job on the left.
                        </div>
                    )}
                </section>
            </div>
        </Layout>
    );
}
