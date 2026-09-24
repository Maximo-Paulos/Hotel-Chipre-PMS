import { apiFetch, type SessionLike } from "./client";

export type HotelRoleCode = string;
export type HotelRoleTemplate = "manager" | "receptionist" | "housekeeping";

export type HotelRole = {
  code: HotelRoleCode;
  name: string;
  kind: "builtin" | "custom";
  base_role: string | null;
  is_active: boolean;
  assigned_count: number;
  pending_invitation_count: number;
  permission_count: number;
  version: number;
};

export type HotelRolesResponse = { roles: HotelRole[] };
export type CreateHotelRolePayload = { name: string; base_role: HotelRoleTemplate };
export type RenameHotelRolePayload = { name: string; expected_version: number };

export const hotelRolesQueryKey = (hotelId?: number | null) => ["hotel-roles", hotelId] as const;

export const fetchHotelRoles = (session?: SessionLike) =>
  apiFetch<HotelRolesResponse>("/api/roles", { session });

export const createHotelRole = (payload: CreateHotelRolePayload, session?: SessionLike) =>
  apiFetch<unknown>("/api/roles", { method: "POST", data: payload, session });

export const renameHotelRole = (
  code: HotelRoleCode,
  payload: RenameHotelRolePayload,
  session?: SessionLike
) =>
  apiFetch<unknown>(`/api/roles/${encodeURIComponent(code)}`, {
    method: "PATCH",
    data: payload,
    session
  });

export const archiveHotelRole = (
  code: HotelRoleCode,
  expectedVersion: number,
  session?: SessionLike
) =>
  apiFetch<unknown>(`/api/roles/${encodeURIComponent(code)}?expected_version=${encodeURIComponent(String(expectedVersion))}`, {
    method: "DELETE",
    session
  });
