import { api } from "./client";

export const usersApi = {
  listUsers: () => api.get("/users/").then((r) => r.data),
  inviteUser: (payload) => api.post("/users/invite", payload).then((r) => r.data),
  updateRole: (id, role) => api.patch(`/users/${id}`, { role }).then((r) => r.data),
  deleteUser: (id) => api.delete(`/users/${id}`).then((r) => r.data),
};
