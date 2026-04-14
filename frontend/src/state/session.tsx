import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { buildAuthHeaders } from "../api/client";

type Role = "owner" | "co_owner" | "manager" | "housekeeping" | "receptionist";

export type SessionState = {
  userId: string | null;
  email?: string | null;
  hotelId: number | null;
  hotelIds?: number[] | null;
  role: Role | null;
  baseRole?: Role | null;
  accessToken?: string | null;
  isVerified?: boolean;
};

type SessionContextValue = {
  session: SessionState;
  login: (partial: Partial<SessionState>) => void;
  logout: () => void;
  setHotelId: (hotelId: number | null) => void;
  setRole: (role: SessionState["role"]) => void;
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

const loadSession = (): SessionState => EMPTY_SESSION;

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<SessionState>(() => loadSession());

  // Always require re-login on page reload: clear any stale persisted session.
  useEffect(() => {
    setSession(EMPTY_SESSION);
    if (typeof localStorage !== "undefined") {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

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
    setSession((prev) => ({
      ...prev,
      hotelId: safeHotelId(hotelId),
      hotelIds: safeHotelId(hotelId) ? [safeHotelId(hotelId) as number] : prev.hotelIds ?? null
    }));
  const setRole = (role: SessionState["role"]) => setSession((prev) => ({ ...prev, role }));

  const authHeaders = useMemo(() => buildAuthHeaders(session), [session]);

  const value: SessionContextValue = { session, login, logout, setHotelId, setRole, authHeaders };

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export const useSession = () => {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
};

export { safeHotelId };
