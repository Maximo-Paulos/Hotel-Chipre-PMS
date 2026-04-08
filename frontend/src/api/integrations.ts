import { apiFetch, type SessionLike } from "./client";

export type IntegrationCatalog = {
  id: number;
  provider: string;
  display_name: string;
  auth_type: "oauth_code" | "api_key" | "signature" | "bearer_token" | string;
  scopes?: string | null;
  doc_url?: string | null;
};

export type IntegrationConnection = {
  id: number;
  integration: IntegrationCatalog;
  status: "connected" | "pending" | "error" | "revoked";
  expires_at?: string | null;
  last_checked_at?: string | null;
  last_error?: string | null;
  account_label?: string | null;
};

export type IntegrationStatus = {
  catalog: IntegrationCatalog[];
  connections: IntegrationConnection[];
};

export const fetchIntegrations = (session?: SessionLike) =>
  apiFetch<IntegrationStatus>("/api/integrations", { session });

export const connectIntegration = (id: number, payload?: Record<string, unknown>, session?: SessionLike) =>
  apiFetch<{ redirect_url?: string | null; status: string }>(`/api/integrations/${id}/connect`, {
    method: "POST",
    data: { payload },
    session,
  });

export const finalizeIntegrationOAuth = (id: number, code: string, session?: SessionLike) =>
  apiFetch<{ status: string }>(`/api/integrations/${id}/callback?code=${encodeURIComponent(code)}`, {
    method: "GET",
    session,
  });

export const revokeIntegration = (id: number, session?: SessionLike) =>
  apiFetch<{ status: string }>(`/api/integrations/${id}/revoke`, { method: "POST", session });

export const refreshIntegration = (id: number, session?: SessionLike) =>
  apiFetch<{ status: string; message: string; last_checked_at?: string | null; last_error?: string | null }>(
    `/api/integrations/${id}/refresh`,
    { method: "POST", session },
  );
