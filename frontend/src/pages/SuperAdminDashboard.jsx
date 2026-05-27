import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { adminApi } from "../api/admin";
import { useAuth } from "../hooks/useAuth";
import { useNavigate } from "react-router-dom";
import { Building2, Zap, AlertTriangle, TrendingUp, UserCheck, Plus, Trash2, Eye } from "lucide-react";

export default function SuperAdminDashboard() {
  const { startImpersonation } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();

  const [orgName, setOrgName] = useState("");
  const [orgEmail, setOrgEmail] = useState("");
  const [orgPlan, setOrgPlan] = useState("starter");
  const [formErr, setFormErr] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);

  // Queries
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: adminApi.getStats,
  });

  const { data: orgs, isLoading: orgsLoading } = useQuery({
    queryKey: ["admin-orgs"],
    queryFn: adminApi.listOrgs,
  });

  // Mutations
  const createMutation = useMutation({
    mutationFn: adminApi.createOrg,
    onSuccess: () => {
      qc.invalidateQueries(["admin-orgs"]);
      qc.invalidateQueries(["admin-stats"]);
      setOrgName("");
      setOrgEmail("");
      setOrgPlan("starter");
      setModalOpen(false);
    },
    onError: (e) => {
      setFormErr(e?.response?.data?.detail || "Failed to create organisation");
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: adminApi.deactivateOrg,
    onSuccess: () => {
      qc.invalidateQueries(["admin-orgs"]);
      qc.invalidateQueries(["admin-stats"]);
    },
  });

  const impersonateMutation = useMutation({
    mutationFn: adminApi.impersonate,
    onSuccess: (data) => {
      // Save impersonated token and redirect to main dashboard
      startImpersonation(data.access_token);
      nav("/");
    },
  });

  const submitCreate = (e) => {
    e.preventDefault();
    setFormErr(null);
    createMutation.mutate({ name: orgName, email: orgEmail, plan: orgPlan });
  };

  if (statsLoading || orgsLoading) {
    return <div className="text-sm text-gray-500">Loading admin operations…</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">SuperAdmin Dashboard</h1>
          <p className="text-sm text-gray-500">Global ChargePulse platform statistics and client management.</p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg text-sm font-semibold transition-all shadow-sm"
        >
          <Plus size={16} /> New Client Organisation
        </button>
      </div>

      {/* Global stats grids */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          icon={Building2}
          label="Total Organisations"
          value={stats?.total_orgs}
          color="bg-purple-50 text-purple-700 border-purple-100"
        />
        <StatCard
          icon={Zap}
          label="Total Chargers"
          value={stats?.total_chargers}
          color="bg-emerald-50 text-emerald-700 border-emerald-100"
        />
        <StatCard
          icon={AlertTriangle}
          label="Open Incidents"
          value={stats?.total_incidents}
          color="bg-amber-50 text-amber-700 border-amber-100"
        />
        <StatCard
          icon={TrendingUp}
          label="Platform MRR"
          value={`₹${(stats?.mrr || 0).toLocaleString()}`}
          color="bg-indigo-50 text-indigo-700 border-indigo-100"
        />
      </div>

      {/* Organisation Table */}
      <div className="bg-white border border-slate-100 rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-50 flex justify-between items-center bg-slate-50/50">
          <h2 className="font-semibold text-slate-800">Active Clients</h2>
          <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-purple-100 text-purple-800">
            {orgs?.length || 0} orgs
          </span>
        </div>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="bg-slate-50 text-gray-500 font-medium border-b border-slate-100">
              <th className="px-6 py-3">Organisation Name</th>
              <th className="px-6 py-3">Billing Email</th>
              <th className="px-6 py-3">Plan</th>
              <th className="px-6 py-3">Chargers Limit</th>
              <th className="px-6 py-3">Active Chargers</th>
              <th className="px-6 py-3">Status</th>
              <th className="px-6 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(orgs ?? []).map((o) => (
              <tr key={o.id} className="hover:bg-slate-50/40 transition">
                <td className="px-6 py-4 font-medium text-slate-800">{o.name}</td>
                <td className="px-6 py-4 text-gray-500">{o.email}</td>
                <td className="px-6 py-4 capitalize font-semibold text-slate-700">
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    o.plan === "enterprise" ? "bg-indigo-50 text-indigo-700" :
                    o.plan === "pro" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"
                  }`}>{o.plan}</span>
                </td>
                <td className="px-6 py-4 text-slate-600">{o.max_chargers}</td>
                <td className="px-6 py-4 font-semibold text-emerald-600">{o.charger_count}</td>
                <td className="px-6 py-4">
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                    o.is_active ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
                  }`}>
                    {o.is_active ? "Active" : "Suspended"}
                  </span>
                </td>
                <td className="px-6 py-4 text-right flex justify-end gap-2">
                  <button
                    onClick={() => impersonateMutation.mutate(o.id)}
                    disabled={impersonateMutation.isPending || !o.is_active}
                    className="flex items-center gap-1.5 text-xs bg-purple-50 hover:bg-purple-100 text-purple-700 px-3 py-1.5 rounded-md font-semibold border border-purple-100 disabled:opacity-50 transition"
                  >
                    <Eye size={14} /> Impersonate
                  </button>
                  <button
                    onClick={() => {
                      if (confirm(`Are you sure you want to deactivate ${o.name}?`)) {
                        deactivateMutation.mutate(o.id);
                      }
                    }}
                    disabled={!o.is_active || deactivateMutation.isPending}
                    className="flex items-center gap-1.5 text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded-md font-semibold border border-red-100 disabled:opacity-50 transition"
                  >
                    <Trash2 size={14} /> Suspend
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Manual Creation Modal */}
      {modalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl p-6 w-[450px] border border-slate-100 animate-in fade-in zoom-in duration-150">
            <h2 className="text-lg font-bold text-slate-800 mb-2">Create New Client Organisation</h2>
            <p className="text-xs text-gray-400 mb-4">Manually register a corporate charging network client.</p>
            {formErr && <div className="text-sm bg-red-50 text-red-700 p-2.5 rounded-md mb-4">{formErr}</div>}
            <form onSubmit={submitCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1">Organisation Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Statiq Gurugram"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-purple-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1">Billing / Owner Email</label>
                <input
                  type="email"
                  required
                  placeholder="cto@statiq.in"
                  value={orgEmail}
                  onChange={(e) => setOrgEmail(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-purple-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1">Subscription Billing Plan</label>
                <select
                  value={orgPlan}
                  onChange={(e) => setOrgPlan(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-purple-500"
                >
                  <option value="starter">Starter (₹2,500/mo - 100 max)</option>
                  <option value="pro">Pro (₹10,000/mo - 500 max)</option>
                  <option value="enterprise">Enterprise (₹25,000/mo - unlimited)</option>
                </select>
              </div>
              <div className="flex justify-end gap-3 pt-3 border-t mt-4">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 border rounded-lg text-sm text-gray-600 hover:bg-slate-50 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm font-semibold disabled:opacity-50 transition"
                >
                  {createMutation.isPending ? "Creating Org…" : "Confirm & Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className={`p-5 rounded-xl border flex items-center gap-4 ${color} shadow-sm`}>
      <div className="p-3 bg-white rounded-lg shadow-sm border border-slate-50">
        <Icon size={24} />
      </div>
      <div>
        <div className="text-2xl font-bold">{value !== undefined ? value : "—"}</div>
        <div className="text-xs text-gray-400 font-semibold uppercase tracking-wider">{label}</div>
      </div>
    </div>
  );
}
