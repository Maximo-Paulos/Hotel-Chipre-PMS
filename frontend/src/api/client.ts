import type { HeadersInit } from "react";

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

export const hasValidSession = (session?: SessionLike) => {
  const hotelId = normalizeHotelId(session?.hotelId);
  const userId = typeof session?.userId === "string" ? session.userId.trim() : "";
  const accessToken = typeof session?.accessToken === "string" ? session.accessToken.trim() : "";
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
    const message = typeof detail === "string" ? detail : response.statusText || "Request failed";
    throw new ApiError(response.status, message, payload);
  }

  return payload as T;
}

const safeJson = (text: string): unknown => {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
};
