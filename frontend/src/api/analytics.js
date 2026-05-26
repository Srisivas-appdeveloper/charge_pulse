import { api } from "./client";

export const analyticsApi = {
  reliability: (params) => api.get("/analytics/reliability", { params }).then((r) => r.data),
  vendorComparison: () => api.get("/analytics/vendor-comparison").then((r) => r.data),
  predictions: () => api.get("/analytics/predictions").then((r) => r.data),
};
