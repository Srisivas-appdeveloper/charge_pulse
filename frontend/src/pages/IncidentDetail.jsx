import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { incidentsApi } from "../api/incidents";

const FAILURE_TYPES = [
  "power_supply", "connector_fault", "communication_loss", "payment_system",
  "firmware_crash", "thermal_overload", "ground_fault", "unknown",
];

export default function IncidentDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { data: i } = useQuery({ queryKey: ["incident", id], queryFn: () => incidentsApi.get(id) });
  const [notes, setNotes] = useState("");
  const [confirmed, setConfirmed] = useState("");

  const acknowledge = useMutation({
    mutationFn: () => incidentsApi.patch(id, { acknowledged_at: new Date().toISOString() }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["incident", id] }),
  });
  const resolve = useMutation({
    mutationFn: () => incidentsApi.patch(id, {
      resolved_at: new Date().toISOString(),
      resolution_notes: notes || null,
      confirmed_failure_type: confirmed || null,
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["incident", id] }),
  });

  if (!i) return <div className="text-sm text-gray-500">Loading…</div>;

  return (
    <div className="space-y-5 max-w-3xl">
      <Link to="/incidents" className="text-sm text-emerald-600">← All incidents</Link>
      <header>
        <h1 className="text-xl font-semibold">{i.title}</h1>
        <div className="text-xs text-gray-500 mt-1">
          <span className="font-mono">{i.cp_id}</span> · {i.severity} · {i.failure_type} ·{" "}
          detected {new Date(i.detected_at).toLocaleString()}
        </div>
      </header>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <Field label="Acknowledged at" value={i.acknowledged_at ? new Date(i.acknowledged_at).toLocaleString() : "—"} />
        <Field label="Resolved at" value={i.resolved_at ? new Date(i.resolved_at).toLocaleString() : "—"} />
        <Field label="Anomaly score" value={i.anomaly_score?.toFixed(3) ?? "—"} />
        <Field label="Auto-detected" value={i.auto_detected ? "Yes" : "No"} />
      </div>

      {i.description && (
        <section className="bg-white rounded-lg border p-4 text-sm">
          <div className="text-xs text-gray-500 uppercase mb-1">Description</div>
          {i.description}
        </section>
      )}

      <section className="bg-white rounded-lg border p-5 space-y-3">
        <h2 className="font-medium">Resolve</h2>
        <textarea
          className="w-full border rounded px-3 py-2 text-sm"
          rows={3} placeholder="Resolution notes (what fixed it?)"
          value={notes} onChange={(e) => setNotes(e.target.value)}
          disabled={!!i.resolved_at}
        />
        <select
          className="w-full border rounded px-3 py-2 text-sm"
          value={confirmed} onChange={(e) => setConfirmed(e.target.value)}
          disabled={!!i.resolved_at}
        >
          <option value="">Confirm failure type (optional, feeds ML training)</option>
          {FAILURE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <div className="flex gap-2">
          {!i.acknowledged_at && !i.resolved_at && (
            <button onClick={() => acknowledge.mutate()} disabled={acknowledge.isPending} className="px-3 py-1.5 text-sm border rounded hover:bg-slate-50">
              Acknowledge
            </button>
          )}
          {!i.resolved_at && (
            <button onClick={() => resolve.mutate()} disabled={resolve.isPending} className="px-3 py-1.5 text-sm bg-emerald-600 text-white rounded disabled:opacity-50">
              Mark resolved
            </button>
          )}
        </div>
      </section>
    </div>
  );
}

function Field({ label, value }) {
  return (
    <div className="bg-white rounded-lg border p-3">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-sm mt-1">{value}</div>
    </div>
  );
}
