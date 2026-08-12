import { apiFetch, type SessionLike } from "./client";

export type SecurityOverview = {
  hotel_id: number;
  active_members: number;
  pending_invitations: number;
  security_events_24h: number;
  permission_denials_24h: number;
  session_timeout_minutes: number;
  current_user: {
    id: number;
    email: string;
    role: string;
    last_login?: string | null;
    token_version: number;
  };
};

export type SecurityEvent = {
  id: number;
  action: string;
  actor_user_id?: number | null;
  resource_type?: string | null;
  resource_id?: string | number | null;
  created_at: string;
};

export type SecurityEventsResponse = {
  hotel_id: number;
  events: SecurityEvent[];
};

export type RevokeAllSessionsResponse = {
  revoked: true;
  user_id: number;
  token_version: number;
  reauthentication_required: true;
};

export const getSecurityOverview = (session?: SessionLike) =>
  apiFetch<SecurityOverview>("/api/settings/security/overview", { session });

export const getSecurityEvents = (limit = 20, session?: SessionLike) =>
  apiFetch<SecurityEventsResponse>(`/api/settings/security/events?limit=${limit}`, { session });

export const revokeAllSessions = (session?: SessionLike) =>
  apiFetch<RevokeAllSessionsResponse>("/api/settings/security/revoke-all", { method: "POST", session });
