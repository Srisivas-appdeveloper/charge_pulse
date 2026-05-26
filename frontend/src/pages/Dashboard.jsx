import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { fleetApi } from "../api/fleet";
import { incidentsApi } from "../api/incidents";
import { AlertTriangle, Battery, Zap, Activity } from "lucide-react";
import HealthBadge from "../components/HealthBadge";

function Card({ label, value, sub, icon: Icon, tone = "slate" }) {
  const tones = {
    slate: "bg-slate-100 text-slate-600",
    green: "bg-emerald-100 text-emerald-700",
    red: "bg-red-100 text-red-700",
    amber: "bg-amber-100 text-amber-700",
  };
  return (
    <div className="bg-white rounded-lg p-5 shadow-sm border border-slate-100">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wide">{label}</div>
          <div className="text-2xl font-semibold mt-1">{value}</div>
          {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
        </div>
        {Icon && (
          <div className={`p-2 rounded-md ${tones[tone]}`}>
            <Icon size={18} />
          </div>
        )}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { data: overview } = useQuery({
    queryKey: ["fleet-overview"],
    queryFn: () => fleetApi.overview(),
    refetchInterval: 15000,
  });
  const { data: recent } = useQuery({
    queryKey: ["incidents-recent"],
    queryFn: () => incidentsApi.list({ limit: 10 }),
    refetchInterval: 15000,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Fleet overview</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card label="Total chargers" value={overview?.total_chargers ?? "–"} icon={Zap} />
        <Card label="Online" value={overview?.online ?? "–"} sub={`${overview?.offline ?? 0} offline · ${overview?.faulted ?? 0} faulted`} icon={Activity} tone="green" />
        <Card label="Avg health" value={Math.round(overview?.avg_health_score ?? 0)} sub={`Uptime 7d: ${Math.round(overview?.avg_uptime_7d ?? 0)}%`} icon={Battery} tone="green" />
        <Card label="Open incidents" value={overview?.open_incidents ?? 0} sub={`${overview?.critical_incidents ?? 0} critical`} icon={AlertTriangle} tone={overview?.critical_incidents > 0 ? "red" : "slate"} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card label="Sessions today" value={overview?.sessions_today ?? 0} icon={Zap} />
        <Card label="Energy today" value={`${(overview?.energy_today_kwh ?? 0).toFixed(1)} kWh`} icon={Battery} tone="amber" />
      </div>

      <section className="bg-white rounded-lg shadow-sm border border-slate-100">
        <header className="flex items-center justify-between px-5 py-3 border-b">
          <h2 className="font-medium">Recent incidents</h2>
          <Link to="/incidents" className="text-xs text-emerald-600">View all →</Link>
        </header>
        <ul className="divide-y">
          {(recent?.incidents ?? []).length === 0 && (
            <li className="p-5 text-sm text-gray-500">No incidents yet — your fleet is healthy.</li>
          )}
          {recent?.incidents?.map((i) => (
            <li key={i.id} className="px-5 py-3 flex items-center justify-between hover:bg-slate-50">
              <div>
                <Link to={`/incidents/${i.id}`} className="text-sm font-medium hover:text-emerald-600">
                  {i.title}
                </Link>
                <div className="text-xs text-gray-500 mt-0.5">
                  <span className="font-mono">{i.cp_id}</span> · {i.failure_type} ·{" "}
                  {new Date(i.detected_at).toLocaleString()}
                </div>
              </div>
              <SeverityPill sev={i.severity} />
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function SeverityPill({ sev }) {
  const colors = {
    low: "bg-gray-100 text-gray-700",
    medium: "bg-amber-100 text-amber-700",
    high: "bg-orange-100 text-orange-700",
    critical: "bg-red-100 text-red-700",
  };
  return <span className={`text-xs px-2 py-0.5 rounded ${colors[sev]}`}>{sev}</span>;
}
