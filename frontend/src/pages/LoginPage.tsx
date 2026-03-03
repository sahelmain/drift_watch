import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, Mail, Lock, Building2, Loader2 } from "lucide-react";
import { login, register, ApiError } from "@/api";
import { useAuth } from "@/App";

const AUTO_LOGIN_KEY = "dw_demo_auto_login_started_v2";
const DEMO_AUTO_LOGIN_ENABLED =
  import.meta.env.VITE_ENABLE_DEMO_AUTO_LOGIN === "true";
const DEMO_AUTO_LOGIN_EMAIL = import.meta.env.VITE_DEMO_EMAIL ?? "";
const DEMO_AUTO_LOGIN_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD ?? "";
const DEMO_AUTO_LOGIN_ORG = import.meta.env.VITE_DEMO_ORG ?? "";

export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [orgName, setOrgName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { setAuth } = useAuth();

  useEffect(() => {
    if (localStorage.getItem("dw_token")) {
      navigate("/");
      return;
    }
    if (
      !DEMO_AUTO_LOGIN_ENABLED ||
      !DEMO_AUTO_LOGIN_EMAIL ||
      !DEMO_AUTO_LOGIN_PASSWORD ||
      !DEMO_AUTO_LOGIN_ORG
    ) {
      return;
    }
    if (sessionStorage.getItem(AUTO_LOGIN_KEY) === "1") {
      return;
    }

    sessionStorage.setItem(AUTO_LOGIN_KEY, "1");
    setEmail(DEMO_AUTO_LOGIN_EMAIL);
    setPassword(DEMO_AUTO_LOGIN_PASSWORD);
    setOrgName(DEMO_AUTO_LOGIN_ORG);
    setMode("login");

    async function runAutoLogin() {
      setError("");
      setLoading(true);
      try {
        let res;
        try {
          res = await login(DEMO_AUTO_LOGIN_EMAIL, DEMO_AUTO_LOGIN_PASSWORD);
        } catch (err) {
          if (err instanceof ApiError && err.status === 401) {
            await register(
              DEMO_AUTO_LOGIN_EMAIL,
              DEMO_AUTO_LOGIN_PASSWORD,
              DEMO_AUTO_LOGIN_ORG,
            );
            res = await login(DEMO_AUTO_LOGIN_EMAIL, DEMO_AUTO_LOGIN_PASSWORD);
          } else {
            throw err;
          }
        }
        setAuth(res.access_token, res.user);
        navigate("/");
      } catch (err) {
        sessionStorage.removeItem(AUTO_LOGIN_KEY);
        setError(
          err instanceof ApiError
            ? err.message
            : "Auto-login failed. Please sign in manually.",
        );
      } finally {
        setLoading(false);
      }
    }

    void runAutoLogin();
  }, [navigate, setAuth]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res =
        mode === "login"
          ? await login(email, password)
          : await register(email, password, orgName);
      setAuth(res.access_token, res.user);
      navigate("/");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Something went wrong. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-surface-950 flex items-center justify-center p-4">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 -left-32 w-96 h-96 bg-drift-600/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 -right-32 w-96 h-96 bg-drift-500/5 rounded-full blur-3xl" />
      </div>

      <div className="w-full max-w-md relative">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-drift-500 to-drift-700 mb-4">
            <Activity className="text-white" size={28} />
          </div>
          <h1 className="text-2xl font-bold text-white">DriftWatch</h1>
          <p className="text-gray-400 mt-1">LLM Evaluation Drift Tracking</p>
        </div>

        <div className="card p-8">
          <div className="flex mb-6 bg-surface-900 rounded-lg p-1">
            <button
              onClick={() => setMode("login")}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                mode === "login"
                  ? "bg-surface-700 text-white"
                  : "text-gray-400 hover:text-gray-300"
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => setMode("register")}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                mode === "register"
                  ? "bg-surface-700 text-white"
                  : "text-gray-400 hover:text-gray-300"
              }`}
            >
              Register
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm">
                {error}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Email
              </label>
              <div className="relative">
                <Mail
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"
                  size={16}
                />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="input pl-10"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"
                  size={16}
                />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="input pl-10"
                  required
                  minLength={6}
                />
              </div>
            </div>

            {mode === "register" && (
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">
                  Organization Name
                </label>
                <div className="relative">
                  <Building2
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"
                    size={16}
                  />
                  <input
                    type="text"
                    value={orgName}
                    onChange={(e) => setOrgName(e.target.value)}
                    placeholder="Acme Inc."
                    className="input pl-10"
                    required
                  />
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2 py-2.5"
            >
              {loading && <Loader2 size={16} className="animate-spin" />}
              {mode === "login" ? "Sign In" : "Create Account"}
            </button>
          </form>
        </div>

        <p className="text-center text-gray-500 text-xs mt-6">
          Monitor LLM evaluation drift in real time
        </p>
      </div>
    </div>
  );
}
