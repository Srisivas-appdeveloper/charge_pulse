import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { api } from "../api/client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { chargersApi } from "../api/chargers";
import { usersApi } from "../api/users";
import { authApi } from "../api/auth";
import { User, ShieldAlert, Key, Zap, CreditCard, UserPlus, Trash, Shield } from "lucide-react";

const COMMANDS = ["Reset", "TriggerMessage", "ChangeConfiguration",
                  "RemoteStartTransaction", "RemoteStopTransaction", "GetDiagnostics"];

export default function Settings() {
  const { user, org, impersonating } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState("profile");

  // Copy toast state
  const [toastMsg, setToastMsg] = useState(null);
  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    setToastMsg("Copied to clipboard!");
    setTimeout(() => setToastMsg(null), 2000);
  };

  // OCPP command state
  const { data: chargers } = useQuery({ queryKey: ["chargers-min"], queryFn: () => chargersApi.list({ limit: 200 }) });
  const [cpId, setCpId] = useState("");
  const [command, setCommand] = useState("Reset");
  const [paramsText, setParamsText] = useState('{"type": "Soft"}');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  // Profile update state
  const [profileName, setProfileName] = useState(user?.full_name || "");
  const [profilePassword, setProfilePassword] = useState("");
  const [profileConfirmPassword, setProfileConfirmPassword] = useState("");
  const [profileMsg, setProfileMsg] = useState(null);
  const [profileErr, setProfileErr] = useState(null);
  const [profileBusy, setProfileBusy] = useState(false);

  // User management state
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [inviteMsg, setInviteMsg] = useState(null);
  const [inviteErr, setInviteErr] = useState(null);
  const [inviteBusy, setInviteBusy] = useState(false);
  const [inviteModalOpen, setInviteModalOpen] = useState(false);

  const { data: teamUsers, isLoading: teamLoading } = useQuery({
    queryKey: ["team-users"],
    queryFn: usersApi.listUsers,
    enabled: user?.role === "owner" || user?.role === "admin",
  });

  const sendCommand = async () => {
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

  const updateProfileSubmit = async (e) => {
    e.preventDefault();
    setProfileMsg(null);
    setProfileErr(null);

    if (profilePassword && profilePassword !== profileConfirmPassword) {
      setProfileErr("Passwords do not match.");
      return;
    }

    setProfileBusy(true);
    try {
      const payload = { full_name: profileName };
      if (profilePassword) payload.password = profilePassword;
      await authApi.updateProfile(payload);
      setProfileMsg("Profile updated successfully!");
      setProfilePassword("");
      setProfileConfirmPassword("");
    } catch (ex) {
      setProfileErr(ex?.response?.data?.detail || "Failed to update profile.");
    } finally {
      setProfileBusy(false);
    }
  };

  const inviteUserSubmit = async (e) => {
    e.preventDefault();
    setInviteMsg(null);
    setInviteErr(null);
    setInviteBusy(true);
    try {
      await usersApi.inviteUser({ email: inviteEmail, role: inviteRole });
      setInviteMsg(`Invitation sent successfully to ${inviteEmail}!`);
      setInviteEmail("");
      setInviteRole("member");
      setInviteModalOpen(false);
      qc.invalidateQueries(["team-users"]);
    } catch (ex) {
      setInviteErr(ex?.response?.data?.detail || "Failed to send invitation.");
    } finally {
      setInviteBusy(false);
    }
  };

  const deleteUserMutation = useMutation({
    mutationFn: usersApi.deleteUser,
    onSuccess: () => {
      qc.invalidateQueries(["team-users"]);
    },
  });

  const changeRoleMutation = useMutation({
    mutationFn: ({ id, role }) => usersApi.updateRole(id, role),
    onSuccess: () => {
      qc.invalidateQueries(["team-users"]);
    },
  });

  const isOwnerOrAdmin = user?.role === "owner" || user?.role === "admin";
  const isSuperadminNotImpersonating = user?.role === "superadmin" && !impersonating;

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Settings</h1>
        <p className="text-sm text-gray-500">Configure your profile, billing, team, and OCPP gateway settings.</p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 gap-6">
        <TabButton id="profile" active={activeTab} onClick={setActiveTab} label="My Profile" icon={User} />
        {!isSuperadminNotImpersonating && isOwnerOrAdmin && (
          <TabButton id="team" active={activeTab} onClick={setActiveTab} label="User Management" icon={Shield} />
        )}
        {!isSuperadminNotImpersonating && (
          <TabButton id="commands" active={activeTab} onClick={setActiveTab} label="OCPP Commands" icon={Zap} />
        )}
        {!isSuperadminNotImpersonating && (
          <TabButton id="billing" active={activeTab} onClick={setActiveTab} label="Billing Plan" icon={CreditCard} />
        )}
      </div>

      {/* Profile Tab */}
      {activeTab === "profile" && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 bg-white border border-slate-100 rounded-xl shadow-sm p-6 space-y-4">
            <h2 className="font-semibold text-slate-800 text-lg flex items-center gap-2">
              <Key size={18} className="text-emerald-500" /> Account Settings
            </h2>
            {profileMsg && <div className="text-sm bg-emerald-50 text-emerald-700 p-2.5 rounded-md font-semibold">{profileMsg}</div>}
            {profileErr && <div className="text-sm bg-red-50 text-red-700 p-2.5 rounded-md">{profileErr}</div>}
            <form onSubmit={updateProfileSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1">Full Name</label>
                <input
                  type="text"
                  required
                  value={profileName}
                  onChange={(e) => setProfileName(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-emerald-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-500 mb-1">Change Password</label>
                  <input
                    type="password"
                    placeholder="New password"
                    value={profilePassword}
                    onChange={(e) => setProfilePassword(e.target.value)}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-500 mb-1">Confirm New Password</label>
                  <input
                    type="password"
                    placeholder="Confirm new password"
                    value={profileConfirmPassword}
                    onChange={(e) => setProfileConfirmPassword(e.target.value)}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-emerald-500"
                  />
                </div>
              </div>
              <button
                type="submit"
                disabled={profileBusy}
                className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold px-4 py-2 rounded-lg text-sm transition-all disabled:opacity-50"
              >
                {profileBusy ? "Saving changes…" : "Save Changes"}
              </button>
            </form>
          </div>
          <div className="bg-white border border-slate-100 rounded-xl shadow-sm p-6 space-y-4 h-fit">
            <h2 className="font-semibold text-slate-800 text-lg">Current Membership</h2>
            <div className="space-y-3">
              <Row k="Organisation" v={org?.name || "Platform Administration"} />
              <Row k="Role" v={user?.role} />
              <Row k="Plan" v={org?.plan || "Platform Admin Plan"} />
              <Row k="Client Email" v={user?.email} />
            </div>
          </div>
        </div>
      )}

      {/* User Management Tab */}
      {activeTab === "team" && isOwnerOrAdmin && (
        <div className="bg-white border border-slate-100 rounded-xl shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-50 flex justify-between items-center bg-slate-50/50">
            <div>
              <h2 className="font-semibold text-slate-800 text-lg">Team Members</h2>
              <p className="text-xs text-gray-400">Invite ops managers, field technicians, and stakeholders to your organization.</p>
            </div>
            <button
              onClick={() => setInviteModalOpen(true)}
              className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg text-sm font-semibold transition shadow-sm"
            >
              <UserPlus size={16} /> Invite Member
            </button>
          </div>
          {inviteMsg && <div className="mx-6 mt-4 text-sm bg-emerald-50 text-emerald-700 p-2.5 rounded-md font-semibold">{inviteMsg}</div>}
          
          {teamLoading ? (
            <div className="p-6 text-sm text-gray-500">Loading team members…</div>
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="bg-slate-50 text-gray-500 font-medium border-b border-slate-100">
                  <th className="px-6 py-3">User</th>
                  <th className="px-6 py-3">Role</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Last Active</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(teamUsers ?? []).map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50/40 transition">
                    <td className="px-6 py-4">
                      <div className="font-medium text-slate-800">{u.full_name}</div>
                      <div className="text-xs text-gray-400">{u.email}</div>
                    </td>
                    <td className="px-6 py-4">
                      {user?.role === "owner" && u.id !== user?.id ? (
                        <select
                          value={u.role}
                          onChange={(e) => changeRoleMutation.mutate({ id: u.id, role: e.target.value })}
                          className="border rounded-md px-2 py-1 text-xs focus:outline-emerald-500"
                        >
                          <option value="admin">Admin</option>
                          <option value="member">Member</option>
                          <option value="viewer">Viewer</option>
                        </select>
                      ) : (
                        <span className="capitalize px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-700">
                          {u.role}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                        u.is_active ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                      }`}>
                        {u.is_active ? "Active" : "Pending Invite"}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-gray-500 text-xs">
                      {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "—"}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {user?.role === "owner" && u.id !== user?.id && (
                        <button
                          onClick={() => {
                            if (confirm(`Are you sure you want to remove ${u.full_name}?`)) {
                              deleteUserMutation.mutate(u.id);
                            }
                          }}
                          className="text-red-600 hover:text-red-800 p-1.5 hover:bg-red-50 rounded-md transition"
                        >
                          <Trash size={16} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* OCPP Command Tab */}
      {activeTab === "commands" && !isSuperadminNotImpersonating && (
        <div className="space-y-6">
          {/* OCPP Gateway Connection Info */}
          {user?.role === "owner" && (
            <div className="bg-emerald-50/40 border border-emerald-100/70 rounded-xl p-6 text-slate-800 space-y-4 shadow-sm">
              <h3 className="font-bold text-emerald-800 text-base flex items-center gap-2">
                🔗 Your OCPP Gateway URL
              </h3>
              
              <div className="bg-slate-950 text-slate-100 p-4 rounded-lg font-mono text-base font-semibold relative select-all flex justify-between items-center border border-slate-850">
                <span>wss://csms.chargepulse.in/ocpp/{"{charger_id}"}</span>
                <button 
                  onClick={() => handleCopy("wss://csms.chargepulse.in/ocpp/{charger_id}")}
                  className="text-xs bg-slate-900 hover:bg-slate-850 text-emerald-400 hover:text-emerald-300 px-3 py-1.5 rounded transition border border-slate-800 font-semibold"
                >
                  Copy
                </button>
              </div>
              
              <p className="text-xs text-emerald-800 leading-tight">
                Replace <code className="bg-emerald-100/80 px-1.5 py-0.5 rounded text-emerald-900 font-mono font-semibold">{"{charger_id}"}</code> with your charger's CP ID.
              </p>

              <div className="bg-emerald-100/20 p-3.5 rounded-lg text-xs text-emerald-800 flex items-center justify-between border border-emerald-200/30">
                <span>
                  Example: If your charger ID is <strong>"CZ-001"</strong>, configure:
                  <code className="bg-emerald-100/60 px-1.5 py-0.5 rounded font-mono ml-2 text-emerald-900 select-all font-semibold">wss://csms.chargepulse.in/ocpp/CZ-001</code>
                </span>
                <button 
                  onClick={() => handleCopy("wss://csms.chargepulse.in/ocpp/CZ-001")}
                  className="text-xs bg-emerald-600/10 hover:bg-emerald-600/20 text-emerald-800 px-3 py-1.5 rounded font-bold transition"
                >
                  Copy
                </button>
              </div>

              <details className="group border border-emerald-200/40 rounded-lg p-3 bg-white cursor-pointer shadow-sm">
                <summary className="font-semibold text-emerald-800 flex justify-between items-center select-none text-xs">
                  Setup Instructions
                  <span className="transition group-open:rotate-180 text-emerald-600">▼</span>
                </summary>
                <ol className="list-decimal pl-5 pt-3 space-y-2 text-xs text-gray-600 leading-relaxed border-t border-slate-100 mt-2">
                  <li>Add your charger in the Chargers page</li>
                  <li>Open your charger's admin panel</li>
                  <li>Find "OCPP Server URL" or "Central System URL" field</li>
                  <li>Paste your gateway URL from above</li>
                  <li>Save and reboot the charger</li>
                  <li>Charger will appear as Online in your dashboard</li>
                </ol>
              </details>

              <div className="flex justify-between items-center pt-3 border-t border-emerald-200/40 text-xs text-emerald-800 font-semibold bg-emerald-50/20 px-1">
                <div>Connected: {(chargers?.chargers ?? []).length} chargers</div>
                <div>Protocol: OCPP 1.6J / 2.0.1</div>
                <div>Port: 443 (WSS/TLS encrypted)</div>
              </div>
            </div>
          )}

          {/* Chargers Table (Registered) */}
          {user?.role === "owner" && (chargers?.chargers ?? []).length > 0 && (
            <div className="border border-slate-100 rounded-xl overflow-hidden shadow-sm bg-white">
              <div className="px-5 py-3 border-b border-slate-50 bg-slate-50/50">
                <h3 className="font-semibold text-slate-800 text-sm">Charger Gateway Map</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="bg-slate-50 text-gray-500 font-semibold border-b border-slate-100">
                      <th className="px-5 py-3">CHARGER ID</th>
                      <th className="px-5 py-3">GATEWAY URL</th>
                      <th className="px-5 py-3">STATUS</th>
                      <th className="px-5 py-3 text-center">COPY</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {(chargers?.chargers ?? []).map((c) => {
                      const url = `wss://csms.chargepulse.in/ocpp/${c.cp_id}`;
                      return (
                        <tr key={c.cp_id} className="hover:bg-slate-50/30 transition">
                          <td className="px-5 py-3.5 font-bold text-slate-800">{c.cp_id}</td>
                          <td className="px-5 py-3.5 font-mono text-slate-500 select-all">{url}</td>
                          <td className="px-5 py-3.5">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold capitalize ${
                              c.status === "online" ? "bg-emerald-50 text-emerald-700" :
                              c.status === "faulted" ? "bg-red-50 text-red-700" : "bg-slate-100 text-slate-600"
                            }`}>
                              {c.status}
                            </span>
                          </td>
                          <td className="px-5 py-3.5 text-center">
                            <button 
                              onClick={() => handleCopy(url)}
                              className="text-gray-400 hover:text-emerald-600 p-1 rounded-md transition text-base"
                              title="Copy URL"
                            >
                              📋
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Send command section */}
          {(chargers?.chargers ?? []).length === 0 ? (
            <div className="bg-slate-50 border border-slate-200 border-dashed rounded-xl p-8 text-center space-y-3">
              <div className="text-gray-400 text-4xl">🔌</div>
              <div className="text-sm font-semibold text-slate-700">No chargers registered yet.</div>
              <p className="text-xs text-gray-500 max-w-sm mx-auto leading-relaxed">
                Add a charger first to send OCPP commands.
              </p>
              <button
                onClick={() => nav("/chargers")}
                className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg text-xs font-semibold shadow-sm transition"
              >
                Go to Chargers page →
              </button>
            </div>
          ) : (
            <section className="bg-white border rounded-xl p-6 space-y-4 shadow-sm">
              <h2 className="font-semibold text-slate-800 text-lg flex items-center gap-2">
                <Zap size={18} className="text-emerald-500" /> Send OCPP command
              </h2>
              <p className="text-xs text-gray-500 leading-relaxed">
                Sends an OCPP request to a connected charger via the gateway. Useful for triggering a
                Reset on a misbehaving unit or pulling diagnostics on demand.
              </p>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <select className="border rounded-lg px-3 py-2 focus:outline-emerald-500" value={cpId} onChange={(e) => setCpId(e.target.value)}>
                  <option value="">Select charger…</option>
                  {(chargers?.chargers ?? []).map((c) => (
                    <option key={c.cp_id} value={c.cp_id}>{c.cp_id} · {c.status}</option>
                  ))}
                </select>
                <select className="border rounded-lg px-3 py-2 focus:outline-emerald-500" value={command} onChange={(e) => setCommand(e.target.value)}>
                  {COMMANDS.map((c) => <option key={c}>{c}</option>)}
                </select>
              </div>
              <textarea
                rows={3}
                className="w-full border rounded-lg px-3 py-2 text-sm font-mono focus:outline-emerald-500"
                value={paramsText} onChange={(e) => setParamsText(e.target.value)}
                placeholder='{"type":"Soft"} or {"requested_message":"StatusNotification"}'
              />
              <div title={!cpId ? "Select a charger first" : ""} className="w-fit">
                <button
                  disabled={!cpId || busy}
                  onClick={sendCommand}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm rounded-lg disabled:opacity-50 disabled:cursor-not-allowed shadow-sm transition"
                >
                  {busy ? "Sending…" : "Send command"}
                </button>
              </div>
              {result && (
                <pre className={`text-xs p-3 rounded-lg ${result.status === "ok" ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"} overflow-auto max-h-60`}>
      {JSON.stringify(result, null, 2)}
                </pre>
              )}
            </section>
          )}
        </div>
      )}

      {/* Billing Tab */}
      {activeTab === "billing" && (
        <section className="bg-white border rounded-xl p-6 space-y-4 shadow-sm">
          <h2 className="font-semibold text-slate-800 text-lg flex items-center gap-2">
            <CreditCard size={18} className="text-emerald-500" /> Billing Settings
          </h2>
          <p className="text-sm text-gray-500">Billing dashboard ships post-MVP. Current plan is included in your subscription.</p>
          <div className="text-xs text-gray-400">Pricing: ₹200/charger/mo (starter) · ₹400 (pro) · ₹500 (enterprise)</div>
        </section>
      )}

      {/* User Invitation Modal */}
      {inviteModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in">
          <div className="bg-white rounded-xl shadow-2xl p-6 w-[450px] border border-slate-100 animate-zoom-in">
            <h2 className="text-lg font-bold text-slate-800 mb-2">Invite Team Member</h2>
            <p className="text-xs text-gray-400 mb-4">Send an invitation to join your organization on ChargePulse.</p>
            {inviteErr && <div className="text-sm bg-red-50 text-red-700 p-2.5 rounded-md mb-4">{inviteErr}</div>}
            <form onSubmit={inviteUserSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1">Email Address</label>
                <input
                  type="email"
                  required
                  placeholder="name@company.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-emerald-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1">Role / Permissions Profile</label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-emerald-500"
                >
                  <option value="admin">Admin (Ops Manager - invite users, delete configs)</option>
                  <option value="member">Member (Field Technician - acknowledge/resolve incidents)</option>
                  <option value="viewer">Viewer (Read-only stakeholder/investor)</option>
                </select>
              </div>
              <div className="flex justify-end gap-3 pt-3 border-t mt-4">
                <button
                  type="button"
                  onClick={() => setInviteModalOpen(false)}
                  className="px-4 py-2 border rounded-lg text-sm text-gray-600 hover:bg-slate-50 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={inviteBusy}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-semibold disabled:opacity-50 transition"
                >
                  {inviteBusy ? "Inviting…" : "Confirm & Send"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {toastMsg && (
        <div className="fixed bottom-5 right-5 bg-slate-900 text-slate-100 px-4 py-2.5 rounded-lg shadow-2xl border border-slate-750 text-sm font-semibold flex items-center gap-2 animate-in slide-in-from-bottom-5 duration-200 z-50">
          <span>📋</span> {toastMsg}
        </div>
      )}
    </div>
  );
}

function TabButton({ id, active, onClick, label, icon: Icon }) {
  const isActive = active === id;
  return (
    <button
      onClick={() => onClick(id)}
      className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition ${
        isActive ? "border-emerald-600 text-emerald-600" : "border-transparent text-gray-500 hover:text-slate-700"
      }`}
    >
      <Icon size={16} /> {label}
    </button>
  );
}

function Row({ k, v }) {
  return (
    <div className="flex justify-between text-sm py-1 border-b border-slate-50">
      <span className="text-gray-500">{k}</span>
      <span className="font-semibold text-slate-700 capitalize">{v ?? "—"}</span>
    </div>
  );
}
