import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { authMe, authLogout, getToken } from "@/lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    const check = useCallback(async () => {
        try {
            const me = await authMe();
            setUser(me);
        } catch {
            setUser(null);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        // CRITICAL: If returning from OAuth callback (no token yet), skip the /me check.
        // AuthCallback will exchange the session_id and establish the session first.
        if (window.location.hash?.includes("session_id=") && !getToken()) {
            setLoading(false);
            return;
        }
        check();
    }, [check]);

    const logout = async () => {
        try {
            await authLogout();
        } catch {
            // ignore
        }
        setUser(null);
    };

    return (
        <AuthCtx.Provider value={{ user, setUser, loading, refresh: check, logout }}>
            {children}
        </AuthCtx.Provider>
    );
}

export const useAuth = () => useContext(AuthCtx);
