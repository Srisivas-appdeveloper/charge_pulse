import { useQuery } from "@tanstack/react-query";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import { Link } from "react-router-dom";
import { fleetApi } from "../api/fleet";

function pinColor(c) {
  if (c.status === "offline") return "#9ca3af";
  if (c.status === "faulted") return "#ef4444";
  if (c.health_score < 50) return "#ef4444";
  if (c.health_score < 70) return "#f97316";
  if (c.health_score < 90) return "#f59e0b";
  return "#10b981";
}

export default function FleetMap() {
  const { data } = useQuery({ queryKey: ["fleet-map"], queryFn: () => fleetApi.map(), refetchInterval: 30000 });
  const chargers = (data?.chargers ?? []).filter((c) => c.lat != null && c.lng != null);
  const center = chargers[0] ? [chargers[0].lat, chargers[0].lng] : [20.5937, 78.9629];

  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Fleet map</h1>
      {chargers.length === 0 && (
        <div className="bg-white rounded-lg p-5 text-sm text-gray-500">
          No chargers with coordinates yet. Add lat/lng when creating a charger.
        </div>
      )}
      <div className="bg-white rounded-lg overflow-hidden shadow-sm border" style={{ height: "70vh" }}>
        <MapContainer center={center} zoom={5} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
          <TileLayer
            attribution='&copy; OpenStreetMap'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {chargers.map((c) => (
            <CircleMarker
              key={c.cp_id}
              center={[c.lat, c.lng]}
              radius={10}
              pathOptions={{ color: pinColor(c), fillColor: pinColor(c), fillOpacity: 0.7 }}
            >
              <Popup>
                <div className="text-sm">
                  <div className="font-medium">{c.display_name || c.cp_id}</div>
                  <div className="text-xs text-gray-500">{c.city}</div>
                  <div className="text-xs mt-1">
                    Status: <b>{c.status}</b> · Health: <b>{Math.round(c.health_score)}</b>
                  </div>
                  <Link to={`/chargers/${c.cp_id}`} className="text-emerald-600 text-xs">
                    View details →
                  </Link>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}
