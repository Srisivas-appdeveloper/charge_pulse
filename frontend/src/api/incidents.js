import { api } from "./client";

export const incidentsApi = {
  list: (params) => api.get("/incidents", { params }).then((r) => r.data),
  get: (id) => api.get(`/incidents/${id}`).then((r) => r.data),
  patch: (id, body) => api.patch(`/incidents/${id}`, body).then((r) => r.data),
};
