import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { ApiError } from "../api/client";

import {
  clearMasterAdminCsrfToken,
  masterAdminFetch,
  setMasterAdminCsrfToken,
  type MasterAdminLoginResult,
  type MasterAdminMfaEnrollment,
  type MasterAdminMfaRecoveryCodes,
  type MasterAdminUser
} from "./api";

type SessionStatus = "loading" | "anonymous" | "authenticated" | "mfa_setup_required";

type MasterAdminSessionValue = {
  user: MasterAdminUser | null;
  status: SessionStatus;
  csrfToken: string | null;
  login: (email: string, password: string, pin: string) => Promise<MasterAdminLoginResult>;
  completeMfaLogin: (mfaToken: string, code: string) => Promise<void>;
  enrollMfa: (password: string) => Promise<MasterAdminMfaEnrollment>;
  confirmMfa: (code: string) => Promise<MasterAdminMfaRecoveryCodes>;
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
    const response = await masterAdminFetch<MasterAdminLoginResult>("/api/master-admin/auth/login", {
      method: "POST",
      data: { email, password, pin }
    });
    if ("requires_mfa_setup" in response) {
      setUser(response.user);
      setCsrfToken(response.csrf_token);
      setMasterAdminCsrfToken(response.csrf_token);
      setStatus("mfa_setup_required");
    } else if (!("requires_mfa" in response)) {
      setUser(response.user);
      setCsrfToken(response.csrf_token);
      setMasterAdminCsrfToken(response.csrf_token);
      setStatus("authenticated");
    }
    return response;
  };

  const completeMfaLogin = async (mfaToken: string, code: string) => {
    const response = await masterAdminFetch<{ user: MasterAdminUser; csrf_token: string }>("/api/master-admin/auth/login/mfa", {
      method: "POST",
      data: { mfa_token: mfaToken, code }
    });
    setUser(response.user);
    setCsrfToken(response.csrf_token);
    setMasterAdminCsrfToken(response.csrf_token);
    setStatus("authenticated");
  };

  const enrollMfa = (password: string) =>
    masterAdminFetch<MasterAdminMfaEnrollment>("/api/master-admin/mfa/enroll", {
      method: "POST",
      data: { password }
    });

  const confirmMfa = async (code: string) => {
    return masterAdminFetch<MasterAdminMfaRecoveryCodes>("/api/master-admin/mfa/enroll/confirm", {
      method: "POST",
      data: { code }
    });
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
    completeMfaLogin,
    enrollMfa,
    confirmMfa,
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
