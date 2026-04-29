import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { Jobs } from "@/lib/api";
import { useNavigate } from "react-router-dom";
import { Play, Trash2, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { ScoreBadge } from "@/pages/Dashboard";

export default function JobsPage() {
    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(false);
    const [filter, setFilter] = useState("all");
    const navigate = useNavigate();

    const load = async () => {
        const data = await Jobs.list();
        setJobs(data);
    };

    useEffect(() => {
        load();
    }, []);

    const scrape = async () => {
        setLoading(true);
        try {
            const res = await Jobs.scrape(6);
            toast.success(`Scraped ${res.inserted} jobs · ${res.skipped_duplicates} dupes skipped.`);
            await load();
        } catch (e) {
            toast.error("Scrape failed.");
        } finally {
            setLoading(false);
        }
    };

    const del = async (id) => {
        await Jobs.del(id);
        await load();
    };

    const filtered = jobs.filter((j) => {
        if (filter === "high") return j.score >= 70;
        if (filter === "applied") return j.status === "applied";
        if (filter === "new") return j.status === "new";
        return true;
    });

    return (
        <Layout>
            <div className="flex items-start justify-between gap-4 mb-6">
                <div>
                    <h1 className="font-heading text-4xl sm:text-5xl font-extrabold tracking-tight">
                        Jobs
                    </h1>
                    <p className="font-mono text-xs uppercase tracking-wider text-jp-sub mt-1">
                        scraped JDs · scored by Haiku 4.5
                    </p>
                </div>
                <button
                    data-testid="jobs-scrape-btn"
                    onClick={scrape}
                    disabled={loading}
                    className="jp-btn inline-flex items-center gap-2"
                    style={{ background: "#a491d3", borderColor: "#8170a9" }}
                >
                    <Play size={16} />
                    {loading ? "scraping…" : "Scrape more"}
                </button>
            </div>

            <div className="flex gap-2 mb-4">
                {[
                    { k: "all", l: "All" },
                    { k: "high", l: "High match (≥70)" },
                    { k: "new", l: "New" },
                    { k: "applied", l: "Applied" },
                ].map((f) => (
                    <button
                        key={f.k}
                        data-testid={`filter-${f.k}`}
                        onClick={() => setFilter(f.k)}
                        className="jp-btn"
                        style={{
                            background: filter === f.k ? "#f5f2b8" : "#ffffff",
                            borderColor: filter === f.k ? "#c4c193" : "#E0E0E0",
                        }}
                    >
                        {f.l}
                    </button>
                ))}
            </div>

            <div className="jp-card overflow-hidden">
                <table className="w-full">
                    <thead>
                        <tr className="font-mono text-[11px] uppercase tracking-wider text-jp-sub">
                            <th className="text-left p-3" style={{ borderBottom: "1.5px solid #E0E0E0" }}>Score</th>
                            <th className="text-left p-3" style={{ borderBottom: "1.5px solid #E0E0E0" }}>Role</th>
                            <th className="text-left p-3" style={{ borderBottom: "1.5px solid #E0E0E0" }}>Company</th>
                            <th className="text-left p-3" style={{ borderBottom: "1.5px solid #E0E0E0" }}>Status</th>
                            <th className="text-left p-3" style={{ borderBottom: "1.5px solid #E0E0E0" }}>Match reason</th>
                            <th className="p-3" style={{ borderBottom: "1.5px solid #E0E0E0" }}></th>
                        </tr>
                    </thead>
                    <tbody>
                        {filtered.map((j) => (
                            <tr
                                key={j.id}
                                data-testid={`job-row-${j.id}`}
                                className="transition-colors hover:bg-black/5 cursor-pointer"
                                onClick={() => navigate(`/jobs/${j.id}`)}
                            >
                                <td className="p-3" style={{ borderBottom: "1.5px solid #F0F0F0" }}>
                                    <ScoreBadge score={j.score} />
                                </td>
                                <td className="p-3 font-heading font-semibold" style={{ borderBottom: "1.5px solid #F0F0F0" }}>
                                    {j.title}
                                </td>
                                <td className="p-3 font-mono text-sm" style={{ borderBottom: "1.5px solid #F0F0F0" }}>
                                    {j.company}
                                </td>
                                <td className="p-3" style={{ borderBottom: "1.5px solid #F0F0F0" }}>
                                    <span
                                        className="jp-pill"
                                        style={
                                            j.status === "applied"
                                                ? { background: "#c5dca0", borderColor: "#9db080" }
                                                : j.status === "archived"
                                                    ? { background: "#FFFFFF", borderColor: "#E0E0E0" }
                                                    : { background: "#f5f2b8", borderColor: "#c4c193" }
                                        }
                                    >
                                        {j.status}
                                    </span>
                                </td>
                                <td className="p-3 text-sm text-jp-sub max-w-[340px] truncate" style={{ borderBottom: "1.5px solid #F0F0F0" }}>
                                    {j.match_reason}
                                </td>
                                <td className="p-3 text-right" style={{ borderBottom: "1.5px solid #F0F0F0" }}>
                                    <div className="inline-flex items-center gap-2">
                                        {j.url ? (
                                            <a
                                                href={j.url}
                                                target="_blank"
                                                rel="noreferrer"
                                                onClick={(e) => e.stopPropagation()}
                                                className="jp-btn inline-flex items-center gap-1"
                                                style={{ background: "#FFFFFF", borderColor: "#E0E0E0" }}
                                                data-testid={`open-url-${j.id}`}
                                            >
                                                <ExternalLink size={14} />
                                            </a>
                                        ) : null}
                                        <button
                                            data-testid={`delete-job-${j.id}`}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                del(j.id);
                                            }}
                                            className="jp-btn inline-flex items-center gap-1"
                                            style={{ background: "#FFFFFF", borderColor: "#E0E0E0" }}
                                        >
                                            <Trash2 size={14} />
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        ))}
                        {filtered.length === 0 ? (
                            <tr>
                                <td colSpan={6} className="p-8 text-center font-mono text-xs text-jp-sub">
                                    No jobs. Click "Scrape more" above.
                                </td>
                            </tr>
                        ) : null}
                    </tbody>
                </table>
            </div>
        </Layout>
    );
}
