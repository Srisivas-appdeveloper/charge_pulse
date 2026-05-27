import { api } from "./client";

export const adminApi = {
  getStats: () => api.get("/admin/dashboard").then((r) => r.data),
  listOrgs: () => api.get("/admin/orgs").then((r) => r.data),
  getOrgDetail: (id) => api.get(`/admin/orgs/${id}`).then((r) => r.data),
  createOrg: (payload) => api.post("/admin/orgs", payload).then((r) => r.data),
  deactivateOrg: (id) => api.delete(`/admin/orgs/${id}`).then((r) => r.data),
  impersonate: (orgId) => api.post(`/admin/impersonate/${orgId}`).then((r) => r.data),
};
