import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import { useAuth } from "../hooks/useAuth";
import { useLiveFeed } from "../hooks/useLiveFeed";
import { LogOut, Wifi, WifiOff } from "lucide-react";

export default function Layout() {
  const { user, org, logout } = useAuth();
  const { connected, events } = useLiveFeed();

  return (
    <div className="h-full flex">
      <Sidebar />
      <main className="flex-1 flex flex-col bg-slate-50 overflow-hidden">
        <header className="h-14 bg-white border-b flex items-center justify-between px-6">
          <div className="text-sm text-gray-500">
            {org?.name} <span className="text-gray-300 mx-2">·</span>{" "}
            <span className="capitalize">{org?.plan} plan</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-xs flex items-center gap-1 text-gray-500">
              {connected ? <Wifi size={14} className="text-emerald-500" /> : <WifiOff size={14} className="text-gray-400" />}
              live {events.length > 0 ? `· ${events.length}` : ""}
            </span>
            <span className="text-sm">{user?.full_name}</span>
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
  );
}
