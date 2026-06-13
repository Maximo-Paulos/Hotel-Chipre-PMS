import { apiFetch, type SessionLike } from "./client";

export type ApiKeyPurpose = "whatsapp_bot" | "web_engine" | "channel_manager" | "reporting" | "other";

export type HotelApiKey = {
  id: number;
  hotel_id: number;
  name: string;
  purpose: ApiKeyPurpose;
  key_prefix: string;
  is_active: boolean;
  last_used_at?: string | null;
  expires_at?: string | null;
  created_at: string;
  revoked_at?: string | null;
};

export type HotelApiKeyIssued = HotelApiKey & {
  secret: string;
};

export type IssueHotelApiKeyPayload = {
  name: string;
  purpose: ApiKeyPurpose;
  expires_at?: string | null;
};

export const listApiKeys = (session?: SessionLike) =>
  apiFetch<HotelApiKey[]>("/api/hotel-api-keys", { session });

export const issueApiKey = (payload: IssueHotelApiKeyPayload, session?: SessionLike) =>
  apiFetch<HotelApiKeyIssued>("/api/hotel-api-keys", {
    method: "POST",
    data: payload,
    session
  });

export const revokeApiKey = (keyId: number, session?: SessionLike) =>
  apiFetch<HotelApiKey>(`/api/hotel-api-keys/${keyId}/revoke`, {
    method: "POST",
    session
  });
