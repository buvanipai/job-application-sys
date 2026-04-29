import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { authSession } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function AuthCallback() {
    const navigate = useNavigate();
    const { setUser } = useAuth();
    const hasProcessed = useRef(false);

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
        (async () => {
            try {
                const user = await authSession(sessionId);
                setUser(user);
                // Remove hash
                window.history.replaceState({}, document.title, window.location.pathname);
                navigate("/dashboard", { replace: true, state: { user } });
            } catch (e) {
                console.error("auth callback failed", e);
                navigate("/login", { replace: true });
            }
        })();
    }, [navigate, setUser]);

    return (
        <div
            data-testid="auth-callback"
            className="min-h-screen flex items-center justify-center font-mono text-sm text-jp-sub"
        >
            signing you in…
        </div>
    );
}
