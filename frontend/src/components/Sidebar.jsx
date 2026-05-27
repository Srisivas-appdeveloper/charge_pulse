import { NavLink } from "react-router-dom";
import { LayoutDashboard, Map, AlertTriangle, BarChart3, Bell, Zap, ShieldCheck, Settings as SettingsIcon, Building2 } from "lucide-react";
import { useAuth } from "../hooks/useAuth";

const ownerItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/map", label: "Fleet Map", icon: Map },
  { to: "/chargers", label: "Chargers", icon: Zap },
  { to: "/incidents", label: "Incidents", icon: AlertTriangle },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/alerts", label: "Alert Config", icon: Bell },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

const adminItems = [
  { to: "/admin", label: "Admin Dashboard", icon: ShieldCheck, end: true },
  { to: "/admin", label: "All Organisations", icon: Building2 },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

export default function Sidebar() {
  const { user, impersonating } = useAuth();

  const isSuper = user?.role === "superadmin";
  const items = (isSuper && !impersonating) ? adminItems : ownerItems;

  return (
    <aside className="w-56 bg-slate-900 text-slate-100 flex flex-col">
      <div className="p-5 text-xl font-bold border-b border-slate-800 flex items-center gap-2">
        <Zap className="text-emerald-400" /> ChargePulse
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {items.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={label}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition ${
                isActive 
                  ? ((isSuper && !impersonating) ? "bg-purple-600 text-white" : "bg-emerald-600 text-white") 
                  : "text-slate-300 hover:bg-slate-800"
              }`
            }
          >
            <Icon size={18} /> {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
