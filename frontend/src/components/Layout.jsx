import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { useState } from "react";
import {
    Briefcase,
    Users,
    Send,
    Sparkles,
    Building2,
    LogOut,
    Settings as SettingsIcon,
    Sun,
    Moon,
} from "lucide-react";
import SettingsDialog from "@/components/SettingsDialog";

const navItems = [
    { to: "/jobs", label: "Jobs", icon: Briefcase, color: "#f5f2b8", border: "#c4c193" },
    { to: "/prospects", label: "Prospects", icon: Users, color: "#818aa3", border: "#656c82" },
    { to: "/campaigns", label: "Campaigns", icon: Send, color: "#f9dad0", border: "#c7aea6" },
    { to: "/skills", label: "Skills", icon: Sparkles, color: "#c5dca0", border: "#9db080" },
    { to: "/company-research", label: "Company Research", icon: Building2, color: "#a491d3", border: "#8170a9" },
];

export default function Layout({ children }) {
    const { user, logout } = useAuth();
    const { theme, toggle: toggleTheme } = useTheme();
    const navigate = useNavigate();
    const [settingsOpen, setSettingsOpen] = useState(false);

    return (
        <div className="min-h-screen bg-[#FDFCF8] text-[#1A1A1A]">
            <div className="mx-auto max-w-[1400px] px-6 py-6">
                <header className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                        <div
                            data-testid="brand-badge"
                            className="w-9 h-9 rounded-lg flex items-center justify-center font-mono font-bold"
                            style={{ background: "#a491d3", border: "1.5px solid #8170a9" }}
                        >
                            TP
                        </div>
                        <div>
                            <div className="font-heading text-xl font-extrabold tracking-tight">
                                Talentpath
                            </div>
                            <div className="font-mono text-[11px] text-jp-sub uppercase tracking-wider">
                                hub &amp; spoke · every action logged
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <span
                            className="jp-pill hidden sm:inline-flex"
                            style={{ background: "#f5f2b8", borderColor: "#c4c193" }}
                            data-testid="user-email"
                        >
                            {user?.email || "—"}
                        </span>
                        {user?.picture ? (
                            <img
                                src={user.picture}
                                alt=""
                                data-testid="user-avatar"
                                className="w-9 h-9 rounded-lg object-cover"
                                style={{ border: "1.5px solid #E0E0E0" }}
                            />
                        ) : null}
                        <button
                            data-testid="theme-toggle-btn"
                            onClick={toggleTheme}
                            aria-label="Toggle theme"
                            title={theme === "dark" ? "Switch to light" : "Switch to dark"}
                            className="jp-btn inline-flex items-center gap-2"
                            style={{ background: "#ffffff", borderColor: "#E0E0E0" }}
                        >
                            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
                        </button>
                        <button
                            data-testid="settings-btn"
                            onClick={() => setSettingsOpen(true)}
                            className="jp-btn inline-flex items-center gap-2"
                            style={{ background: "#ffffff", borderColor: "#E0E0E0" }}
                        >
                            <SettingsIcon size={16} /> Settings
                        </button>
                        <button
                            data-testid="logout-btn"
                            onClick={async () => {
                                await logout();
                                navigate("/login", { replace: true });
                            }}
                            className="jp-btn"
                            style={{ background: "#ffffff", borderColor: "#E0E0E0" }}
                        >
                            <span className="inline-flex items-center gap-2">
                                <LogOut size={16} /> Logout
                            </span>
                        </button>
                    </div>
                </header>

                <nav className="flex gap-2 overflow-x-auto no-scrollbar mb-6">
                    {navItems.map((n) => (
                        <NavLink
                            key={n.to}
                            to={n.to}
                            data-testid={`nav-${n.label.toLowerCase().replace(/\s+/g, "-")}`}
                            className={({ isActive }) =>
                                `jp-btn inline-flex items-center gap-2 whitespace-nowrap ${
                                    isActive ? "" : "opacity-80"
                                }`
                            }
                            style={{ background: n.color, borderColor: n.border }}
                        >
                            <n.icon size={16} />
                            <span>{n.label}</span>
                        </NavLink>
                    ))}
                </nav>

                <main className="animate-fade-up">{children}</main>

                <footer className="mt-16 pb-6 font-mono text-[11px] text-jp-sub uppercase tracking-wider">
                    talentpath · hub-and-spoke pipeline · mocked integrations
                </footer>
            </div>

            <SettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} />
        </div>
    );
}
