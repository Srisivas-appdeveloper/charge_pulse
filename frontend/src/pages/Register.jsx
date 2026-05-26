import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { Zap } from "lucide-react";

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({
    org_name: "", email: "", password: "", full_name: "",
  });
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault(); setErr(null); setBusy(true);
    try { await register(form); nav("/"); }
    catch (ex) { setErr(ex?.response?.data?.detail || "Registration failed"); }
    finally { setBusy(false); }
  };

  const upd = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className="h-full flex items-center justify-center bg-slate-900">
      <form onSubmit={submit} className="bg-white p-8 rounded-lg shadow-xl w-96 space-y-3">
        <div className="flex items-center gap-2 text-2xl font-bold">
          <Zap className="text-emerald-500" /> Create org
        </div>
        {err && <div className="text-sm bg-red-50 text-red-700 p-2 rounded">{err}</div>}
        <input className="w-full border rounded px-3 py-2 text-sm" placeholder="Organisation name" value={form.org_name} onChange={upd("org_name")} required />
        <input className="w-full border rounded px-3 py-2 text-sm" placeholder="Your full name" value={form.full_name} onChange={upd("full_name")} required />
        <input className="w-full border rounded px-3 py-2 text-sm" type="email" placeholder="Email" value={form.email} onChange={upd("email")} required />
        <input className="w-full border rounded px-3 py-2 text-sm" type="password" placeholder="Password (min 8 chars)" value={form.password} onChange={upd("password")} minLength={8} required />
        <button disabled={busy} className="w-full bg-emerald-600 hover:bg-emerald-700 text-white py-2 rounded text-sm font-medium disabled:opacity-50">
          {busy ? "Creating…" : "Register"}
        </button>
        <p className="text-xs text-gray-500 text-center">
          Already have an account? <Link to="/login" className="text-emerald-600">Sign in</Link>
        </p>
      </form>
    </div>
  );
}
