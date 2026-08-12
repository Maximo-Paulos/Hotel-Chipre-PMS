import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { buildAuthHeaders } from "../api/client";

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
  isVerified?: boolean;
};

type SessionContextValue = {
  session: SessionState;
  login: (partial: Partial<SessionState>) => void;
  logout: () => void;
  setHotelId: (hotelId: number | null) => void;
  setRole: (role: SessionState["role"]) => void;
  setPermissions: (permissions: string[], role?: Role | null) => void;
  authHeaders: Record<string, string>;
};

const STORAGE_KEY = "hotel-pms-session";
const EMPTY_SESSION: SessionState = {
  userId: null,
  email: null,
  hotelId: null,
  hotelIds: null,
  role: null,
  baseRole: null,
  permissions: null,
  accessToken: null,
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

const loadSession = (): SessionState => {
  if (typeof localStorage === "undefined") return EMPTY_SESSION;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY_SESSION;
    const parsed = JSON.parse(raw) as Partial<SessionState>;
    const hotelId = safeHotelId(parsed.hotelId);
    const userId = typeof parsed.userId === "string" ? parsed.userId.trim() : "";
    const accessToken = typeof parsed.accessToken === "string" ? parsed.accessToken.trim() : "";
    // Only restore a session that actually carries valid credentials.
    if (!hotelId || !userId || !accessToken) return EMPTY_SESSION;
    return {
      ...EMPTY_SESSION,
      ...parsed,
      userId,
      hotelId,
      accessToken,
      role: normalizeRole(parsed.role as string | null | undefined),
      baseRole: normalizeRole((parsed.baseRole ?? parsed.role) as string | null | undefined),
      permissions: Array.isArray(parsed.permissions)
        ? parsed.permissions.filter((permission): permission is string => typeof permission === "string")
        : null,
    };
  } catch {
    return EMPTY_SESSION;
  }
};

const persistSession = (session: SessionState) => {
  if (typeof localStorage === "undefined") return;
  try {
    if (session.userId && session.hotelId && session.accessToken) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    /* ignore storage quota / availability errors */
  }
};

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<SessionState>(() => loadSession());

  // Persist the session so reloads and deep-links into protected routes keep
  // the user logged in instead of bouncing back to /login.
  useEffect(() => {
    persistSession(session);
  }, [session]);

  const login = (partial: Partial<SessionState>) => {
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
      isVerified: partial.isVerified ?? prev.isVerified ?? false,
      hotelIds: partial.hotelIds?.length
        ? partial.hotelIds
        : safeHotelId(partial.hotelId ?? prev.hotelId)
          ? [safeHotelId(partial.hotelId ?? prev.hotelId) as number]
          : prev.hotelIds ?? null
    }));
  };

  const logout = () => {
    setSession(EMPTY_SESSION);
  };

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

  const value: SessionContextValue = { session, login, logout, setHotelId, setRole, setPermissions, authHeaders };

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export const useSession = () => {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
};

export { safeHotelId };
