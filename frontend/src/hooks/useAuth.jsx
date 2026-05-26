import { createContext, useContext, useEffect, useState } from "react";
import { authApi } from "../api/auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [org, setOrg] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!localStorage.getItem("token")) { setLoading(false); return; }
    authApi.me()
      .then((d) => { setUser(d.user); setOrg(d.organisation); })
      .catch(() => localStorage.removeItem("token"))
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const d = await authApi.login(email, password);
    localStorage.setItem("token", d.access_token);
    setUser(d.user); setOrg(d.organisation);
    return d;
  };

  const register = async (payload) => {
    const d = await authApi.register(payload);
    localStorage.setItem("token", d.access_token);
    setUser(d.user); setOrg(d.organisation);
    return d;
  };

  const logout = () => {
    localStorage.removeItem("token");
    setUser(null); setOrg(null);
    window.location.assign("/login");
  };

  return (
    <AuthContext.Provider value={{ user, org, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
