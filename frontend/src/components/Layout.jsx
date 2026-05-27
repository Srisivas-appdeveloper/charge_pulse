import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import { useAuth } from "../hooks/useAuth";
import { useLiveFeed } from "../hooks/useLiveFeed";
import { LogOut, Wifi, WifiOff, EyeOff } from "lucide-react";

export default function Layout() {
  const { user, org, logout, impersonating, exitImpersonation } = useAuth();
  const { connected, events } = useLiveFeed();

  return (
    <div className="h-full flex flex-col">
      {impersonating && (
        <div className="bg-amber-500 text-white text-sm font-semibold flex items-center justify-between px-6 py-2 shadow-sm">
          <div className="flex items-center gap-2">
            <span>👁 Viewing as: <strong>{org?.name}</strong></span>
          </div>
          <button 
            onClick={exitImpersonation} 
            className="bg-white text-amber-600 px-3 py-1 rounded text-xs hover:bg-amber-50 transition-all font-bold shadow-sm"
          >
            Exit Impersonation
          </button>
        </div>
      )}
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <main className="flex-1 flex flex-col bg-slate-50 overflow-hidden">
          <header className="h-14 bg-white border-b flex items-center justify-between px-6">
            <div className="text-sm text-gray-500">
              {org?.name} {org?.plan && <span className="text-gray-300 mx-2">·</span>}{" "}
              {org?.plan && <span className="capitalize">{org?.plan} plan</span>}
            </div>
            <div className="flex items-center gap-4">
              <span className="text-xs flex items-center gap-1 text-gray-500">
                {connected ? <Wifi size={14} className="text-emerald-500" /> : <WifiOff size={14} className="text-gray-400" />}
                live {events.length > 0 ? `· ${events.length}` : ""}
              </span>
              <span className="text-sm font-medium">{user?.full_name} <span className="text-gray-400 text-xs">({user?.role})</span></span>
              <button onClick={logout} className="text-gray-400 hover:text-gray-700">
                <LogOut size={16} />
              </button>
            </div>
          </header>
          <div className="flex-1 overflow-auto p-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
