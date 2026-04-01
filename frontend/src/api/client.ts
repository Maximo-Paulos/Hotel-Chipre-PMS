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

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") || "";

const normalizeHotelId = (hotelId?: number | string | null) => {
  const parsed = typeof hotelId === "string" ? parseInt(hotelId, 10) : hotelId;
  return Number.isInteger(parsed) && (parsed as number) > 0 ? (parsed as number) : 1;
};

export const buildAuthHeaders = (session?: SessionLike): Record<string, string> => {
  const hotelId = normalizeHotelId(session?.hotelId);
  const userId = session?.userId || "guest";
  const headers: Record<string, string> = {
    "X-Hotel-Id": String(hotelId),
    "X-User-Id": userId
  };
  if (session?.accessToken) {
    headers.Authorization = `Bearer ${session.accessToken}`;
  }
  return headers;
};

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  data?: unknown;
  headers?: HeadersInit;
  signal?: AbortSignal;
  session?: SessionLike;
};

export async function apiFetch<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", data, headers, signal, session } = options;

  const finalHeaders: HeadersInit = {
    "Content-Type": "application/json",
    ...buildAuthHeaders(session),
    ...headers
  };

  const response = await fetch(`${API_BASE}${path}`, {
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
