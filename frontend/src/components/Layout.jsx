import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
    LayoutDashboard,
    Briefcase,
    Users,
    Send,
    Sparkles,
    FileText,
    LogOut,
    CircleDot,
} from "lucide-react";

const navItems = [
    { to: "/dashboard", label: "Pipeline", icon: LayoutDashboard, color: "#a491d3", border: "#8170a9" },
    { to: "/jobs", label: "Jobs", icon: Briefcase, color: "#f5f2b8", border: "#c4c193" },
    { to: "/prospects", label: "Prospects", icon: Users, color: "#818aa3", border: "#656c82" },
    { to: "/campaigns", label: "Campaigns", icon: Send, color: "#f9dad0", border: "#c7aea6" },
    { to: "/skills", label: "Skills", icon: Sparkles, color: "#c5dca0", border: "#9db080" },
    { to: "/resumes", label: "Resumes", icon: FileText, color: "#FFFFFF", border: "#E0E0E0" },
];

export default function Layout({ children }) {
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    return (
        <div className="min-h-screen bg-[#FDFCF8] text-[#1A1A1A]">
            <div className="mx-auto max-w-[1400px] px-6 py-6">
                {/* Header */}
                <header className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                        <div
                            data-testid="brand-badge"
                            className="w-9 h-9 rounded-lg flex items-center justify-center font-mono font-bold"
                            style={{ background: "#a491d3", border: "1.5px solid #8170a9" }}
                        >
                            JP
                        </div>
                        <div>
                            <div className="font-heading text-xl font-extrabold tracking-tight">
                                Jobpath
                            </div>
                            <div className="font-mono text-[11px] text-jp-sub uppercase tracking-wider">
                                Pipeline OS
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="jp-pill" style={{ background: "#f5f2b8", borderColor: "#c4c193" }}>
                            <CircleDot size={12} />
                            <span data-testid="user-email">{user?.email}</span>
                        </div>
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

                {/* Nav */}
                <nav className="flex gap-2 overflow-x-auto no-scrollbar mb-6">
                    {navItems.map((n) => (
                        <NavLink
                            key={n.to}
                            to={n.to}
                            data-testid={`nav-${n.label.toLowerCase()}`}
                            className={({ isActive }) =>
                                `jp-btn inline-flex items-center gap-2 whitespace-nowrap ${
                                    isActive ? "" : "opacity-80"
                                }`
                            }
                            style={({ isActive } = {}) => ({
                                background: n.color,
                                borderColor: n.border,
                                outline: "none",
                            })}
                        >
                            <n.icon size={16} />
                            <span>{n.label}</span>
                        </NavLink>
                    ))}
                </nav>

                <main className="animate-fade-up">{children}</main>

                <footer className="mt-16 pb-6 font-mono text-[11px] text-jp-sub uppercase tracking-wider">
                    jobpath · flat pastel utility · mocked integrations enabled
                </footer>
            </div>
        </div>
    );
}
