import { api } from "./client";

export const authApi = {
  login: (email, password) => api.post("/auth/login", { email, password }).then((r) => r.data),
  register: (payload) => api.post("/auth/register", payload).then((r) => r.data),
  me: () => api.get("/auth/me").then((r) => r.data),
};
