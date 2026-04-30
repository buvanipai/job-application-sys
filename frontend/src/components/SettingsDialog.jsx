import { useEffect, useState } from "react";
import { Resumes, Settings } from "@/lib/api";
import { toast } from "sonner";
import { X, Star, Trash2, Save, Copy, Puzzle } from "lucide-react";

export default function SettingsDialog({ open, onClose }) {
    const [resumes, setResumes] = useState([]);
    const [name, setName] = useState("");
    const [content, setContent] = useState("");
    const [isDefault, setIsDefault] = useState(true);
    const [settings, setSettings] = useState({
        followup_days: 3,
        apply_after_days: 7,
        signature: "",
    });
    const [saving, setSaving] = useState(false);

    const loadAll = async () => {
        try {
            const [r, s] = await Promise.all([Resumes.list(), Settings.get()]);
            setResumes(r);
            setSettings({
                followup_days: s.followup_days ?? 3,
                apply_after_days: s.apply_after_days ?? 7,
                signature: s.signature ?? "",
            });
        } catch (e) {
            // silent — dialog still usable
        }
    };

    useEffect(() => {
        if (open) loadAll();
    }, [open]);

    if (!open) return null;

    const saveResume = async () => {
        if (!name.trim() || !content.trim()) {
            toast.error("Fill resume name + content.");
            return;
        }
        await Resumes.create({ name, content, is_default: isDefault });
        setName("");
        setContent("");
        toast.success("Resume saved.");
        await loadAll();
    };

    const saveSettings = async () => {
        setSaving(true);
        try {
            await Settings.update({
                followup_days: Number(settings.followup_days) || 3,
                apply_after_days: Number(settings.apply_after_days) || 7,
                signature: settings.signature || "",
            });
            toast.success("Settings saved.");
        } catch {
            toast.error("Failed to save settings.");
        } finally {
            setSaving(false);
        }
    };

    return (
        <div
            data-testid="settings-dialog"
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30"
            onClick={onClose}
        >
            <div
                className="jp-card w-full max-w-3xl max-h-[90vh] overflow-y-auto p-6"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center justify-between mb-4">
                    <h2 className="font-heading text-2xl font-bold">Settings</h2>
                    <button
                        data-testid="settings-close"
                        onClick={onClose}
                        className="jp-btn"
                        style={{ background: "#FFFFFF", borderColor: "#E0E0E0" }}
                    >
                        <X size={16} />
                    </button>
                </div>

                {/* Browser extension token */}
                <section
                    className="rounded-lg p-4 mb-4"
                    style={{ background: "#a491d3", border: "1.5px solid #8170a9" }}
                >
                    <div className="flex items-center gap-2 mb-2">
                        <Puzzle size={14} />
                        <div className="font-mono text-[11px] uppercase tracking-wider">
                            chrome extension
                        </div>
                    </div>
                    <p className="text-sm mb-3" style={{ color: "var(--jp-ink)" }}>
                        Copy your session token, paste it once into the Talentpath browser
                        extension, and capture any job posting in one click.
                    </p>
                    <button
                        data-testid="copy-extension-token-btn"
                        onClick={async () => {
                            const token = (() => {
                                try {
                                    return localStorage.getItem("jp_session_token") || "";
                                } catch {
                                    return "";
                                }
                            })();
                            if (!token) {
                                toast.error("No session token found. Try logging out and back in.");
                                return;
                            }
                            try {
                                await navigator.clipboard.writeText(token);
                                toast.success("Token copied — paste it into the extension popup.");
                            } catch {
                                window.prompt("Copy this token:", token);
                            }
                        }}
                        className="jp-btn inline-flex items-center gap-2"
                        style={{ background: "#f5f2b8", borderColor: "#c4c193" }}
                    >
                        <Copy size={14} /> Copy extension token
                    </button>
                </section>

                {/* Follow-up config */}
                <section
                    className="rounded-lg p-4 mb-4"
                    style={{ background: "#f9dad0", border: "1.5px solid #c7aea6" }}
                >
                    <div className="font-mono text-[11px] uppercase tracking-wider mb-2">
                        follow-up schedule
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <label className="block">
                            <span className="font-mono text-xs">follow-up after N days</span>
                            <input
                                data-testid="setting-followup-days"
                                type="number"
                                min="1"
                                max="60"
                                value={settings.followup_days}
                                onChange={(e) =>
                                    setSettings((s) => ({ ...s, followup_days: e.target.value }))
                                }
                                className="jp-input mt-1"
                            />
                        </label>
                        <label className="block">
                            <span className="font-mono text-xs">
                                apply-prompt after N days post follow-up (no reply)
                            </span>
                            <input
                                data-testid="setting-apply-days"
                                type="number"
                                min="1"
                                max="60"
                                value={settings.apply_after_days}
                                onChange={(e) =>
                                    setSettings((s) => ({ ...s, apply_after_days: e.target.value }))
                                }
                                className="jp-input mt-1"
                            />
                        </label>
                    </div>
                    <label className="block mt-3">
                        <span className="font-mono text-xs">email signature (optional)</span>
                        <textarea
                            data-testid="setting-signature"
                            value={settings.signature}
                            onChange={(e) => setSettings((s) => ({ ...s, signature: e.target.value }))}
                            className="jp-input mt-1 min-h-[60px] font-mono text-xs"
                            placeholder="— First Last, title, contact"
                        />
                    </label>
                    <button
                        data-testid="save-settings-btn"
                        onClick={saveSettings}
                        disabled={saving}
                        className="jp-btn inline-flex items-center gap-2 mt-3"
                        style={{ background: "#a491d3", borderColor: "#8170a9" }}
                    >
                        <Save size={14} /> {saving ? "saving…" : "Save settings"}
                    </button>
                </section>

                {/* Resumes */}
                <section>
                    <div className="font-mono text-[11px] uppercase tracking-wider mb-2">
                        resumes
                    </div>
                    <div
                        className="rounded-lg p-4 mb-3"
                        style={{ background: "#f5f2b8", border: "1.5px solid #c4c193" }}
                    >
                        <input
                            data-testid="resume-name"
                            className="jp-input"
                            placeholder="Name (e.g., Engineering 2026)"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                        />
                        <textarea
                            data-testid="resume-content"
                            className="jp-input mt-2 min-h-[140px] font-mono text-xs"
                            placeholder="Paste resume text (or LaTeX blocks)…"
                            value={content}
                            onChange={(e) => setContent(e.target.value)}
                        />
                        <label className="flex items-center gap-2 mt-2 font-mono text-xs">
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
                            onClick={saveResume}
                            className="jp-btn mt-3"
                            style={{ background: "#a491d3", borderColor: "#8170a9" }}
                        >
                            Save resume
                        </button>
                    </div>
                    <div className="space-y-2">
                        {resumes.map((r) => (
                            <div
                                key={r.id}
                                className="rounded-lg p-3 flex items-center justify-between"
                                style={{ border: "1.5px solid #E0E0E0" }}
                                data-testid={`resume-${r.id}`}
                            >
                                <div className="min-w-0">
                                    <div className="font-heading font-semibold truncate">{r.name}</div>
                                    <div className="font-mono text-xs text-jp-sub truncate">
                                        {(r.content || "").slice(0, 90)}…
                                    </div>
                                </div>
                                <div className="flex gap-2 ml-3">
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
                                            onClick={async () => {
                                                await Resumes.setDefault(r.id);
                                                loadAll();
                                            }}
                                            className="jp-btn text-sm inline-flex items-center gap-1"
                                            style={{ background: "#FFFFFF", borderColor: "#E0E0E0" }}
                                        >
                                            <Star size={12} /> default
                                        </button>
                                    )}
                                    <button
                                        data-testid={`resume-delete-${r.id}`}
                                        onClick={async () => {
                                            await Resumes.del(r.id);
                                            loadAll();
                                        }}
                                        className="jp-btn text-sm"
                                        style={{ background: "#FFFFFF", borderColor: "#E0E0E0" }}
                                    >
                                        <Trash2 size={12} />
                                    </button>
                                </div>
                            </div>
                        ))}
                        {resumes.length === 0 ? (
                            <div className="font-mono text-xs text-jp-sub">
                                No resumes yet. Paste one above so scoring and outreach have context.
                            </div>
                        ) : null}
                    </div>
                </section>
            </div>
        </div>
    );
}
