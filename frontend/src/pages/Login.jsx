import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { Zap } from "lucide-react";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("admin@demo.in");
  const [password, setPassword] = useState("supersecret");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault(); setErr(null); setBusy(true);
    try { await login(email, password); nav("/"); }
    catch (ex) { setErr(ex?.response?.data?.detail || "Login failed"); }
    finally { setBusy(false); }
  };

  return (
    <div className="h-full flex items-center justify-center bg-slate-900">
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
    </div>
  );
}
