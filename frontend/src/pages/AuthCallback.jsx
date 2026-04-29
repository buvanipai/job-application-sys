import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { authSession } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH

// Module-level guard: persists across StrictMode double-mounts in dev so we
// never POST the (single-use) session_id twice.
const PROCESSED = new Set();

export default function AuthCallback() {
    const navigate = useNavigate();
    const { setUser } = useAuth();
    const hasProcessed = useRef(false);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (hasProcessed.current) return;
        hasProcessed.current = true;

        const hash = window.location.hash || "";
        const m = hash.match(/session_id=([^&]+)/);
        if (!m) {
            navigate("/login", { replace: true });
            return;
        }
        const sessionId = decodeURIComponent(m[1]);

        if (PROCESSED.has(sessionId)) {
            // Already processed in this tab — just go to dashboard, AuthProvider will
            // pick up the token from localStorage / cookie.
            window.history.replaceState({}, document.title, window.location.pathname);
            navigate("/dashboard", { replace: true });
            return;
        }
        PROCESSED.add(sessionId);

        (async () => {
            try {
                const user = await authSession(sessionId);
                setUser(user);
                window.history.replaceState({}, document.title, window.location.pathname);
                navigate("/dashboard", { replace: true, state: { user } });
            } catch (e) {
                console.error("auth callback failed", e);
                const msg =
                    e?.response?.data?.detail ||
                    e?.message ||
                    "Authentication failed. Please try again.";
                setError(String(msg));
            }
        })();
    }, [navigate, setUser]);

    if (error) {
        return (
            <div className="min-h-screen bg-[#FDFCF8] text-[#1A1A1A] flex items-center justify-center px-6">
                <div className="jp-card p-8 max-w-md w-full" style={{ background: "#f9dad0", borderColor: "#c7aea6" }}>
                    <div className="font-mono text-[11px] uppercase tracking-wider mb-2">
                        sign-in error
                    </div>
                    <h2 className="font-heading text-2xl font-bold mb-2">Couldn't sign you in</h2>
                    <p data-testid="auth-error" className="font-mono text-xs whitespace-pre-wrap mb-4">
                        {error}
                    </p>
                    <p className="text-sm mb-4 text-[#1A1A1A]/80">
                        This usually happens when the sign-in link expired (it's single-use). Please
                        click the button below to start a new sign-in.
                    </p>
                    <button
                        data-testid="auth-retry-btn"
                        onClick={() => navigate("/login", { replace: true })}
                        className="jp-btn"
                        style={{ background: "#a491d3", borderColor: "#8170a9" }}
                    >
                        Back to login
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div
            data-testid="auth-callback"
            className="min-h-screen flex items-center justify-center font-mono text-sm text-jp-sub"
        >
            signing you in…
        </div>
    );
}
