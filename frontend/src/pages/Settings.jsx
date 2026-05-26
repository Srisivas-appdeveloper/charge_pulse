import { useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { api } from "../api/client";
import { useQuery } from "@tanstack/react-query";
import { chargersApi } from "../api/chargers";

const COMMANDS = ["Reset", "TriggerMessage", "ChangeConfiguration",
                  "RemoteStartTransaction", "RemoteStopTransaction", "GetDiagnostics"];

export default function Settings() {
  const { user, org } = useAuth();
  const { data: chargers } = useQuery({ queryKey: ["chargers-min"], queryFn: () => chargersApi.list({ limit: 200 }) });
  const [cpId, setCpId] = useState("");
  const [command, setCommand] = useState("Reset");
  const [paramsText, setParamsText] = useState('{"type": "Soft"}');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const send = async () => {
    setBusy(true); setResult(null);
    try {
      const params = JSON.parse(paramsText || "{}");
      const r = await api.post(`/chargers/${cpId}/command`, { command, params });
      setResult(r.data);
    } catch (e) {
      setResult({ status: "error", error: e?.response?.data?.detail || e.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-xl font-semibold">Settings</h1>

      <section className="bg-white border rounded-lg p-5 space-y-3">
        <h2 className="font-medium">Organisation</h2>
        <Row k="Name" v={org?.name} />
        <Row k="Email" v={org?.email} />
        <Row k="Plan" v={org?.plan} />
        <Row k="Charger quota" v={org?.max_chargers} />
      </section>

      <section className="bg-white border rounded-lg p-5 space-y-3">
        <h2 className="font-medium">Your account</h2>
        <Row k="Name" v={user?.full_name} />
        <Row k="Email" v={user?.email} />
        <Row k="Role" v={user?.role} />
      </section>

      <section className="bg-white border rounded-lg p-5 space-y-3">
        <h2 className="font-medium">Billing</h2>
        <p className="text-sm text-gray-500">Billing dashboard ships post-MVP. Current plan is included in your subscription.</p>
        <div className="text-xs text-gray-400">Pricing: ₹200/charger/mo (starter) · ₹400 (pro) · ₹500 (enterprise)</div>
      </section>

      <section className="bg-white border rounded-lg p-5 space-y-3">
        <h2 className="font-medium">Send OCPP command</h2>
        <p className="text-xs text-gray-500">
          Sends an OCPP request to a connected charger via the gateway. Useful for triggering a
          Reset on a misbehaving unit or pulling diagnostics on demand.
        </p>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <select className="border rounded px-3 py-2" value={cpId} onChange={(e) => setCpId(e.target.value)}>
            <option value="">Select charger…</option>
            {(chargers?.chargers ?? []).map((c) => (
              <option key={c.cp_id} value={c.cp_id}>{c.cp_id} · {c.status}</option>
            ))}
          </select>
          <select className="border rounded px-3 py-2" value={command} onChange={(e) => setCommand(e.target.value)}>
            {COMMANDS.map((c) => <option key={c}>{c}</option>)}
          </select>
        </div>
        <textarea
          rows={3}
          className="w-full border rounded px-3 py-2 text-sm font-mono"
          value={paramsText} onChange={(e) => setParamsText(e.target.value)}
          placeholder='{"type":"Soft"} or {"requested_message":"StatusNotification"}'
        />
        <button
          disabled={!cpId || busy}
          onClick={send}
          className="px-3 py-1.5 bg-emerald-600 text-white text-sm rounded disabled:opacity-50"
        >
          {busy ? "Sending…" : "Send command"}
        </button>
        {result && (
          <pre className={`text-xs p-3 rounded ${result.status === "ok" ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"} overflow-auto max-h-60`}>
{JSON.stringify(result, null, 2)}
          </pre>
        )}
      </section>
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-gray-500">{k}</span>
      <span>{v ?? "—"}</span>
    </div>
  );
}
