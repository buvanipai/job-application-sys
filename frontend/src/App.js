import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation, Navigate } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import Login from "@/pages/Login";
import AuthCallback from "@/pages/AuthCallback";
import Jobs from "@/pages/Jobs";
import JobDetail from "@/pages/JobDetail";
import Prospects from "@/pages/Prospects";
import Campaigns from "@/pages/Campaigns";
import Skills from "@/pages/Skills";
import CompanyResearch from "@/pages/CompanyResearch";
import { Toaster } from "sonner";

function RouterRoot() {
    const location = useLocation();
    if (location.hash?.includes("session_id=")) {
        return <AuthCallback />;
    }
    return (
        <Routes>
            <Route path="/" element={<Login />} />
            <Route path="/login" element={<Login />} />
            <Route
                path="/jobs"
                element={
                    <ProtectedRoute>
                        <Jobs />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/jobs/:id"
                element={
                    <ProtectedRoute>
                        <JobDetail />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/prospects"
                element={
                    <ProtectedRoute>
                        <Prospects />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/campaigns"
                element={
                    <ProtectedRoute>
                        <Campaigns />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/skills"
                element={
                    <ProtectedRoute>
                        <Skills />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/company-research"
                element={
                    <ProtectedRoute>
                        <CompanyResearch />
                    </ProtectedRoute>
                }
            />
            {/* Legacy routes → redirect to Jobs (hub landing) */}
            <Route path="/dashboard" element={<Navigate to="/jobs" replace />} />
            <Route path="/resumes" element={<Navigate to="/jobs" replace />} />
        </Routes>
    );
}

export default function App() {
    return (
        <div className="App">
            <BrowserRouter>
                <AuthProvider>
                    <RouterRoot />
                    <Toaster position="top-right" />
                </AuthProvider>
            </BrowserRouter>
        </div>
    );
}
