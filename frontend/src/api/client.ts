import { broadcastDomainChange } from "../sync/crossTabSync";

export type SessionLike = {
  hotelId?: number | null;
  userId?: string | null;
  accessToken?: string | null;
  csrfToken?: string | null;
};

export type AuthResponsePayload = {
  access_token: string;
  token_type?: string;
  hotel_id: number;
  hotel_ids?: number[];
  user: {
    id: number;
    email: string;
    role: string;
    is_verified: boolean;
    is_active: boolean;
    permissions?: string[];
  };
  permissions?: string[];
  requires_verification?: boolean;
  csrf_token?: string | null;
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
//
// Capacitor builds: the iOS Simulator can reach the host Mac's 127.0.0.1 directly, so this
// default (or a VITE_API_URL override pointed at a local dev backend) works for `npx cap run ios`.
// A physical device or a real store-submission build CANNOT reach 127.0.0.1 — it must be built
// with VITE_API_URL set to the deployed backend (e.g. https://<render-service>.onrender.com/api,
// per APP_BASE_URL's production value in .env.example) before `npm run build && npx cap sync`.
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
  // Let the request interceptor see an expired bearer token and refresh it
  // from the browser session. This is intentionally different from the JWT
  // expiry helper: an expired access token does not mean the cookie session is
  // gone.
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

const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

let clientSession: SessionLike | null = null;
let authResponseHandler: ((response: AuthResponsePayload) => void) | null = null;
let unauthorizedHandler: (() => void) | null = null;
let refreshInFlight: Promise<AuthResponsePayload> | null = null;
let unauthorizedHandled = false;

export const setClientSession = (session?: SessionLike | null) => {
  clientSession = session ? { ...session } : null;
  if (clientSession?.accessToken) unauthorizedHandled = false;
};

export const setAuthResponseHandler = (handler: ((response: AuthResponsePayload) => void) | null) => {
  authResponseHandler = handler;
  return () => {
    if (authResponseHandler === handler) authResponseHandler = null;
  };
};

export const setUnauthorizedHandler = (handler: (() => void) | null) => {
  unauthorizedHandler = handler;
  return () => {
    if (unauthorizedHandler === handler) unauthorizedHandler = null;
  };
};

// Clear the in-memory session and redirect to /login. Guarded so a burst of
// concurrent 401s only triggers one navigation.
const handleUnauthorized = () => {
  if (unauthorizedHandled || typeof window === "undefined") return;
  unauthorizedHandled = true;
  clientSession = null;
  unauthorizedHandler?.();
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

const mergeSession = (session?: SessionLike | null): SessionLike | null => {
  if (!clientSession && !session) return null;
  const sessionHasCsrfToken = Boolean(session && Object.prototype.hasOwnProperty.call(session, "csrfToken"));
  return {
    ...(clientSession ?? {}),
    ...(session ?? {}),
    csrfToken: sessionHasCsrfToken ? session?.csrfToken ?? null : clientSession?.csrfToken ?? null
  };
};

const requestHeaders = (method: string, session: SessionLike | null, headers?: HeadersInit) => {
  const finalHeaders = new Headers();
  finalHeaders.set("Content-Type", "application/json");
  Object.entries(buildAuthHeaders(session ?? undefined)).forEach(([key, value]) => finalHeaders.set(key, value));

  const csrfToken = session?.csrfToken?.trim();
  if (MUTATING_METHODS.has(method) && csrfToken) {
    finalHeaders.set("X-CSRF-Token", csrfToken);
  }

  if (headers) {
    new Headers(headers).forEach((value, key) => finalHeaders.set(key, value));
  }
  return finalHeaders;
};

const isPublicAuthPath = (path: string) =>
  [
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/google",
    "/api/auth/request-verify",
    "/api/auth/verify-email",
    "/api/auth/request-reset",
    "/api/auth/reset-password",
    "/api/auth/session/refresh",
    "/api/auth/logout"
  ].some((publicPath) => path === publicPath || path.startsWith(`${publicPath}?`));

const makeApiError = (response: Response, payload: unknown) => {
  const detail =
    typeof payload === "object" && payload !== null && "detail" in (payload as Record<string, unknown>)
      ? (payload as Record<string, unknown>).detail
      : undefined;
  const message = formatErrorDetail(detail) || response.statusText || "Request failed";
  return new ApiError(response.status, message, payload);
};

const isAuthResponsePayload = (payload: unknown): payload is AuthResponsePayload => {
  if (!payload || typeof payload !== "object") return false;
  const candidate = payload as Partial<AuthResponsePayload>;
  return Boolean(
    typeof candidate.access_token === "string" &&
      typeof candidate.hotel_id === "number" &&
      candidate.user &&
      typeof candidate.user === "object" &&
      typeof candidate.user.email === "string"
  );
};

export async function refreshSession(session?: SessionLike): Promise<AuthResponsePayload> {
  if (refreshInFlight) return refreshInFlight;

  const refreshSessionState = mergeSession(session);
  const promise = (async () => {
    const csrfToken = refreshSessionState?.csrfToken?.trim();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (csrfToken) headers["X-CSRF-Token"] = csrfToken;

    const response = await fetch(buildUrl("/api/auth/session/refresh"), {
      method: "POST",
      headers,
      credentials: "include"
    });
    const text = await response.text();
    const payload = text ? safeJson(text) : null;
    if (!response.ok) throw makeApiError(response, payload);
    if (!isAuthResponsePayload(payload)) {
      throw new ApiError(500, "La respuesta de renovación de sesión es inválida", payload);
    }
    return payload;
  })().finally(() => {
    refreshInFlight = null;
  });

  refreshInFlight = promise;
  return promise;
}

async function requestWithRefresh<T>(path: string, options: RequestOptions, allowRefresh: boolean): Promise<T> {
  const { method = "GET", data, headers, signal, session } = options;
  const requestSession = mergeSession(session);
  const response = await fetch(buildUrl(path), {
    method,
    headers: requestHeaders(method, requestSession, headers),
    body: data !== undefined ? JSON.stringify(data) : undefined,
    signal,
    credentials: "include"
  });

  const text = await response.text();
  const payload = text ? safeJson(text) : null;

  if (!response.ok) {
    const error = makeApiError(response, payload);
    const canRefresh =
      allowRefresh &&
      response.status === 401 &&
      Boolean(requestSession?.accessToken) &&
      !isPublicAuthPath(path);

    if (canRefresh) {
      try {
        const refreshed = await refreshSession(requestSession ?? undefined);
        const refreshedSession: SessionLike = {
          ...(requestSession ?? {}),
          accessToken: refreshed.access_token,
          csrfToken: refreshed.csrf_token ?? null
        };
        setClientSession(refreshedSession);
        authResponseHandler?.(refreshed);
        return requestWithRefresh(path, { ...options, session: refreshedSession }, false);
      } catch (refreshError) {
        if (refreshError instanceof ApiError && refreshError.status >= 400 && refreshError.status < 500) {
          handleUnauthorized();
        }
      }
    }

    if (response.status === 401 && requestSession?.accessToken && !allowRefresh) {
      handleUnauthorized();
    }
    throw error;
  }

  if (MUTATING_METHODS.has(method) && requestSession?.hotelId) {
    broadcastDomainChange(requestSession.hotelId, path);
  }

  return payload as T;
}

export async function apiFetch<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  return requestWithRefresh(path, options, true);
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
