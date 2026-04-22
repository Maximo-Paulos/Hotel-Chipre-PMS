import { ApiError, buildUrl } from "../api/client";

type RequestOptions = {
  method?: "GET" | "HEAD" | "POST" | "PUT" | "PATCH" | "DELETE";
  data?: unknown;
  headers?: Record<string, string>;
};

const CSRF_COOKIE_NAME = "master_admin_csrf";
let masterAdminCsrfToken: string | null = null;

const readCookie = (name: string): string | null => {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
};

export const setMasterAdminCsrfToken = (token: string | null) => {
  masterAdminCsrfToken = typeof token === "string" && token.trim() ? token.trim() : null;
};

export const clearMasterAdminCsrfToken = () => {
  masterAdminCsrfToken = null;
};

const safeJson = (text: string): unknown => {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
};

export async function masterAdminFetch<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", data, headers = {} } = options;
  const finalHeaders: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
    ...headers
  };

  if (method !== "GET" && method !== "HEAD") {
    const csrf = masterAdminCsrfToken || readCookie(CSRF_COOKIE_NAME);
    if (csrf) {
      finalHeaders["X-CSRF-Token"] = csrf;
    }
  }

  const response = await fetch(buildUrl(path), {
    method,
    credentials: "include",
    headers: finalHeaders,
    body: data !== undefined ? JSON.stringify(data) : undefined
  });

  const text = await response.text();
  const payload = text ? safeJson(text) : null;

  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in (payload as Record<string, unknown>)
        ? (payload as Record<string, unknown>).detail
        : undefined;
    const message = typeof detail === "string" ? detail : response.statusText || "Request failed";
    throw new ApiError(response.status, message, payload);
  }

  return payload as T;
}

export type MasterAdminUser = {
  id: number;
  email: string;
  role: string;
  is_active: boolean;
  is_verified: boolean;
};

export type MasterAdminLoginResponse = {
  user: MasterAdminUser;
  csrf_token: string;
  expires_at: string;
};

export type MasterBillingPolicy = {
  policy_key: string;
  enabled: boolean;
  allow_active: boolean;
  allow_trialing: boolean;
  exempt_hotel_ids: number[];
  exempt_user_ids: number[];
  notes?: string | null;
  updated_at?: string | null;
  updated_by_user_id?: number | null;
};

export type MasterHotelRow = {
  hotel_id: number;
  hotel_name: string;
  owner_email: string | null;
  plan: string;
  status: string;
  can_write: boolean;
  reason: string;
  room_limit: number | null;
  staff_limit: number | null;
  exempt: boolean;
  updated_at: string | null;
};

export type MasterDashboardSummary = {
  operator: MasterAdminUser;
  counts: {
    hotels: number;
    active_subscriptions: number;
    trialing: number;
    past_due: number;
  };
  policy: MasterBillingPolicy;
  recent_events: Array<{
    id: number;
    action: string;
    outcome: string;
    target_type: string | null;
    target_id: string | null;
    created_at: string;
  }>;
};

export type MasterEmailStatus = {
  configured: boolean;
  status: string;
  provider: string;
  connected_account_email?: string | null;
  connected_account_name?: string | null;
  last_checked_at?: string | null;
  last_error?: string | null;
  updated_at?: string | null;
};

export type MasterEmailConnectResponse = {
  redirect_url?: string | null;
  status: string;
};

export type MasterStripeConfig = {
  configured: boolean;
  enabled: boolean;
  account_id?: string | null;
  account_name?: string | null;
  webhook_secret_configured: boolean;
  last_checked_at?: string | null;
  last_error?: string | null;
};
