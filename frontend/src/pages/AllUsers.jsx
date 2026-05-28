import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, KeyRound, Trash2, ShieldCheck, ShieldOff, Copy, Check } from "lucide-react";
import { adminApi } from "../api/admin";

const ROLE_BADGE = {
  superadmin: "bg-purple-50 text-purple-700 border-purple-100",
  owner:      "bg-indigo-50 text-indigo-700 border-indigo-100",
  admin:      "bg-emerald-50 text-emerald-700 border-emerald-100",
  member:     "bg-slate-50 text-slate-700 border-slate-100",
  viewer:     "bg-amber-50 text-amber-700 border-amber-100",
};

function fmtDate(s) {
  if (!s) return "—";
  try { return new Date(s).toLocaleString(); } catch { return s; }
}

function ResetPasswordModal({ result, onClose }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(result.temporary_password);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* ignore */ }
  };
  return (
    <div className="fixed inset-0 bg-black/50 grid place-items-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
        <h2 className="text-lg font-bold text-slate-800">Temporary password generated</h2>
        <div className="text-sm text-slate-600">
          For <span className="font-mono">{result.email}</span>
        </div>
        <div className="bg-amber-50 border border-amber-200 text-amber-900 text-xs p-3 rounded-md">
          ⚠ This password is shown <strong>only once</strong>. Copy it now and share over
          a secure channel. The user should change it immediately after logging in.
        </div>
        <div className="flex items-center gap-2 bg-slate-900 text-emerald-300 font-mono text-sm px-3 py-2 rounded-md">
          <span className="flex-1 select-all">{result.temporary_password}</span>
          <button onClick={copy} className="text-slate-300 hover:text-white">
            {copied ? <Check size={16} /> : <Copy size={16} />}
          </button>
        </div>
        <div className="flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-md bg-slate-800 text-white text-sm hover:bg-slate-900"
          >
            I've copied it
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AllUsers() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [resetResult, setResetResult] = useState(null);

  const { data: users = [], isLoading, error } = useQuery({
    queryKey: ["admin-users"],
    queryFn: adminApi.listUsers,
  });

  const resetMutation = useMutation({
    mutationFn: adminApi.resetUserPassword,
    onSuccess: (data) => setResetResult(data),
  });

  const activeMutation = useMutation({
    mutationFn: ({ id, active }) => adminApi.setUserActive(id, active),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: adminApi.deleteUser,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    return users.filter((u) => {
      if (roleFilter !== "all" && u.role !== roleFilter) return false;
      if (!s) return true;
      return (
        u.email.toLowerCase().includes(s) ||
        u.full_name.toLowerCase().includes(s) ||
        (u.org_name || "").toLowerCase().includes(s)
      );
    });
  }, [users, q, roleFilter]);

  if (isLoading) return <div className="text-sm text-gray-500">Loading users…</div>;
  if (error) return <div className="text-sm text-rose-600">Failed to load users.</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">All Users</h1>
        <p className="text-sm text-gray-500">
          Every user across every organisation (plus platform superadmins).
          Passwords are never displayed — use "Reset" to issue a one-time temporary
          password to share over a secure channel.
        </p>
      </div>

      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-2.5 text-slate-400" />
          <input
            placeholder="Search email, name, or org…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="pl-8 pr-3 py-2 border border-slate-200 rounded-md text-sm w-72"
          />
        </div>
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="px-3 py-2 border border-slate-200 rounded-md text-sm"
        >
          <option value="all">All roles</option>
          <option value="superadmin">Superadmin</option>
          <option value="owner">Owner</option>
          <option value="admin">Admin</option>
          <option value="member">Member</option>
          <option value="viewer">Viewer</option>
        </select>
        <span className="text-xs text-slate-500 ml-auto">{filtered.length} of {users.length}</span>
      </div>

      <div className="bg-white border border-slate-100 rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-gray-500 font-medium border-b border-slate-100">
            <tr>
              <th className="px-6 py-3">User</th>
              <th className="px-6 py-3">Organisation</th>
              <th className="px-6 py-3">Role</th>
              <th className="px-6 py-3">Status</th>
              <th className="px-6 py-3">Last login</th>
              <th className="px-6 py-3">Created</th>
              <th className="px-6 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filtered.map((u) => (
              <tr key={u.id} className="hover:bg-slate-50/40">
                <td className="px-6 py-4">
                  <div className="font-medium text-slate-800">{u.full_name}</div>
                  <div className="text-xs text-slate-500">{u.email}</div>
                </td>
                <td className="px-6 py-4 text-slate-700">
                  {u.is_superadmin ? <span className="text-purple-700 font-medium">— Platform —</span> : (u.org_name || "—")}
                </td>
                <td className="px-6 py-4">
                  <span className={`px-2 py-0.5 rounded text-xs border ${ROLE_BADGE[u.role] || ROLE_BADGE.member}`}>
                    {u.role}
                  </span>
                </td>
                <td className="px-6 py-4">
                  {u.is_active ? (
                    <span className="text-emerald-700 text-xs font-semibold">Active</span>
                  ) : (
                    <span className="text-slate-400 text-xs font-semibold">Disabled</span>
                  )}
                </td>
                <td className="px-6 py-4 text-xs text-slate-500">{fmtDate(u.last_login_at)}</td>
                <td className="px-6 py-4 text-xs text-slate-500">{fmtDate(u.created_at)}</td>
                <td className="px-6 py-4 text-right">
                  <div className="flex justify-end gap-1">
                    <button
                      title="Reset password"
                      onClick={() => {
                        if (confirm(`Generate a new temporary password for ${u.email}?`)) {
                          resetMutation.mutate(u.id);
                        }
                      }}
                      className="p-1.5 rounded hover:bg-amber-50 text-amber-600"
                    >
                      <KeyRound size={16} />
                    </button>
                    {!u.is_superadmin && (
                      <button
                        title={u.is_active ? "Deactivate" : "Reactivate"}
                        onClick={() => activeMutation.mutate({ id: u.id, active: !u.is_active })}
                        className={`p-1.5 rounded hover:bg-slate-100 ${u.is_active ? "text-slate-600" : "text-emerald-600"}`}
                      >
                        {u.is_active ? <ShieldOff size={16} /> : <ShieldCheck size={16} />}
                      </button>
                    )}
                    {!u.is_superadmin && (
                      <button
                        title="Delete user"
                        onClick={() => {
                          if (confirm(`Permanently delete ${u.email}? This cannot be undone.`)) {
                            deleteMutation.mutate(u.id);
                          }
                        }}
                        className="p-1.5 rounded hover:bg-rose-50 text-rose-600"
                      >
                        <Trash2 size={16} />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="px-6 py-12 text-center text-sm text-slate-400">
                  No users match.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {resetResult && (
        <ResetPasswordModal result={resetResult} onClose={() => setResetResult(null)} />
      )}
    </div>
  );
}
