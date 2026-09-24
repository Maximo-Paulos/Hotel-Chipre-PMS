import { apiFetch, type SessionLike } from "./client";
import { type AuthUser as UserInfo } from "./auth";

export type InvitePayload = {
  email: string;
  role: string;
  password?: string;
  alias?: string | null;
};

export type EmailDeliveryStatus = "sent" | "failed" | "not_configured";

export type UserAliasEntry = {
  user_id: number;
  email: string;
  role: InvitePayload["role"];
  status: string;
  alias: string | null;
};

export type InviteResponse = {
  user: UserInfo;
  invitation_id: number;
  invite_token: string;
  accept_url: string;
  email_delivery: EmailDeliveryStatus;
};

export const listUsers = (session?: SessionLike) => apiFetch<UserInfo[]>("/api/users/", { session });

export const inviteUser = (payload: InvitePayload, session?: SessionLike) =>
  apiFetch<InviteResponse>("/api/users/invite", {
    method: "POST",
    data: payload,
    session
  });

export const resendInvitation = (invitationId: number, session?: SessionLike) =>
  apiFetch<InviteResponse>(`/api/users/invitations/${invitationId}/resend`, {
    method: "POST",
    session
  });

export const listUserAliases = (session?: SessionLike) =>
  apiFetch<{ items: UserAliasEntry[] }>("/api/users/aliases", { session });

export const updateUserAlias = (userId: number, alias: string | null, session?: SessionLike) =>
  apiFetch<UserAliasEntry>(`/api/users/${userId}/alias`, {
    method: "PATCH",
    data: { alias },
    session
  });

export const revokeUser = (userId: number, session?: SessionLike) =>
  apiFetch<void>(`/api/users/${userId}`, { method: "DELETE", session });

export const updateUserRole = (userId: number, role: InvitePayload["role"], session?: SessionLike) =>
  apiFetch<UserInfo>(`/api/users/${userId}/role`, { method: "PATCH", data: { role }, session });
