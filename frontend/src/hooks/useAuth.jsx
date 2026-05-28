import { createContext, useContext, useEffect, useState } from "react";
import { authApi } from "../api/auth";

const AuthContext = createContext(null);

// Decode the JWT payload without signature verification — purely for reading
// claims like `impersonating` on the client. Server still validates the token.
function decodeJwtClaims(token) {
  if (!token) return null;
  try {
    const payload = token.split(".")[1];
    const padded = payload + "===".slice((payload.length + 3) % 4);
    const json = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

function tokenIsImpersonation(token) {
  const claims = decodeJwtClaims(token);
  return !!(claims && claims.impersonating);
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [org, setOrg] = useState(null);
  const [loading, setLoading] = useState(true);
  const [impersonating, setImpersonating] = useState(
    () => tokenIsImpersonation(localStorage.getItem("token"))
  );

  useEffect(() => {
    if (!localStorage.getItem("token")) { setLoading(false); return; }
    authApi.me()
      .then((d) => { setUser(d.user); setOrg(d.organisation); })
      .catch(() => {
        localStorage.removeItem("token");
        localStorage.removeItem("super_token");
      })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const d = await authApi.login(email, password);
    localStorage.setItem("token", d.access_token);
    // Fresh login is never an impersonation, so always clear the backup slot.
    localStorage.removeItem("super_token");
    setUser(d.user); setOrg(d.organisation);
    setImpersonating(tokenIsImpersonation(d.access_token));
    return d;
  };

  const register = async (payload) => {
    const d = await authApi.register(payload);
    localStorage.setItem("token", d.access_token);
    localStorage.removeItem("super_token");
    setUser(d.user); setOrg(d.organisation);
    setImpersonating(false);
    return d;
  };

  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("super_token");
    setUser(null); setOrg(null);
    setImpersonating(false);
    window.location.assign("/login");
  };

  const startImpersonation = (token) => {
    // Save the current (real superadmin) token so Exit can restore it.
    const current = localStorage.getItem("token");
    if (current && !tokenIsImpersonation(current)) {
      localStorage.setItem("super_token", current);
    }
    localStorage.setItem("token", token);
    setImpersonating(tokenIsImpersonation(token));
    setLoading(true);
    authApi.me()
      .then((d) => { setUser(d.user); setOrg(d.organisation); })
      .finally(() => setLoading(false));
  };

  const exitImpersonation = () => {
    const superToken = localStorage.getItem("super_token");
    if (superToken) {
      localStorage.setItem("token", superToken);
      localStorage.removeItem("super_token");
      setImpersonating(false);
      window.location.assign("/admin");
    } else {
      // No backup — token state is inconsistent. Force a clean re-login.
      logout();
    }
  };

  return (
    <AuthContext.Provider value={{ user, org, loading, login, register, logout, startImpersonation, exitImpersonation, impersonating }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
