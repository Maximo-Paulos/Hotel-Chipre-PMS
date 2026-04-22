import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { ApiError } from "../api/client";

import {
  clearMasterAdminCsrfToken,
  masterAdminFetch,
  setMasterAdminCsrfToken,
  type MasterAdminLoginResponse,
  type MasterAdminUser
} from "./api";

type SessionStatus = "loading" | "anonymous" | "authenticated";

type MasterAdminSessionValue = {
  user: MasterAdminUser | null;
  status: SessionStatus;
  csrfToken: string | null;
  login: (email: string, password: string, pin: string) => Promise<MasterAdminLoginResponse>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const MasterAdminSessionContext = createContext<MasterAdminSessionValue | null>(null);

const SESSION_HINT_COOKIE_NAME = "master_admin_session_hint";

const hasSessionHintCookie = () => {
  if (typeof document === "undefined") return false;
  return document.cookie.split("; ").some((entry) => entry.startsWith(`${SESSION_HINT_COOKIE_NAME}=`));
};

export function MasterAdminSessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<MasterAdminUser | null>(null);
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [status, setStatus] = useState<SessionStatus>("loading");

  const refresh = async () => {
    if (!hasSessionHintCookie()) {
      setUser(null);
      setCsrfToken(null);
      clearMasterAdminCsrfToken();
      setStatus("anonymous");
      return;
    }
    setStatus("loading");
    try {
      const response = await masterAdminFetch<{ user: MasterAdminUser; csrf_token: string }>("/api/master-admin/auth/me");
      setUser(response.user);
      setCsrfToken(response.csrf_token);
      setMasterAdminCsrfToken(response.csrf_token);
      setStatus("authenticated");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setUser(null);
        setCsrfToken(null);
        clearMasterAdminCsrfToken();
        setStatus("anonymous");
        return;
      }
      setUser(null);
      setCsrfToken(null);
      clearMasterAdminCsrfToken();
      setStatus("anonymous");
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const login = async (email: string, password: string, pin: string) => {
    const response = await masterAdminFetch<MasterAdminLoginResponse>("/api/master-admin/auth/login", {
      method: "POST",
      data: { email, password, pin }
    });
    setUser(response.user);
    setCsrfToken(response.csrf_token);
    setMasterAdminCsrfToken(response.csrf_token);
    setStatus("authenticated");
    return response;
  };

  const logout = async () => {
    try {
      await masterAdminFetch("/api/master-admin/auth/logout", { method: "POST" });
    } finally {
      setUser(null);
      setCsrfToken(null);
      clearMasterAdminCsrfToken();
      setStatus("anonymous");
    }
  };

  const value: MasterAdminSessionValue = {
    user,
    status,
    csrfToken,
    login,
    logout,
    refresh
  };

  return <MasterAdminSessionContext.Provider value={value}>{children}</MasterAdminSessionContext.Provider>;
}

export function useMasterAdminSession() {
  const ctx = useContext(MasterAdminSessionContext);
  if (!ctx) {
    throw new Error("useMasterAdminSession must be used within MasterAdminSessionProvider");
  }
  return ctx;
}
