import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import type { User } from "./types";
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

interface AuthContextValue {
  user: User | null;
  token: string | null;
  setAuth: (token: string, user: User) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  token: null,
  setAuth: () => {},
  logout: () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem("dw_token"),
  );
  const [user, setUser] = useState<User | null>(() => {
    const raw = localStorage.getItem("dw_user");
    return raw ? JSON.parse(raw) : null;
  });

  const setAuth = useCallback((newToken: string, newUser: User) => {
    localStorage.setItem("dw_token", newToken);
    localStorage.setItem("dw_user", JSON.stringify(newUser));
    setToken(newToken);
    setUser(newUser);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("dw_token");
    localStorage.removeItem("dw_user");
    sessionStorage.removeItem("dw_demo_auto_login_started_v2");
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, setAuth, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

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
    </AuthProvider>
  );
}
