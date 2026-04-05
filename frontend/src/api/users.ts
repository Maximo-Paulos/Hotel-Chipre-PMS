import { apiFetch, type SessionLike } from "./client";
import { type UserInfo } from "./auth";

export type InvitePayload = {
  email: string;
  role: "owner" | "co_owner" | "manager" | "housekeeping";
  password?: string;
};

export const listUsers = (session?: SessionLike) => apiFetch<UserInfo[]>("/api/users/", { session });

export const inviteUser = (payload: InvitePayload, session?: SessionLike) =>
  apiFetch<UserInfo>("/api/users/invite", { method: "POST", data: payload, session });

export const revokeUser = (userId: number, session?: SessionLike) =>
  apiFetch<void>(`/api/users/${userId}`, { method: "DELETE", session });
