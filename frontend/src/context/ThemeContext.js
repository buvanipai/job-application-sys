import { createContext, useContext, useEffect, useState, useCallback } from "react";

const ThemeCtx = createContext(null);
const KEY = "jp_theme";

function applyTheme(theme) {
    const root = document.documentElement;
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
}

export function ThemeProvider({ children }) {
    const [theme, setThemeState] = useState(() => {
        try {
            return localStorage.getItem(KEY) || "light";
        } catch {
            return "light";
        }
    });

    useEffect(() => {
        applyTheme(theme);
        try {
            localStorage.setItem(KEY, theme);
        } catch {
            // ignore
        }
    }, [theme]);

    const setTheme = useCallback((t) => setThemeState(t), []);
    const toggle = useCallback(() => setThemeState((t) => (t === "dark" ? "light" : "dark")), []);

    return (
        <ThemeCtx.Provider value={{ theme, setTheme, toggle }}>{children}</ThemeCtx.Provider>
    );
}

export const useTheme = () => useContext(ThemeCtx);
