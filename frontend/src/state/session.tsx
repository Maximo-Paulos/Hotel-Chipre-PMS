import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  apiFetch,
  buildAuthHeaders,
  refreshSession,
  setAuthResponseHandler,
  setClientSession,
  setUnauthorizedHandler,
  type AuthResponsePayload
} from "../api/client";
import { isAppHostname } from "../config/publicUrls";

export type Role = "owner" | "co_owner" | "manager" | "housekeeping" | "receptionist";

export type SessionState = {
  userId: string | null;
  email?: string | null;
  hotelId: number | null;
  hotelIds?: number[] | null;
  role: Role | null;
  baseRole?: Role | null;
  permissions?: string[] | null;
  accessToken?: string | null;
  csrfToken?: string | null;
  isVerified?: boolean;
};

type SessionContextValue = {
  session: SessionState;
  login: (partial: Partial<SessionState>) => void;
  logout: () => void;
  isInitializing: boolean;
  restoredSession: boolean;
  setHotelId: (hotelId: number | null) => void;
  setRole: (role: SessionState["role"]) => void;
  setPermissions: (permissions: string[], role?: Role | null) => void;
  authHeaders: Record<string, string>;
};

const LEGACY_STORAGE_KEY = "hotel-pms-session";
const CSRF_STORAGE_KEY = "hotel-pms-csrf-token";
const EMPTY_SESSION: SessionState = {
  userId: null,
  email: null,
  hotelId: null,
  hotelIds: null,
  role: null,
  baseRole: null,
  permissions: null,
  accessToken: null,
  csrfToken: null,
  isVerified: false
};

const SessionContext = createContext<SessionContextValue | null>(null);

const safeHotelId = (value?: number | string | null): number | null => {
  const parsed = typeof value === "string" ? parseInt(value, 10) : value;
  return Number.isInteger(parsed) && (parsed as number) > 0 ? (parsed as number) : null;
};

export const normalizeRole = (role?: string | null): Role | null => {
  const normalized = role?.trim().toLowerCase();
  if (
    normalized === "owner" ||
    normalized === "co_owner" ||
    normalized === "manager" ||
    normalized === "housekeeping" ||
    normalized === "receptionist"
  ) {
    return normalized as Role;
  }
  return null;
};

export const defaultPathForRole = (role: Role | null | undefined) =>
  role === "housekeeping" ? "/habitaciones" : "/dashboard";

const readStoredCsrfToken = (): string | null => {
  if (typeof localStorage === "undefined") return null;
  try {
    const token = localStorage.getItem(CSRF_STORAGE_KEY)?.trim();
    return token || null;
  } catch {
    return null;
  }
};

const persistCsrfToken = (token?: string | null) => {
  if (typeof localStorage === "undefined") return;
  try {
    if (token?.trim()) {
      localStorage.setItem(CSRF_STORAGE_KEY, token.trim());
    } else {
      localStorage.removeItem(CSRF_STORAGE_KEY);
    }
  } catch {
    /* ignore storage quota / availability errors */
  }
};

const clearLegacyStoredSession = () => {
  if (typeof localStorage === "undefined") return;
  try {
    // Remove the old bearer-token payload once. Only the CSRF bootstrap value
    // remains persisted; access tokens never return to browser storage.
    localStorage.removeItem(LEGACY_STORAGE_KEY);
  } catch {
    /* ignore unavailable storage */
  }
};

const initialSession = (): SessionState => ({
  ...EMPTY_SESSION,
  csrfToken: readStoredCsrfToken()
});

