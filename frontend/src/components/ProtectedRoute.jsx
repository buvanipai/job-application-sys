import { useAuth } from "@/context/AuthContext";
import { Navigate, useLocation } from "react-router-dom";

export default function ProtectedRoute({ children }) {
    const { user, loading } = useAuth();
    const location = useLocation();

    if (loading) {
        return (
            <div
                data-testid="auth-loading"
                className="min-h-screen flex items-center justify-center font-mono text-sm text-jp-sub"
            >
                loading…
            </div>
        );
    }
    if (!user && !location.state?.user) {
        return <Navigate to="/login" replace />;
    }
    return children;
}
