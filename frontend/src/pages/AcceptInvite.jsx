import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { authApi } from "../api/auth";
import { Zap } from "lucide-react";

export default function AcceptInvite() {
  const { startImpersonation } = useAuth();
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const nav = useNavigate();

  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr(null);
    if (!token) {
      setErr("Invitation token is missing. Please check your link.");
      return;
    }
    if (password !== confirmPassword) {
      setErr("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setErr("Password must be at least 8 characters long.");
      return;
    }

    setBusy(true);
    try {
      const data = await authApi.acceptInvite({
        token,
        full_name: fullName,
        password,
      });
      // Save token and trigger login state
      startImpersonation(data.access_token);
      nav("/");
    } catch (ex) {
      setErr(ex?.response?.data?.detail || "Invitation acceptance failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="h-full flex items-center justify-center bg-slate-900">
      <form onSubmit={submit} className="bg-white p-8 rounded-lg shadow-xl w-96 space-y-4">
        <div className="flex items-center gap-2 text-2xl font-bold">
          <Zap className="text-emerald-500" /> ChargePulse
        </div>
        <p className="text-sm text-gray-500">Complete your invitation profile.</p>
        
        {err && <div className="text-sm bg-red-50 text-red-700 p-2 rounded">{err}</div>}
        
        <input
          type="text"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          placeholder="Full Name"
          required
          className="w-full border rounded px-3 py-2 text-sm focus:outline-emerald-500"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password (min 8 characters)"
          required
          className="w-full border rounded px-3 py-2 text-sm focus:outline-emerald-500"
        />
        <input
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          placeholder="Confirm Password"
          required
          className="w-full border rounded px-3 py-2 text-sm focus:outline-emerald-500"
        />
        
        <button
          disabled={busy || !token}
          className="w-full bg-emerald-600 hover:bg-emerald-700 text-white py-2 rounded text-sm font-medium disabled:opacity-50 transition-all"
        >
          {busy ? "Accepting Invite…" : "Accept Invitation"}
        </button>
      </form>
    </div>
  );
}
