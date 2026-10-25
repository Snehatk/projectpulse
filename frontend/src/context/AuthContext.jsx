import { createContext, useContext, useEffect, useState } from "react";
import {
  getAuthStatus,
  getCurrentUserProfile,
  loginUser,
  setupFirstPM,
} from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem("projectpulse_user");
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });
  const [token, setToken] = useState(() => localStorage.getItem("projectpulse_token") || null);
  const [hasPMAccount, setHasPMAccount] = useState(null);
  const [loading, setLoading] = useState(true);

  const checkStatus = async () => {
    try {
      const status = await getAuthStatus();
      const hasPM = Boolean(status?.has_pm_account);
      setHasPMAccount(hasPM);
      return hasPM;
    } catch (err) {
      console.warn("Auth status check warning:", err);
      setHasPMAccount(false);
      return false;
    }
  };

  const loadUserProfile = async () => {
    if (!token) {
      setUser(null);
      return null;
    }
    try {
      const profile = await getCurrentUserProfile();
      setUser(profile);
      localStorage.setItem("projectpulse_user", JSON.stringify(profile));
      return profile;
    } catch (err) {
      console.warn("Session expired or invalid:", err);
      logout();
      return null;
    }
  };

  useEffect(() => {
    let mounted = true;
    Promise.all([checkStatus(), loadUserProfile()]).finally(() => {
      if (mounted) setLoading(false);
    });
    return () => {
      mounted = false;
    };
  }, []);

  const login = async (email, password) => {
    const res = await loginUser(email, password);
    setToken(res.access_token);
    localStorage.setItem("projectpulse_token", res.access_token);
    const profile = {
      user_id: res.user_id,
      email: res.email,
      name: res.name,
      role: res.role,
      is_active: true,
    };
    setUser(profile);
    localStorage.setItem("projectpulse_user", JSON.stringify(profile));
    setHasPMAccount(true);
    return profile;
  };

  const setupPM = async (payload) => {
    const res = await setupFirstPM(payload);
    setToken(res.access_token);
    localStorage.setItem("projectpulse_token", res.access_token);
    const profile = {
      user_id: res.user_id,
      email: res.email,
      name: res.name,
      role: res.role,
      is_active: true,
    };
    setUser(profile);
    localStorage.setItem("projectpulse_user", JSON.stringify(profile));
    setHasPMAccount(true);
    return profile;
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem("projectpulse_token");
    localStorage.removeItem("projectpulse_user");
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        role: user?.role || null,
        isAuthenticated: Boolean(token && user),
        hasPMAccount,
        loading,
        login,
        setupPM,
        logout,
        refreshStatus: checkStatus,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
