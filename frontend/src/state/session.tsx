import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { buildAuthHeaders } from "../api/client";

export type SessionState = {
  userId: string;
  email?: string;
  hotelId: number;
  hotelIds?: number[];
  role: "owner" | "receptionist";
  accessToken?: string;
  isVerified?: boolean;
};

type SessionContextValue = {
  session: SessionState;
  login: (partial: Partial<SessionState>) => void;
  logout: () => void;
  setHotelId: (hotelId: number) => void;
  setRole: (role: SessionState["role"]) => void;
  authHeaders: Record<string, string>;
};

const STORAGE_KEY = "hotel-pms-session";
const DEFAULT_SESSION: SessionState = { userId: "guest", hotelId: 1, role: "owner" };

const SessionContext = createContext<SessionContextValue | null>(null);

const safeHotelId = (value?: number | string | null): number => {
  const parsed = typeof value === "string" ? parseInt(value, 10) : value;
  return Number.isInteger(parsed) && (parsed as number) > 0 ? (parsed as number) : 1;
};

const loadSession = (): SessionState => DEFAULT_SESSION;

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<SessionState>(() => loadSession());

  // Always require re-login on page reload: clear any stale persisted session.
  useEffect(() => {
    setSession(DEFAULT_SESSION);
    if (typeof localStorage !== "undefined") {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const login = (partial: Partial<SessionState>) => {
    setSession((prev) => ({
      userId: partial.userId?.trim() || prev.userId || DEFAULT_SESSION.userId,
      email: partial.email ?? partial.userId ?? prev.email,
      hotelId: safeHotelId(partial.hotelId ?? prev.hotelId),
      role: partial.role ?? prev.role ?? DEFAULT_SESSION.role,
      accessToken: partial.accessToken ?? prev.accessToken,
      isVerified: partial.isVerified ?? prev.isVerified ?? false
    }));
  };

  const logout = () => {
    setSession((prev) => ({
      userId: DEFAULT_SESSION.userId,
      email: undefined,
      hotelId: safeHotelId(prev.hotelId),
      role: DEFAULT_SESSION.role,
      accessToken: undefined,
      isVerified: false
    }));
  };

  const setHotelId = (hotelId: number) => setSession((prev) => ({ ...prev, hotelId: safeHotelId(hotelId) }));
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
