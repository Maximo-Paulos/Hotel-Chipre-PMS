import { broadcastDomainChange } from "../sync/crossTabSync";

export type SessionLike = {
  hotelId?: number | null;
  userId?: string | null;
  accessToken?: string | null;
  csrfToken?: string | null;
};

export type ActionStepUpChallenge = {
  permissionCode: string;
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  path: string;
};

type ActionStepUpHandler = (
  challenge: ActionStepUpChallenge,
  session: SessionLike | null,
  signal?: AbortSignal
) => Promise<string | null>;

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
    password_login_enabled?: boolean;
    google_login_enabled?: boolean;
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
export const API_BASE =
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
let refreshInFlight: { session: SessionLike | null; promise: Promise<AuthResponsePayload> } | null = null;
let unauthorizedHandled = false;
let actionStepUpHandler: ActionStepUpHandler | null = null;
let actionStepUpQueue: Promise<void> = Promise.resolve();

const normalizedSessionUserId = (userId?: string | null) => userId?.trim().toLowerCase() ?? "";

const hasSameSessionIdentity = (left?: SessionLike | null, right?: SessionLike | null) => {
  const leftUserId = normalizedSessionUserId(left?.userId);
  const rightUserId = normalizedSessionUserId(right?.userId);
  const leftHotelId = normalizeHotelId(left?.hotelId);
  const rightHotelId = normalizeHotelId(right?.hotelId);
  return Boolean(leftUserId && rightUserId && leftHotelId && rightHotelId && leftUserId === rightUserId && leftHotelId === rightHotelId);
};

const hasSameSession = (left?: SessionLike | null, right?: SessionLike | null) => {
  const leftToken = left?.accessToken?.trim();
  const rightToken = right?.accessToken?.trim();
  return Boolean(leftToken && rightToken && leftToken === rightToken && hasSameSessionIdentity(left, right));
};

const isCurrentSession = (session?: SessionLike | null) => hasSameSession(session, clientSession);

const isRefreshResponseForSession = (response: AuthResponsePayload, session: SessionLike) =>
  normalizedSessionUserId(response.user.email) === normalizedSessionUserId(session.userId) &&
  normalizeHotelId(response.hotel_id) === normalizeHotelId(session.hotelId);

const isSameRefreshContext = (left: SessionLike | null, right: SessionLike | null) =>
  left === null || right === null ? left === right : hasSameSession(left, right);

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

export const setActionStepUpHandler = (handler: ActionStepUpHandler | null) => {
  actionStepUpHandler = handler;
  return () => {
    if (actionStepUpHandler === handler) actionStepUpHandler = null;
  };
};

const requestActionStepUpTicket = (
  challenge: ActionStepUpChallenge,
  session: SessionLike | null,
  signal?: AbortSignal
): Promise<string | null> => {
  const queuedRequest = actionStepUpQueue.then(() => {
    if (signal?.aborted || !isCurrentSession(session)) return null;
    const handler = actionStepUpHandler;
    return handler ? handler(challenge, session, signal) : null;
  });
  // Keep the queue alive even when a UI handler rejects unexpectedly. The
  // original protected request will surface its own 428 in that case.
  actionStepUpQueue = queuedRequest.then(
    () => undefined,
    () => undefined
  );
  return queuedRequest;
};

// Clear the in-memory session and redirect to /login. Guarded so a burst of
// concurrent 401s only triggers one navigation.
const handleUnauthorized = (expectedSession: SessionLike | null) => {
  if (unauthorizedHandled || typeof window === "undefined" || !isCurrentSession(expectedSession)) return;
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
    "/api/auth/login/mfa",
    "/api/auth/register",
    "/api/auth/google",
    "/api/auth/providers",
    "/api/auth/request-verify",
    "/api/auth/verify-email",
    "/api/auth/request-reset",
    "/api/auth/reset-password",
    "/api/auth/session/refresh",
    "/api/auth/logout"
  ].some((publicPath) => path === publicPath || path.startsWith(`${publicPath}?`));

