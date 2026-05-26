import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { chargersApi } from "../api/chargers";
import HealthBadge from "../components/HealthBadge";
import ChargerStatusDot from "../components/ChargerStatusDot";
import { Plus, Search } from "lucide-react";

const STATUSES = ["", "online", "offline", "faulted"];

export default function Chargers() {
  const [showNew, setShowNew] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["chargers", statusFilter],
    queryFn: () => chargersApi.list({ limit: 200, ...(statusFilter && { status: statusFilter }) }),
  });
  const create = useMutation({
    mutationFn: (body) => chargersApi.create(body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["chargers"] }); setShowNew(false); },
  });

  const filtered = useMemo(() => {
    const all = data?.chargers ?? [];
    if (!search) return all;
    const q = search.toLowerCase();
    return all.filter((c) =>
      c.cp_id.toLowerCase().includes(q) ||
      (c.display_name || "").toLowerCase().includes(q) ||
      (c.vendor || "").toLowerCase().includes(q) ||
      (c.city || "").toLowerCase().includes(q),
    );
  }, [data, search]);

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Chargers</h1>
        <button onClick={() => setShowNew(true)} className="inline-flex items-center gap-1 px-3 py-1.5 bg-emerald-600 text-white text-sm rounded hover:bg-emerald-700">
          <Plus size={16} /> Add
        </button>
      </header>

      <div className="flex gap-3 items-center">
        <div className="relative flex-1 max-w-sm">
          <Search size={14} className="absolute left-2.5 top-2.5 text-gray-400" />
          <input
            placeholder="Search cp_id, name, vendor, city…"
            className="w-full pl-8 pr-3 py-1.5 border rounded text-sm"
            value={search} onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select className="border rounded px-2 py-1.5 text-sm" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          {STATUSES.map((s) => <option key={s} value={s}>{s || "all statuses"}</option>)}
        </select>
        <span className="text-xs text-gray-500">{filtered.length} of {data?.total ?? 0}</span>
      </div>

      <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="text-left p-3">CP ID</th>
              <th className="text-left p-3">Name</th>
              <th className="text-left p-3">Vendor</th>
              <th className="text-left p-3">Status</th>
              <th className="text-left p-3">Health</th>
              <th className="text-left p-3">Last heartbeat</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {filtered.map((c) => (
              <tr key={c.cp_id} className="hover:bg-slate-50">
                <td className="p-3 font-mono text-xs">
                  <Link to={`/chargers/${c.cp_id}`} className="text-emerald-600">{c.cp_id}</Link>
                </td>
                <td className="p-3">{c.display_name || "—"}</td>
                <td className="p-3 text-gray-500">{c.vendor || "—"}</td>
                <td className="p-3"><ChargerStatusDot status={c.status} /></td>
                <td className="p-3"><HealthBadge score={c.health_score} /></td>
                <td className="p-3 text-xs text-gray-500">
                  {c.last_heartbeat_at ? new Date(c.last_heartbeat_at).toLocaleString() : "never"}
                </td>
              </tr>
            ))}
            {!isLoading && filtered.length === 0 && (
              <tr><td colSpan={6} className="p-8 text-center text-gray-500">
                {search || statusFilter ? "No chargers match your filters." : "No chargers yet — click Add to register one."}
              </td></tr>
            )}
            {isLoading && (
              <tr><td colSpan={6} className="p-8 text-center text-gray-400">Loading…</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showNew && <NewChargerModal onClose={() => setShowNew(false)} onCreate={(b) => create.mutate(b)} busy={create.isPending} err={create.error?.response?.data?.detail} />}
    </div>
  );
}

function NewChargerModal({ onClose, onCreate, busy, err }) {
  const [form, setForm] = useState({ cp_id: "", display_name: "", vendor: "", lat: "", lng: "", city: "" });
  const upd = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const submit = (e) => {
    e.preventDefault();
    onCreate({
      cp_id: form.cp_id,
      display_name: form.display_name || null,
      vendor: form.vendor || null,
      city: form.city || null,
      lat: form.lat ? parseFloat(form.lat) : null,
      lng: form.lng ? parseFloat(form.lng) : null,
    });
  };
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center" onClick={onClose}>
      <form onClick={(e) => e.stopPropagation()} onSubmit={submit} className="bg-white rounded-lg p-6 w-96 space-y-3">
        <h2 className="font-semibold">Add charger</h2>
        {err && <div className="bg-red-50 text-red-700 text-xs p-2 rounded">{err}</div>}
        <input className="w-full border rounded px-3 py-2 text-sm" required placeholder="CP ID (e.g. CP-CHN-001)" value={form.cp_id} onChange={upd("cp_id")} />
        <input className="w-full border rounded px-3 py-2 text-sm" placeholder="Display name" value={form.display_name} onChange={upd("display_name")} />
        <input className="w-full border rounded px-3 py-2 text-sm" placeholder="Vendor (Delta / ABB / …)" value={form.vendor} onChange={upd("vendor")} />
        <input className="w-full border rounded px-3 py-2 text-sm" placeholder="City" value={form.city} onChange={upd("city")} />
        <div className="grid grid-cols-2 gap-2">
          <input className="border rounded px-3 py-2 text-sm" placeholder="Latitude" value={form.lat} onChange={upd("lat")} />
          <input className="border rounded px-3 py-2 text-sm" placeholder="Longitude" value={form.lng} onChange={upd("lng")} />
        </div>
        <div className="flex gap-2 justify-end pt-2">
          <button type="button" onClick={onClose} className="px-3 py-1.5 text-sm">Cancel</button>
          <button disabled={busy} className="px-3 py-1.5 text-sm bg-emerald-600 text-white rounded disabled:opacity-50">
            {busy ? "Creating…" : "Create"}
          </button>
        </div>
      </form>
    </div>
  );
}
