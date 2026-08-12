import { apiFetch, type SessionLike } from "./client";

export type PermissionRole = "owner" | "co_owner" | "manager" | "receptionist" | "housekeeping";

export type PermissionCell = {
  allowed: boolean;
  source: "default" | "override" | "deny" | string;
  description: string;
};

export type PermissionMatrix = Record<PermissionRole, Record<string, PermissionCell>>;

export type PermissionMatrixResponse = {
  hotel_id: number;
  matrix: PermissionMatrix;
};

export type PermissionOverridePayload = {
  role: PermissionRole;
  permission_code: string;
  allowed: boolean;
};

export type PermissionOverrideResponse = {
  hotel_id: number;
  role: PermissionRole;
  permission_code: string;
  allowed: boolean;
  updated_by_user_id?: number | null;
  updated_at?: string | null;
};

export type EffectivePermissionsResponse = {
  hotel_id: number;
  role: PermissionRole;
  permissions: string[];
};

export const fetchEffectivePermissions = (session?: SessionLike) =>
  apiFetch<EffectivePermissionsResponse>("/api/permissions/effective", { session });

export const fetchPermissionMatrix = (session?: SessionLike) =>
  apiFetch<PermissionMatrixResponse>("/api/permissions/matrix", { session });

export const updatePermissionOverride = (payload: PermissionOverridePayload, session?: SessionLike) =>
  apiFetch<PermissionOverrideResponse>("/api/permissions/override", {
    method: "PUT",
    data: payload,
    session
  });
