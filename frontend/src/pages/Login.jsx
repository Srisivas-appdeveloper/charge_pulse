import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { Zap } from "lucide-react";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    if (e) e.preventDefault();
    setErr(null); setBusy(true);
    try {
      const res = await login(email, password);
      // If superadmin, redirect to /admin. Else redirect to /dashboard (or "/")
      if (res?.user?.role === "superadmin") {
        nav("/admin");
      } else {
        nav("/");
      }
    }
    catch (ex) { setErr(ex?.response?.data?.detail || "Login failed"); }
    finally { setBusy(false); }
  };

  const handleUseCredentials = async (demoEmail, demoPassword) => {
    setEmail(demoEmail);
    setPassword(demoPassword);
    setErr(null);
    setBusy(true);
    try {
      const res = await login(demoEmail, demoPassword);
      if (res?.user?.role === "superadmin") {
        nav("/admin");
      } else {
        nav("/");
      }
    } catch (ex) {
      setErr(ex?.response?.data?.detail || "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="h-full flex flex-col items-center justify-center bg-slate-900 gap-4">
      <form onSubmit={submit} className="bg-white p-8 rounded-lg shadow-xl w-96 space-y-4">
        <div className="flex items-center gap-2 text-2xl font-bold">
          <Zap className="text-emerald-500" /> ChargePulse
        </div>
        <p className="text-sm text-gray-500">Sign in to your CPO dashboard.</p>
        {err && <div className="text-sm bg-red-50 text-red-700 p-2 rounded">{err}</div>}
        <input
          type="email" value={email} onChange={(e) => setEmail(e.target.value)}
          placeholder="Email" required
          className="w-full border rounded px-3 py-2 text-sm"
        />
        <input
          type="password" value={password} onChange={(e) => setPassword(e.target.value)}
          placeholder="Password" required
          className="w-full border rounded px-3 py-2 text-sm"
        />
        <button
          disabled={busy}
          className="w-full bg-emerald-600 hover:bg-emerald-700 text-white py-2 rounded text-sm font-medium disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="text-xs text-gray-500 text-center">
          No account? <Link to="/register" className="text-emerald-600">Register</Link>
        </p>
      </form>

      {import.meta.env.VITE_APP_ENV === 'development' && (
        <div className="bg-slate-800 text-slate-100 p-6 rounded-lg shadow-xl w-96 border border-slate-700 space-y-4">
          <div className="flex items-center gap-2 text-lg font-semibold text-emerald-400">
            <span>🧪</span> Demo Credentials
          </div>
          
          <div className="space-y-3 text-sm">
            <div className="bg-slate-900/60 p-3 rounded border border-slate-700/50 flex justify-between items-center">
              <div>
                <div className="font-semibold text-slate-300">Platform Admin</div>
                <div className="text-xs text-slate-400 select-all">saravanan@chargepulse.in</div>
                <div className="text-xs text-slate-400 select-all font-mono text-emerald-400/90">chargepulse123</div>
              </div>
              <button
                type="button"
                onClick={() => handleUseCredentials("saravanan@chargepulse.in", "chargepulse123")}
                className="bg-emerald-600/20 hover:bg-emerald-600 text-emerald-300 hover:text-white px-3 py-1.5 rounded text-xs font-medium transition-all duration-200 border border-emerald-500/30 active:scale-95"
              >
                Use this
              </button>
            </div>

            <div className="bg-slate-900/60 p-3 rounded border border-slate-700/50 flex justify-between items-center">
              <div>
                <div className="font-semibold text-slate-300">CPO Owner</div>
                <div className="text-xs text-slate-400 select-all">admin@demo.in</div>
                <div className="text-xs text-slate-400 select-all font-mono text-emerald-400/90">supersecret</div>
              </div>
              <button
                type="button"
                onClick={() => handleUseCredentials("admin@demo.in", "supersecret")}
                className="bg-emerald-600/20 hover:bg-emerald-600 text-emerald-300 hover:text-white px-3 py-1.5 rounded text-xs font-medium transition-all duration-200 border border-emerald-500/30 active:scale-95"
              >
                Use this
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
