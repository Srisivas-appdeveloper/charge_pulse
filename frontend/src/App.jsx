import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AuthProvider, useAuth } from "./hooks/useAuth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import FleetMap from "./pages/FleetMap";
import Chargers from "./pages/Chargers";
import ChargerDetail from "./pages/ChargerDetail";
import Incidents from "./pages/Incidents";
import IncidentDetail from "./pages/IncidentDetail";
import AlertConfig from "./pages/AlertConfig";
import Analytics from "./pages/Analytics";
import Settings from "./pages/Settings";
import AcceptInvite from "./pages/AcceptInvite";
import SuperAdminDashboard from "./pages/SuperAdminDashboard";

const qc = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

function Protected() {
  const { user, loading } = useAuth();
  if (loading) return <div className="h-full grid place-items-center text-sm text-gray-500">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <Layout />;
}

function AdminProtected() {
  const { user } = useAuth();
  if (user?.role !== "superadmin") return <Navigate to="/" replace />;
  return <Outlet />;
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/accept-invite" element={<AcceptInvite />} />
            <Route element={<Protected />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/map" element={<FleetMap />} />
              <Route path="/chargers" element={<Chargers />} />
              <Route path="/chargers/:cp_id" element={<ChargerDetail />} />
              <Route path="/incidents" element={<Incidents />} />
              <Route path="/incidents/:id" element={<IncidentDetail />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/alerts" element={<AlertConfig />} />
              <Route path="/settings" element={<Settings />} />
              <Route element={<AdminProtected />}>
                <Route path="/admin" element={<SuperAdminDashboard />} />
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
