import { useState, useEffect } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { SpeedInsights } from "@vercel/speed-insights/react";
import { useAuth } from "./AuthContext";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import SuitesPage from "./pages/SuitesPage";
import TimelinePage from "./pages/TimelinePage";
import RunDetailPage from "./pages/RunDetailPage";
import AlertsPage from "./pages/AlertsPage";
import SettingsPage from "./pages/SettingsPage";
import RunsPage from "./pages/RunsPage";
import PoliciesPage from "./pages/PoliciesPage";
import { AuthProvider } from "./AuthContext";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Layout>{children}</Layout>;
}

export default function App() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) return null;

  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/*"
          element={
            <RequireAuth>
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/suites" element={<SuitesPage />} />
                <Route path="/runs" element={<RunsPage />} />
                <Route path="/runs/:id" element={<RunDetailPage />} />
                <Route path="/timeline" element={<TimelinePage />} />
                <Route path="/alerts" element={<AlertsPage />} />
                <Route path="/policies" element={<PoliciesPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </RequireAuth>
          }
        />
      </Routes>
      <SpeedInsights />
    </AuthProvider>
  );
}
