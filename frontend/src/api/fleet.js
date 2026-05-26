import { api } from "./client";

export const fleetApi = {
  overview: () => api.get("/fleet/overview").then((r) => r.data),
  map: () => api.get("/fleet/map").then((r) => r.data),
  uptime: (params) => api.get("/fleet/uptime", { params }).then((r) => r.data),
};
