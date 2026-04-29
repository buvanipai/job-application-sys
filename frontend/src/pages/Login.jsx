import { ArrowRight, Sparkles, Zap } from "lucide-react";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function Login() {
    const startAuth = () => {
        const redirectUrl = window.location.origin + "/dashboard";
        window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
    };

    return (
        <div className="min-h-screen bg-[#FDFCF8] text-[#1A1A1A] flex items-center justify-center px-6">
            <div className="w-full max-w-[1100px] grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Left: marketing */}
                <div className="jp-card p-8 md:p-10" style={{ background: "#f5f2b8", borderColor: "#c4c193" }}>
                    <div className="font-mono text-[11px] uppercase tracking-wider mb-6">
                        jobpath · pipeline os
                    </div>
                    <h1 className="font-heading text-5xl lg:text-6xl font-extrabold leading-[1.02] tracking-tight">
                        Find, score, and
                        <br />
                        reach out —
                        <br />
                        <span style={{ background: "#a491d3", padding: "0 8px", border: "1.5px solid #8170a9", borderRadius: 8 }}>
                            on autopilot.
                        </span>
                    </h1>
                    <p className="mt-6 text-base max-w-md">
                        Scrape job descriptions, score them with Claude Haiku, draft outreach with Sonnet,
                        send, and follow-up automatically. Built for the one-founder job search.
                    </p>
                    <div className="mt-8 grid grid-cols-2 gap-3 max-w-md">
                        <Feature icon={<Sparkles size={16} />} label="Haiku 4.5 scoring" fill="#818aa3" border="#656c82" />
                        <Feature icon={<Zap size={16} />} label="Sonnet 4.5 drafts" fill="#c5dca0" border="#9db080" />
                        <Feature icon={<Sparkles size={16} />} label="Auto follow-ups" fill="#f9dad0" border="#c7aea6" />
                        <Feature icon={<Zap size={16} />} label="Skill gap swaps" fill="#a491d3" border="#8170a9" />
                    </div>
                </div>

                {/* Right: auth card */}
                <div className="jp-card p-8 md:p-10 flex flex-col justify-center">
                    <div className="font-mono text-[11px] uppercase tracking-wider text-jp-sub mb-3">
                        sign in
                    </div>
                    <h2 className="font-heading text-3xl font-bold mb-2">Welcome back</h2>
                    <p className="text-jp-sub mb-8">
                        Continue with your Google account. Sessions last 7 days.
                    </p>
                    <button
                        data-testid="google-login-btn"
                        onClick={startAuth}
                        className="jp-btn w-full inline-flex items-center justify-between"
                        style={{ background: "#a491d3", borderColor: "#8170a9" }}
                    >
                        <span>Continue with Google</span>
                        <ArrowRight size={18} />
                    </button>
                    <div className="mt-6 font-mono text-[11px] text-jp-sub">
                        by continuing, you agree to store anonymized pipeline data in our DB.
                    </div>
                </div>
            </div>
        </div>
    );
}

function Feature({ icon, label, fill, border }) {
    return (
        <div
            className="rounded-lg px-3 py-2 flex items-center gap-2 font-mono text-xs"
            style={{ background: fill, border: `1.5px solid ${border}` }}
        >
            {icon}
            <span>{label}</span>
        </div>
    );
}
