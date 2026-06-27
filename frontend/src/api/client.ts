export type SessionLike = {
  hotelId?: number | null;
  userId?: string | null;
  accessToken?: string | null;
};

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(status: number, message: string, payload?: unknown) {
    super(message);
    this.status = status;
    this.payload = payload;
  }
}

// Default to local backend so the dev/preview build doesn't hit the Vite preview origin.
// Use 8040 to avoid conflicts with other local services; override with VITE_API_URL if set.
const DEFAULT_API_BASE = "http://127.0.0.1:8040/api";
const API_BASE =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") || DEFAULT_API_BASE;

const normalizeHotelId = (hotelId?: number | string | null) => {
  const parsed = typeof hotelId === "string" ? parseInt(hotelId, 10) : hotelId;
  return Number.isInteger(parsed) && (parsed as number) > 0 ? (parsed as number) : null;
};

// Decode a JWT's `exp` claim (seconds since epoch) without verifying the
// signature. Returns null when the token is malformed or carries no exp.
const jwtExpMs = (token: string): number | null => {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return typeof payload?.exp === "number" ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
};

export const isTokenExpired = (token?: string | null): boolean => {
  if (!token) return false;
  const expMs = jwtExpMs(token);
  // 10s skew so a token about to expire isn't treated as valid for a request
  // that would arrive after it lapses.
  return expMs !== null && expMs <= Date.now() + 10_000;
};

export const hasValidSession = (session?: SessionLike) => {
  const hotelId = normalizeHotelId(session?.hotelId);
  const userId = typeof session?.userId === "string" ? session.userId.trim() : "";
  const accessToken = typeof session?.accessToken === "string" ? session.accessToken.trim() : "";
  if (isTokenExpired(accessToken)) return false;
  return Boolean(hotelId && userId && accessToken && userId !== "guest");
};

export const buildAuthHeaders = (session?: SessionLike): Record<string, string> => {
  if (!hasValidSession(session)) {
    return {};
  }
  const hotelId = normalizeHotelId(session?.hotelId);
  const userId = session?.userId?.trim();
  const accessToken = session?.accessToken?.trim();
  if (!hotelId || !userId || !accessToken) {
    return {};
  }
  const headers: Record<string, string> = {
    "X-Hotel-Id": String(hotelId),
    "X-User-Id": userId
  };
  headers.Authorization = `Bearer ${accessToken}`;
  return headers;
};

// Clear the persisted session and redirect to /login. Guarded so a burst of
// concurrent 401s only triggers one navigation.
let unauthorizedHandled = false;
const handleUnauthorized = () => {
  if (unauthorizedHandled || typeof window === "undefined") return;
  unauthorizedHandled = true;
  try {
    localStorage.removeItem("hotel-pms-session");
  } catch {
    /* ignore */
  }
  if (window.location.pathname !== "/login") {
    window.location.assign("/login?expired=1");
  }
};

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  data?: unknown;
  headers?: HeadersInit;
  signal?: AbortSignal;
  session?: SessionLike;
};

export const buildUrl = (path: string) => {
  const leading = path.startsWith("/") ? path : `/${path}`;
  // Avoid duplicating /api when both the base and path contain it.
  if (API_BASE.endsWith("/api") && leading.startsWith("/api/")) {
    return `${API_BASE}${leading.replace(/^\/api/, "")}`;
  }
  return `${API_BASE}${leading}`;
};

export async function apiFetch<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", data, headers, signal, session } = options;

  const finalHeaders: HeadersInit = {
    "Content-Type": "application/json",
    ...buildAuthHeaders(session),
    ...headers
  };

  const response = await fetch(buildUrl(path), {
    method,
    headers: finalHeaders,
    body: data !== undefined ? JSON.stringify(data) : undefined,
    signal
  });

  const text = await response.text();
  const payload = text ? safeJson(text) : null;

  if (!response.ok) {
    const detail = typeof payload === "object" && payload !== null && "detail" in (payload as Record<string, unknown>)
      ? (payload as Record<string, unknown>).detail
      : undefined;
    const message = formatErrorDetail(detail) || response.statusText || "Request failed";
    // An expired/invalid token leaves a stale session in localStorage that
    // would otherwise render every protected section as broken (repeated 401s).
    // Clear it and bounce to login so the user can re-authenticate cleanly.
    if (response.status === 401 && buildAuthHeaders(session).Authorization) {
      handleUnauthorized();
    }
    throw new ApiError(response.status, message, payload);
  }

  return payload as T;
}

// FastAPI returns `detail` as a string for HTTPException, but as an array of
// {loc, msg, type} objects for Pydantic 422 validation errors. Render both so
// the UI shows the real backend validation message instead of "Request failed".
const formatErrorDetail = (detail: unknown): string | null => {
  if (typeof detail === "string") return detail.trim() || null;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const rec = item as Record<string, unknown>;
          const msg = typeof rec.msg === "string" ? rec.msg : null;
          const loc = Array.isArray(rec.loc)
            ? rec.loc.filter((part) => part !== "body").join(".")
            : null;
          if (msg && loc) return `${loc}: ${msg}`;
          return msg;
        }
        return null;
      })
      .filter((m): m is string => Boolean(m));
    return messages.length ? messages.join(" · ") : null;
  }
  if (detail && typeof detail === "object") {
    const rec = detail as Record<string, unknown>;
    if (typeof rec.msg === "string") return rec.msg;
  }
  return null;
};

const safeJson = (text: string): unknown => {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
};
