import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Download } from "lucide-react";
import { incidentsApi } from "../api/incidents";

const SEVERITY_COLORS = {
  low: "bg-gray-100 text-gray-700",
  medium: "bg-amber-100 text-amber-700",
  high: "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-700",
};

function downloadCsv(rows) {
  if (!rows.length) return;
  const cols = ["id", "cp_id", "severity", "failure_type", "title", "anomaly_score",
                "detected_at", "acknowledged_at", "resolved_at", "resolution_notes",
                "confirmed_failure_type"];
  const escape = (v) => {
    if (v == null) return "";
    const s = String(v).replace(/"/g, '""');
    return /[",\n]/.test(s) ? `"${s}"` : s;
  };
  const csv = [cols.join(","), ...rows.map((r) => cols.map((c) => escape(r[c])).join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `incidents-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click(); URL.revokeObjectURL(url);
}

export default function Incidents() {
  const [filters, setFilters] = useState({ severity: "", resolved: "" });
  const params = {
    ...(filters.severity && { severity: filters.severity }),
    ...(filters.resolved !== "" && { resolved: filters.resolved === "true" }),
    limit: 200,
  };
  const { data, isLoading } = useQuery({
    queryKey: ["incidents", params],
    queryFn: () => incidentsApi.list(params),
    refetchInterval: 15000,
  });
  const rows = data?.incidents ?? [];

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Incidents</h1>
        <button onClick={() => downloadCsv(rows)} disabled={!rows.length} className="inline-flex items-center gap-1 px-3 py-1.5 border rounded text-sm hover:bg-slate-50 disabled:opacity-50">
          <Download size={14} /> Export CSV
        </button>
      </header>

      <div className="flex gap-3 text-sm">
        <select className="border rounded px-2 py-1" value={filters.severity} onChange={(e) => setFilters((f) => ({ ...f, severity: e.target.value }))}>
          <option value="">All severities</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="critical">Critical</option>
        </select>
        <select className="border rounded px-2 py-1" value={filters.resolved} onChange={(e) => setFilters((f) => ({ ...f, resolved: e.target.value }))}>
          <option value="">Open + resolved</option>
          <option value="false">Open only</option>
          <option value="true">Resolved only</option>
        </select>
        <span className="text-xs text-gray-500 self-center">{data?.total ?? 0} total</span>
      </div>

      <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="text-left p-3">Severity</th>
              <th className="text-left p-3">Title</th>
              <th className="text-left p-3">Charger</th>
              <th className="text-left p-3">Type</th>
              <th className="text-left p-3">Detected</th>
              <th className="text-left p-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((i) => (
              <tr key={i.id} className="hover:bg-slate-50">
                <td className="p-3"><span className={`text-xs px-2 py-0.5 rounded ${SEVERITY_COLORS[i.severity]}`}>{i.severity}</span></td>
                <td className="p-3"><Link to={`/incidents/${i.id}`} className="text-emerald-600">{i.title}</Link></td>
                <td className="p-3 font-mono text-xs">{i.cp_id}</td>
                <td className="p-3 text-xs text-gray-500">{i.failure_type}</td>
                <td className="p-3 text-xs text-gray-500">{new Date(i.detected_at).toLocaleString()}</td>
                <td className="p-3 text-xs">
                  {i.resolved_at ? <span className="text-emerald-600">Resolved</span> : <span className="text-orange-600">Open</span>}
                </td>
              </tr>
            ))}
            {!isLoading && rows.length === 0 && (
              <tr><td colSpan={6} className="p-8 text-center text-gray-500">
                {filters.severity || filters.resolved ? "No incidents match your filters." : "No incidents — your fleet is healthy."}
              </td></tr>
            )}
            {isLoading && <tr><td colSpan={6} className="p-8 text-center text-gray-400">Loading…</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