const sessionFromAuthResponse = (response: AuthResponsePayload): Partial<SessionState> => {
  const role = normalizeRole(response.user.role);
  return {
    userId: response.user.email,
    email: response.user.email,
    hotelId: response.hotel_id,
    hotelIds: response.hotel_ids?.length ? response.hotel_ids : [response.hotel_id],
    role,
    baseRole: role,
    permissions: response.permissions ?? response.user.permissions ?? null,
    accessToken: response.access_token,
    csrfToken: response.csrf_token ?? null,
    isVerified: response.user.is_verified
  };
};

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<SessionState>(() => {
    clearLegacyStoredSession();
    return initialSession();
  });
  const [isInitializing, setIsInitializing] = useState(() => isAppHostname());
  const [restoredSession, setRestoredSession] = useState(false);

  const login = useCallback((partial: Partial<SessionState>) => {
    setSession((prev) => ({
      userId: partial.userId?.trim() || prev.userId || null,
      email: partial.email ?? partial.userId ?? prev.email ?? null,
      hotelId: safeHotelId(partial.hotelId ?? prev.hotelId),
      role: (partial.role as Role | null | undefined) ?? prev.role ?? null,
      baseRole:
        (partial.baseRole as Role | null | undefined) ??
        (partial.role as Role | null | undefined) ??
        prev.baseRole ??
        null,
      permissions:
        partial.permissions !== undefined
          ? Array.from(new Set((partial.permissions ?? []).filter((permission) => typeof permission === "string"))).sort()
          : prev.permissions ?? null,
      accessToken: partial.accessToken ?? prev.accessToken ?? null,
      csrfToken:
        partial.csrfToken !== undefined
          ? typeof partial.csrfToken === "string" && partial.csrfToken.trim()
            ? partial.csrfToken.trim()
            : null
          : prev.csrfToken ?? null,
      isVerified: partial.isVerified ?? prev.isVerified ?? false,
      hotelIds: partial.hotelIds?.length
        ? partial.hotelIds
        : safeHotelId(partial.hotelId ?? prev.hotelId)
          ? [safeHotelId(partial.hotelId ?? prev.hotelId) as number]
          : prev.hotelIds ?? null
    }));
  }, []);

  const applyAuthResponse = useCallback((response: AuthResponsePayload) => {
    if (!response.access_token || !response.user || !response.hotel_id) return;
    login(sessionFromAuthResponse(response));
  }, [login]);

  const logout = useCallback(() => {
    const currentSession = session;
    // Logout is deliberately best-effort. Clear local state immediately even
    // if the browser is offline or the cookie session has already expired.
    void apiFetch<{ logged_out: boolean }>("/api/auth/logout", {
      method: "POST",
      session: currentSession
    }).catch(() => undefined);
    setClientSession(null);
    setSession(EMPTY_SESSION);
    setRestoredSession(false);
  }, [session]);

  // Keep the API module's synchronous snapshot aligned with React state so an
  // interceptor can refresh even while a component still holds an older
  // render's SessionState object.
  useEffect(() => {
    setClientSession(session);
    persistCsrfToken(session.csrfToken);
  }, [session]);

  useEffect(() => {
    const removeAuthResponseHandler = setAuthResponseHandler(applyAuthResponse);
    const removeUnauthorizedHandler = setUnauthorizedHandler(() => {
      setClientSession(null);
      setSession(EMPTY_SESSION);
      setRestoredSession(false);
    });
    return () => {
      removeAuthResponseHandler();
      removeUnauthorizedHandler();
    };
  }, [applyAuthResponse]);

  useEffect(() => {
    if (!isInitializing) return;
    let cancelled = false;
    void refreshSession()
      .then((response) => {
        if (cancelled) return;
        applyAuthResponse(response);
        setRestoredSession(true);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 401) {
          persistCsrfToken(null);
          setSession(EMPTY_SESSION);
        }
      })
      .finally(() => {
        if (!cancelled) setIsInitializing(false);
      });
    return () => {
      cancelled = true;
    };
  }, [applyAuthResponse, isInitializing]);

  const setHotelId = (hotelId: number | null) =>
    setSession((prev) => {
      const nextHotelId = safeHotelId(hotelId);
      if (!nextHotelId) return prev;

      const authorizedHotelIds = (prev.hotelIds ?? [])
        .map((id) => safeHotelId(id))
        .filter((id): id is number => id !== null);
      if (authorizedHotelIds.length > 0 && !authorizedHotelIds.includes(nextHotelId)) {
        return prev;
      }

      return {
        ...prev,
        hotelId: nextHotelId,
        // The login response is the source of truth for memberships. Keep the
        // complete authorized list so switching once does not erase every
        // other hotel from the selector.
        hotelIds: prev.hotelIds?.length ? prev.hotelIds : [nextHotelId],
        permissions: nextHotelId === prev.hotelId ? prev.permissions ?? null : null
      };
    });
  const setRole = (role: SessionState["role"]) => setSession((prev) => ({ ...prev, role }));
  const setPermissions = useCallback((permissions: string[], role?: Role | null) =>
    setSession((prev) => {
      const wasPreviewing = Boolean(prev.role && prev.baseRole && prev.role !== prev.baseRole);
      return {
        ...prev,
        role: role && !wasPreviewing ? role : prev.role,
        baseRole: role ?? prev.baseRole,
        permissions: Array.from(new Set(permissions.filter((permission) => typeof permission === "string"))).sort()
      };
    }), []);

  const authHeaders = useMemo(() => buildAuthHeaders(session), [session]);

  const value: SessionContextValue = {
    session,
    login,
    logout,
    isInitializing,
    restoredSession,
    setHotelId,
    setRole,
    setPermissions,
    authHeaders
  };

  if (isInitializing) {
    return <p className="p-8 text-sm text-slate-500" role="status">Comprobando sesión...</p>;
  }

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export const useSession = () => {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
};

export { safeHotelId };
