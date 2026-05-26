import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "../api/analytics";
import { fleetApi } from "../api/fleet";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  LineChart, Line,
} from "recharts";

export default function Analytics() {
  const { data: vendors } = useQuery({ queryKey: ["vendors"], queryFn: () => analyticsApi.vendorComparison() });
  const { data: uptime } = useQuery({ queryKey: ["uptime"], queryFn: () => fleetApi.uptime({ granularity: "daily" }) });
  const { data: predictions } = useQuery({ queryKey: ["predictions"], queryFn: () => analyticsApi.predictions() });

  const uptimeData = (uptime?.timeline ?? []).map((p) => ({
    date: new Date(p.date).toLocaleDateString(),
    uptime: p.uptime_pct,
  }));
  const vendorData = (vendors?.vendors ?? []).map((v) => ({
    name: `${v.vendor}/${v.model}`,
    health: v.avg_health,
    incident_rate: v.incident_rate,
  }));

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-semibold">Analytics</h1>

      <section className="bg-white border rounded-lg p-5">
        <h2 className="font-medium mb-3">Uptime (daily)</h2>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={uptimeData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} />
            <Tooltip />
            <Line type="monotone" dataKey="uptime" stroke="#10b981" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </section>

      <section className="bg-white border rounded-lg p-5">
        <h2 className="font-medium mb-3">Vendor / model health</h2>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={vendorData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="health" fill="#10b981" />
          </BarChart>
        </ResponsiveContainer>
      </section>

      <section className="bg-white border rounded-lg">
        <h2 className="font-medium px-5 py-3 border-b">Predicted failures (lowest health)</h2>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="text-left p-3">Charger</th>
              <th className="text-left p-3">Health</th>
              <th className="text-left p-3">Predicted type</th>
              <th className="text-left p-3">Hours to failure</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {(predictions?.predictions ?? []).map((p) => (
              <tr key={p.cp_id}>
                <td className="p-3 font-mono text-xs">{p.cp_id}</td>
                <td className="p-3 text-xs">{Math.round(p.health_score)}</td>
                <td className="p-3 text-xs text-gray-500">{p.predicted_failure_type || "—"}</td>
                <td className="p-3 text-xs text-gray-500">{p.estimated_hours_to_failure ?? "—"}</td>
              </tr>
            ))}
            {(predictions?.predictions ?? []).length === 0 && (
              <tr><td colSpan={4} className="p-5 text-center text-gray-500">No data yet.</td></tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
