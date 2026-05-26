import { api } from "./client";

export const alertsApi = {
  list: () => api.get("/alerts/config").then((r) => r.data),
  create: (body) => api.post("/alerts/config", body).then((r) => r.data),
  update: (id, body) => api.put(`/alerts/config/${id}`, body).then((r) => r.data),
  remove: (id) => api.delete(`/alerts/config/${id}`).then((r) => r.data),
};
