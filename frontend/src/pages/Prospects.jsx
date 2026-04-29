import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { Prospects } from "@/lib/api";
import { Users } from "lucide-react";

export default function ProspectsPage() {
    const [items, setItems] = useState([]);
    useEffect(() => {
        Prospects.list().then(setItems);
    }, []);

    return (
        <Layout>
            <h1 className="font-heading text-4xl sm:text-5xl font-extrabold tracking-tight">Prospects</h1>
            <p className="font-mono text-xs uppercase tracking-wider text-jp-sub mt-1 mb-6">
                apify + hunter (mocked) · per job
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {items.map((p) => (
                    <div key={p.id} data-testid={`prospect-${p.id}`} className="jp-card p-5">
                        <div className="flex items-center gap-2 mb-1">
                            <span
                                className="jp-pill"
                                style={{ background: "#818aa3", borderColor: "#656c82" }}
                            >
                                <Users size={12} /> {p.source}
                            </span>
                            {p.confidence ? (
                                <span
                                    className="jp-pill"
                                    style={{ background: "#c5dca0", borderColor: "#9db080" }}
                                >
                                    conf {p.confidence}
                                </span>
                            ) : null}
                        </div>
                        <div className="font-heading font-bold mt-1">{p.name}</div>
                        <div className="font-mono text-xs text-jp-sub">{p.role}</div>
                        <div className="font-mono text-xs mt-2 break-all">{p.email}</div>
                        <div className="font-mono text-[11px] text-jp-sub mt-1">{p.company}</div>
                    </div>
                ))}
                {items.length === 0 ? (
                    <div className="font-mono text-xs text-jp-sub">
                        No prospects yet. Open a job and click "Find prospects".
                    </div>
                ) : null}
            </div>
        </Layout>
    );
}
