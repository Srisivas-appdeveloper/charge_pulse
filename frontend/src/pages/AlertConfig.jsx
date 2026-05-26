import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { alertsApi } from "../api/alerts";
import { Trash2, Plus } from "lucide-react";

const CHANNELS = ["email", "sms", "whatsapp", "webhook", "slack"];
const SEVS = ["low", "medium", "high", "critical"];

export default function AlertConfig() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["alert-configs"], queryFn: () => alertsApi.list() });
  const [form, setForm] = useState({ channel: "email", endpoint: "", label: "", severity_min: "medium" });
  const create = useMutation({
    mutationFn: (b) => alertsApi.create(b),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["alert-configs"] }); setForm({ channel: "email", endpoint: "", label: "", severity_min: "medium" }); },
  });
  const remove = useMutation({
    mutationFn: (id) => alertsApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alert-configs"] }),
  });
  const toggle = useMutation({
    mutationFn: ({ id, active }) => alertsApi.update(id, { is_active: active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alert-configs"] }),
  });

  return (
    <div className="space-y-5 max-w-3xl">
      <h1 className="text-xl font-semibold">Alert channels</h1>

      <form
        onSubmit={(e) => { e.preventDefault(); create.mutate(form); }}
        className="bg-white border rounded-lg p-4 grid grid-cols-2 gap-3 text-sm"
      >
        <select className="border rounded px-3 py-2" value={form.channel} onChange={(e) => setForm((f) => ({ ...f, channel: e.target.value }))}>
          {CHANNELS.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select className="border rounded px-3 py-2" value={form.severity_min} onChange={(e) => setForm((f) => ({ ...f, severity_min: e.target.value }))}>
          {SEVS.map((s) => <option key={s} value={s}>severity ≥ {s}</option>)}
        </select>
        <input className="border rounded px-3 py-2 col-span-2" placeholder="Endpoint (email / phone / URL)" required value={form.endpoint} onChange={(e) => setForm((f) => ({ ...f, endpoint: e.target.value }))} />
        <input className="border rounded px-3 py-2 col-span-2" placeholder="Label (optional)" value={form.label} onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))} />
        <button disabled={create.isPending} className="col-span-2 inline-flex justify-center items-center gap-1 bg-emerald-600 text-white py-2 rounded disabled:opacity-50">
          <Plus size={16} /> Add channel
        </button>
        {create.error && <div className="col-span-2 text-xs text-red-600">{create.error.response?.data?.detail || "Error"}</div>}
      </form>

      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="text-left p-3">Channel</th>
              <th className="text-left p-3">Endpoint</th>
              <th className="text-left p-3">Label</th>
              <th className="text-left p-3">Severity ≥</th>
              <th className="text-left p-3">Active</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {(data?.configs ?? []).map((c) => (
              <tr key={c.id}>
                <td className="p-3 font-mono text-xs">{c.channel}</td>
                <td className="p-3 text-xs">{c.endpoint}</td>
                <td className="p-3 text-xs text-gray-500">{c.label || "—"}</td>
                <td className="p-3 text-xs">{c.severity_min}</td>
                <td className="p-3">
                  <input type="checkbox" checked={c.is_active} onChange={(e) => toggle.mutate({ id: c.id, active: e.target.checked })} />
                </td>
                <td className="p-3 text-right">
                  <button onClick={() => remove.mutate(c.id)} className="text-gray-400 hover:text-red-600">
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
            {(data?.configs ?? []).length === 0 && (
              <tr><td colSpan={6} className="p-5 text-center text-gray-500">No channels yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
