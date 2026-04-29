import { ChevronRight } from "lucide-react";

const stages = [
    { key: "scrape", label: "Scrape JDs", sub: "Playwright (mocked)", fill: "#f5f2b8", border: "#c4c193" },
    { key: "score", label: "Score", sub: "Claude Haiku 4.5", fill: "#818aa3", border: "#656c82" },
    { key: "db", label: "Insert jobs", sub: "Mongo → jobs", fill: "#c5dca0", border: "#9db080" },
    { key: "skills", label: "Skills & gaps", sub: "Aggregate + swaps", fill: "#a491d3", border: "#8170a9" },
    { key: "prospects", label: "Prospects", sub: "Apify + Hunter (mock)", fill: "#f5f2b8", border: "#c4c193" },
    { key: "write", label: "Write outreach", sub: "Claude Sonnet 4.5", fill: "#818aa3", border: "#656c82" },
    { key: "send", label: "Send email", sub: "Gmail SMTP (mock)", fill: "#c5dca0", border: "#9db080" },
    { key: "followup", label: "Follow-up", sub: "APScheduler (3d)", fill: "#f9dad0", border: "#c7aea6" },
];

export default function PipelineFlow({ counts = {} }) {
    return (
        <div
            data-testid="pipeline-flow"
            className="jp-card p-5 overflow-x-auto no-scrollbar"
        >
            <div className="flex items-center gap-2 min-w-[900px]">
                {stages.map((s, i) => {
                    const count = counts[s.key];
                    return (
                        <div key={s.key} className="flex items-center gap-2">
                            <div
                                data-testid={`stage-${s.key}`}
                                className="rounded-lg px-4 py-3 min-w-[140px]"
                                style={{ background: s.fill, border: `1.5px solid ${s.border}` }}
                            >
                                <div className="font-mono text-[10px] uppercase tracking-wider opacity-70">
                                    stage {i + 1}
                                </div>
                                <div className="font-heading text-sm font-bold leading-tight mt-0.5">
                                    {s.label}
                                </div>
                                <div className="font-mono text-[11px] mt-1 text-[#1A1A1A]/70">
                                    {s.sub}
                                </div>
                                {count !== undefined ? (
                                    <div className="font-mono text-lg font-bold mt-2">{count}</div>
                                ) : null}
                            </div>
                            {i < stages.length - 1 ? (
                                <ChevronRight size={16} className="text-[#1A1A1A]/50 shrink-0" />
                            ) : null}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
