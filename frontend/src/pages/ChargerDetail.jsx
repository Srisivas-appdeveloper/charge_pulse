import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { chargersApi } from "../api/chargers";
import HealthBadge from "../components/HealthBadge";
import ChargerStatusDot from "../components/ChargerStatusDot";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";

export default function ChargerDetail() {
  const { cp_id } = useParams();
  const { data: detail } = useQuery({ queryKey: ["charger", cp_id], queryFn: () => chargersApi.get(cp_id) });
  const { data: health } = useQuery({ queryKey: ["charger-health", cp_id], queryFn: () => chargersApi.health(cp_id) });
  const { data: sessions } = useQuery({ queryKey: ["charger-sessions", cp_id], queryFn: () => chargersApi.sessions(cp_id, { limit: 10 }) });
  const { data: telemetry } = useQuery({ queryKey: ["charger-telemetry", cp_id], queryFn: () => chargersApi.telemetry(cp_id, { limit: 30 }) });

  const c = detail?.charger;
  if (!c) return <div className="text-sm text-gray-500">Loading…</div>;

  const chartData = (health?.timeline ?? []).map((p) => ({
    time: new Date(p.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    anomaly: p.anomaly_score ?? 0,
  }));

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 text-sm text-gray-500">
        <Link to="/chargers" className="text-emerald-600">← Chargers</Link>
      </div>
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{c.display_name || c.cp_id}</h1>
          <div className="text-xs text-gray-500 mt-1 font-mono">{c.cp_id}</div>
        </div>
        <div className="flex items-center gap-3">
          <ChargerStatusDot status={c.status} />
          <HealthBadge score={c.health_score} />
        </div>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Meta label="Vendor" value={c.vendor || "—"} />
        <Meta label="Model" value={c.model || "—"} />
        <Meta label="Firmware" value={c.firmware_version || "—"} />
        <Meta label="Connectors" value={c.connector_count} />
        <Meta label="Last boot" value={c.last_boot_at ? new Date(c.last_boot_at).toLocaleString() : "—"} />
        <Meta label="Last heartbeat" value={c.last_heartbeat_at ? new Date(c.last_heartbeat_at).toLocaleString() : "—"} />
        <Meta label="Last session" value={c.last_session_at ? new Date(c.last_session_at).toLocaleString() : "—"} />
        <Meta label="Current anomaly" value={detail?.current_anomaly_score?.toFixed(3) ?? "—"} />
      </div>

      <section className="bg-white rounded-lg shadow-sm border p-5">
        <h2 className="font-medium mb-3">Anomaly timeline (hourly)</h2>
        {chartData.length === 0 ? (
          <p className="text-sm text-gray-500">No feature vectors computed yet for this charger.</p>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line type="monotone" dataKey="anomaly" stroke="#10b981" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </section>

      <div className="grid md:grid-cols-2 gap-5">
        <section className="bg-white rounded-lg shadow-sm border">
          <h2 className="font-medium px-5 py-3 border-b">Recent sessions</h2>
          <ul className="divide-y text-sm">
            {(sessions?.sessions ?? []).slice(0, 8).map((s) => (
              <li key={s.id} className="px-5 py-2 flex justify-between">
                <span className="text-xs text-gray-500">
                  {new Date(s.started_at).toLocaleString()} · {s.id_tag || "anon"}
                </span>
                <span className="text-xs">
                  {(s.energy_kwh ?? 0).toFixed(2)} kWh · {Math.round(s.duration_min ?? 0)}m · {s.stop_reason || "—"}
                </span>
              </li>
            ))}
            {(sessions?.sessions ?? []).length === 0 && (
              <li className="px-5 py-3 text-sm text-gray-500">No sessions.</li>
            )}
          </ul>
        </section>

        <section className="bg-white rounded-lg shadow-sm border">
          <h2 className="font-medium px-5 py-3 border-b">Telemetry (latest 30 events)</h2>
          <ul className="divide-y text-xs max-h-96 overflow-auto">
            {(telemetry?.events ?? []).map((e, i) => (
              <li key={i} className="px-5 py-2 flex justify-between gap-3">
                <span className="text-gray-500 shrink-0">{new Date(e.time).toLocaleTimeString()}</span>
                <span className="font-mono shrink-0">{e.event_type}</span>
                <span className="text-gray-500 truncate">{JSON.stringify(e.payload)}</span>
              </li>
            ))}
            {(telemetry?.events ?? []).length === 0 && (
              <li className="px-5 py-3 text-sm text-gray-500">No telemetry.</li>
            )}
          </ul>
        </section>
      </div>

      <section className="bg-white rounded-lg shadow-sm border">
        <h2 className="font-medium px-5 py-3 border-b">Recent incidents</h2>
        <ul className="divide-y text-sm">
          {(detail?.recent_incidents ?? []).length === 0 && (
            <li className="px-5 py-3 text-sm text-gray-500">No incidents.</li>
          )}
          {(detail?.recent_incidents ?? []).map((i) => (
            <li key={i.id} className="px-5 py-3 flex justify-between">
              <Link to={`/incidents/${i.id}`} className="text-emerald-600">{i.title}</Link>
              <span className="text-xs text-gray-500">
                {i.severity} · {new Date(i.detected_at).toLocaleString()}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Meta({ label, value }) {
  return (
    <div className="bg-white rounded-lg shadow-sm border p-3">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-sm mt-1">{value}</div>
    </div>
  );
}
