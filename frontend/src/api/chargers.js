import { api } from "./client";

export const chargersApi = {
  list: (params) => api.get("/chargers", { params }).then((r) => r.data),
  create: (body) => api.post("/chargers", body).then((r) => r.data),
  get: (cp_id) => api.get(`/chargers/${cp_id}`).then((r) => r.data),
  health: (cp_id, params) => api.get(`/chargers/${cp_id}/health`, { params }).then((r) => r.data),
  telemetry: (cp_id, params) => api.get(`/chargers/${cp_id}/telemetry`, { params }).then((r) => r.data),
  sessions: (cp_id, params) => api.get(`/chargers/${cp_id}/sessions`, { params }).then((r) => r.data),
};