const isActionStepUpPath = (path: string) => {
  const pathname = path.split(/[?#]/, 1)[0].replace(/\/+$/, "");
  return pathname === "/api/auth/step-up" || pathname === "/auth/step-up";
};

const parseActionStepUpChallenge = (payload: unknown): ActionStepUpChallenge | null => {
  if (!payload || typeof payload !== "object") return null;
  const detail = (payload as Record<string, unknown>).detail;
  if (!detail || typeof detail !== "object") return null;

  const value = detail as Record<string, unknown>;
  const methods = ["GET", "POST", "PUT", "PATCH", "DELETE"] as const;
  if (
    value.code !== "STEP_UP_REQUIRED" ||
    typeof value.permission_code !== "string" ||
    !value.permission_code.trim() ||
    typeof value.method !== "string" ||
    !methods.includes(value.method as (typeof methods)[number]) ||
    typeof value.path !== "string" ||
    !value.path.startsWith("/api/") ||
    value.path.startsWith("//") ||
    value.path.includes("?") ||
    value.path.includes("#") ||
    value.path.includes("\\") ||
    Array.from(value.path).some((character) => character.charCodeAt(0) < 32)
  ) {
    return null;
  }

  return {
    permissionCode: value.permission_code,
    method: value.method as ActionStepUpChallenge["method"],
    path: value.path
  };
};

const isStepUpTotpRejection = (path: string, payload: unknown) => {
  if (!isActionStepUpPath(path) || !payload || typeof payload !== "object") return false;
  const detail = (payload as Record<string, unknown>).detail;
  // The current backend uses 401 for both invalid TOTP and invalid sessions.
  // Do not refresh/logout on a rejected TOTP; let the dialog ask for another.
  return detail === "Codigo MFA invalido o ya utilizado";
};

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
  const refreshSessionState = mergeSession(session);
  if (refreshInFlight && isSameRefreshContext(refreshInFlight.session, refreshSessionState)) {
    return refreshInFlight.promise;
  }

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
  })();

  const trackedPromise = promise.finally(() => {
    if (refreshInFlight?.promise === trackedPromise) refreshInFlight = null;
  });
  refreshInFlight = {
    session: refreshSessionState ? { ...refreshSessionState } : null,
    promise: trackedPromise
  };
  return trackedPromise;
}

async function requestWithRefresh<T>(
  path: string,
  options: RequestOptions,
  allowRefresh: boolean,
  allowActionStepUp = true,
  actionStepUpTicket?: string
): Promise<T> {
  const { method = "GET", data, headers, signal, session } = options;
  const requestSession = mergeSession(session);
  const fetchHeaders = requestHeaders(method, requestSession, headers);
  if (actionStepUpTicket) fetchHeaders.set("X-Action-Step-Up-Ticket", actionStepUpTicket);
  const response = await fetch(buildUrl(path), {
    method,
    headers: fetchHeaders,
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
      isCurrentSession(requestSession) &&
      !isPublicAuthPath(path) &&
      !isStepUpTotpRejection(path, payload);

    if (canRefresh) {
      let refreshed: AuthResponsePayload | null = null;
      try {
        refreshed = await refreshSession(requestSession ?? undefined);
      } catch (refreshError) {
        if (refreshError instanceof ApiError && refreshError.status >= 400 && refreshError.status < 500) {
          handleUnauthorized(requestSession);
        }
      }

      if (refreshed && isRefreshResponseForSession(refreshed, requestSession!)) {
        const activeSession = clientSession;
        let refreshedSession: SessionLike;

        if (isCurrentSession(requestSession)) {
          refreshedSession = {
            ...(requestSession ?? {}),
            accessToken: refreshed.access_token,
            csrfToken: refreshed.csrf_token ?? null
          };
          setClientSession(refreshedSession);
          authResponseHandler?.(refreshed);
        } else if (
          hasSameSessionIdentity(requestSession, activeSession) &&
          activeSession?.accessToken?.trim() === refreshed.access_token.trim()
        ) {
          // Another request sharing this exact refresh already applied it.
          refreshedSession = activeSession;
        } else {
          // Logout, account switch, or hotel switch won the race. Do not let
          // the old refresh response restore or overwrite that session.
          throw error;
        }

        return requestWithRefresh(path, { ...options, session: refreshedSession }, false, allowActionStepUp);
      }
    }

    if (response.status === 401 && requestSession?.accessToken && !allowRefresh) {
      handleUnauthorized(requestSession);
    }

    const challenge = response.status === 428 ? parseActionStepUpChallenge(payload) : null;
    if (
      allowActionStepUp &&
      challenge &&
      Boolean(requestSession?.accessToken) &&
      isCurrentSession(requestSession) &&
      !isPublicAuthPath(path) &&
      !isActionStepUpPath(path)
    ) {
      let ticket: string | null = null;
      try {
        ticket = await requestActionStepUpTicket(challenge, requestSession, signal);
      } catch {
        // If the dialog fails or unmounts, preserve the backend's original
        // precondition response instead of replacing it with a UI error.
        throw error;
      }
      if (!ticket || !isCurrentSession(requestSession)) throw error;

      return requestWithRefresh(path, options, allowRefresh, false, ticket);
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
