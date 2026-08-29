import { apiFetch, type SessionLike } from "./client";

export type PermissionRole = "owner" | "co_owner" | "manager" | "receptionist" | "housekeeping";

export type PermissionCatalogItem = {
  code: string;
  module: string;
  description: string;
  help_es: string;
  legacy_aliases: string[];
  locked: boolean;
  lock_reason: string | null;
  critical: boolean;
  step_up_required: boolean;
  delegable: boolean;
};

export type PermissionDetail = {
  allowed: boolean;
  source: "invariant" | "user_override" | "role_override" | "role_default" | "deny" | string;
  locked: boolean;
  lock_reason: string | null;
};

export type PermissionCell = {
  allowed: boolean;
  source: "default" | "override" | "deny" | string;
  description: string;
  module: string;
  help_es: string;
  locked?: boolean;
  lock_reason?: string | null;
};

export type PermissionMatrix = Record<PermissionRole, Record<string, PermissionCell>>;

export type PermissionProfileMatrix = Record<PermissionRole, Record<string, PermissionDetail & {
  description: string;
  module: string;
  help_es: string;
}>>;

export type PermissionMatrixResponse = {
  hotel_id: number;
  matrix: PermissionMatrix;
};

export type PermissionCatalogResponse = {
  hotel_id: number;
  permissions: PermissionCatalogItem[];
};

export type RolePermissionProfilesResponse = {
  hotel_id: number;
  matrix: PermissionProfileMatrix;
};

export type PermissionOverridePayload = {
  role: PermissionRole;
  permission_code: string;
  allowed: boolean;
  expected_version?: number;
};

export type PermissionOverrideResponse = {
  hotel_id: number;
  role: PermissionRole;
  permission_code: string;
  allowed: boolean;
  version: number;
  source: "role_override" | string;
  locked: boolean;
  updated_by_user_id?: number | null;
  updated_at?: string | null;
};

export type UserPermissionOverridePayload = {
  permission_code: string;
  allowed: boolean;
  expected_version?: number;
};

export type UserPermissionOverrideResponse = {
  hotel_id: number;
  user_id: number;
  role: PermissionRole;
  details: Record<string, PermissionDetail>;
};

export type UserPermissionMutationResponse = {
  hotel_id: number;
  user_id: number;
  role: PermissionRole;
  permission_code: string;
  allowed: boolean;
  version?: number;
  source: string;
  locked?: boolean;
  restored?: boolean;
  updated_by_user_id?: number | null;
  updated_at?: string | null;
};

export type VisibilityWindowHours = 12 | 24 | 48 | 72 | 168;

export type VisibilityWindow = {
  role: PermissionRole;
  past_hours: VisibilityWindowHours | null;
  future_hours: VisibilityWindowHours | null;
  updated_by_user_id: number | null;
  updated_at: string | null;
};

export type VisibilityWindowsResponse = {
  hotel_id: number;
  windows: VisibilityWindow[];
};

export type VisibilityWindowPayload = {
  role: PermissionRole;
  past_hours: VisibilityWindowHours | null;
  future_hours: VisibilityWindowHours | null;
};

export type RestoreRoleDefaultsResponse = {
  hotel_id: number;
  role: PermissionRole;
  restored: number;
};

export type RestoreRolePermissionResponse = {
  hotel_id: number;
  role: PermissionRole;
  permission_code: string;
  allowed: boolean;
  source: "role_default" | string;
  restored: boolean;
};

export type RestoreUserDefaultsResponse = {
  hotel_id: number;
  user_id: number;
  restored: number;
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

export const fetchPermissionCatalog = (session?: SessionLike) =>
  apiFetch<PermissionCatalogResponse>("/api/permissions/catalog", { session });

export const fetchRolePermissionProfiles = (session?: SessionLike) =>
  apiFetch<RolePermissionProfilesResponse>("/api/permissions/role-overrides", { session });

export const updatePermissionOverride = (payload: PermissionOverridePayload, session?: SessionLike) =>
  apiFetch<PermissionOverrideResponse>("/api/permissions/override", {
    method: "PUT",
    data: payload,
    session
  });

export const fetchVisibilityWindows = (session?: SessionLike) =>
  apiFetch<VisibilityWindowsResponse>("/api/permissions/visibility-windows", { session });

export const updateVisibilityWindow = (payload: VisibilityWindowPayload, session?: SessionLike) =>
  apiFetch<VisibilityWindow>("/api/permissions/visibility-windows", {
    method: "PUT",
    data: payload,
    session
  });

export const restoreRolePermissionOverride = (
  role: PermissionRole,
  permissionCode: string,
  expectedVersion: number,
  session?: SessionLike
) =>
  apiFetch<RestoreRolePermissionResponse>(
    `/api/permissions/role-overrides/${role}/${encodeURIComponent(permissionCode)}?expected_version=${expectedVersion}`,
    { method: "DELETE", session }
  );

export const restoreRoleDefaults = (role: PermissionRole, session?: SessionLike) =>
  apiFetch<RestoreRoleDefaultsResponse>(`/api/permissions/role-overrides/${role}`, { method: "DELETE", session });

export const fetchUserPermissionOverrides = (userId: number, session?: SessionLike) =>
  apiFetch<UserPermissionOverrideResponse>(`/api/permissions/user-overrides/${userId}`, { session });

export const updateUserPermissionOverride = (
  userId: number,
  payload: UserPermissionOverridePayload,
  session?: SessionLike
) =>
  apiFetch<UserPermissionMutationResponse>(`/api/permissions/user-overrides/${userId}`, {
    method: "PUT",
    data: payload,
    session
  });

export const restoreUserPermissionOverride = (
  userId: number,
  permissionCode: string,
  expectedVersion: number,
  session?: SessionLike
) =>
  apiFetch<UserPermissionMutationResponse>(
    `/api/permissions/user-overrides/${userId}/${encodeURIComponent(permissionCode)}?expected_version=${expectedVersion}`,
    { method: "DELETE", session }
  );

export const restoreUserDefaults = (userId: number, session?: SessionLike) =>
  apiFetch<RestoreUserDefaultsResponse>(`/api/permissions/user-overrides/${userId}`, { method: "DELETE", session });
