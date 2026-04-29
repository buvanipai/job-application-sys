import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { Resumes } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Star, Trash2 } from "lucide-react";

export default function ResumesPage() {
    const [items, setItems] = useState([]);
    const [name, setName] = useState("");
    const [content, setContent] = useState("");
    const [isDefault, setIsDefault] = useState(true);

    const load = async () => setItems(await Resumes.list());
    useEffect(() => {
        load();
    }, []);

    const create = async () => {
        if (!name.trim() || !content.trim()) {
            toast.error("Fill name and content.");
            return;
        }
        await Resumes.create({ name, content, is_default: isDefault });
        setName("");
        setContent("");
        toast.success("Resume saved.");
        await load();
    };

    const setDefault = async (id) => {
        await Resumes.setDefault(id);
        await load();
    };
    const del = async (id) => {
        await Resumes.del(id);
        await load();
    };

    return (
        <Layout>
            <h1 className="font-heading text-4xl sm:text-5xl font-extrabold tracking-tight">
                Resumes
            </h1>
            <p className="font-mono text-xs uppercase tracking-wider text-jp-sub mt-1 mb-6">
                paste text · default resume is used for scoring + outreach
            </p>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="jp-card p-6 lg:col-span-1" style={{ background: "#f5f2b8", borderColor: "#c4c193" }}>
                    <div className="font-mono text-[11px] uppercase tracking-wider mb-2">
                        new resume
                    </div>
                    <input
                        data-testid="resume-name"
                        className="jp-input"
                        placeholder="Name (e.g., Engineering 2026)"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                    />
                    <textarea
                        data-testid="resume-content"
                        className="jp-input mt-3 min-h-[220px] font-mono text-xs"
                        placeholder="Paste resume text here…"
                        value={content}
                        onChange={(e) => setContent(e.target.value)}
                    />
                    <label className="flex items-center gap-2 mt-3 font-mono text-xs">
                        <input
                            type="checkbox"
                            checked={isDefault}
                            onChange={(e) => setIsDefault(e.target.checked)}
                            data-testid="resume-default-chk"
                        />
                        make default
                    </label>
                    <button
                        data-testid="resume-save-btn"
                        onClick={create}
                        className="jp-btn inline-flex items-center gap-2 mt-4"
                        style={{ background: "#a491d3", borderColor: "#8170a9" }}
                    >
                        <Plus size={16} /> Save resume
                    </button>
                </div>

                <div className="lg:col-span-2 grid grid-cols-1 gap-3">
                    {items.map((r) => (
                        <div key={r.id} className="jp-card p-5" data-testid={`resume-${r.id}`}>
                            <div className="flex items-center justify-between mb-1">
                                <div className="font-heading font-bold">{r.name}</div>
                                <div className="flex gap-2">
                                    {r.is_default ? (
                                        <span
                                            className="jp-pill"
                                            style={{ background: "#c5dca0", borderColor: "#9db080" }}
                                        >
                                            <Star size={12} /> default
                                        </span>
                                    ) : (
                                        <button
                                            data-testid={`resume-default-${r.id}`}
                                            onClick={() => setDefault(r.id)}
                                            className="jp-btn inline-flex items-center gap-1 text-sm"
                                            style={{ background: "#FFFFFF", borderColor: "#E0E0E0" }}
                                        >
                                            <Star size={12} /> make default
                                        </button>
                                    )}
                                    <button
                                        data-testid={`resume-delete-${r.id}`}
                                        onClick={() => del(r.id)}
                                        className="jp-btn inline-flex items-center gap-1 text-sm"
                                        style={{ background: "#FFFFFF", borderColor: "#E0E0E0" }}
                                    >
                                        <Trash2 size={12} />
                                    </button>
                                </div>
                            </div>
                            <pre className="font-mono text-xs whitespace-pre-wrap text-[#1A1A1A]/80 mt-2 line-clamp-6">
                                {r.content}
                            </pre>
                        </div>
                    ))}
                    {items.length === 0 ? (
                        <div className="font-mono text-xs text-jp-sub">
                            No resumes yet. Paste one on the left.
                        </div>
                    ) : null}
                </div>
            </div>
        </Layout>
    );
}
