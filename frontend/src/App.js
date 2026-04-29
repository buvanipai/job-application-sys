import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import Login from "@/pages/Login";
import AuthCallback from "@/pages/AuthCallback";
import Dashboard from "@/pages/Dashboard";
import Jobs from "@/pages/Jobs";
import JobDetail from "@/pages/JobDetail";
import Prospects from "@/pages/Prospects";
import Campaigns from "@/pages/Campaigns";
import Skills from "@/pages/Skills";
import Resumes from "@/pages/Resumes";
import { Toaster } from "sonner";

function RouterRoot() {
    const location = useLocation();
    // Synchronously catch oauth callback
    if (location.hash?.includes("session_id=")) {
        return <AuthCallback />;
    }
    return (
        <Routes>
            <Route path="/" element={<Login />} />
            <Route path="/login" element={<Login />} />
            <Route
                path="/dashboard"
                element={
                    <ProtectedRoute>
                        <Dashboard />
                    </ProtectedRoute>
                }
            />
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
                path="/resumes"
                element={
                    <ProtectedRoute>
                        <Resumes />
                    </ProtectedRoute>
                }
            />
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
