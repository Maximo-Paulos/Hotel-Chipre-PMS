import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import {
  fetchPermissionCatalog,
  fetchPermissionMatrix,
  fetchRolePermissionProfiles,
  fetchUserPermissionOverrides,
  fetchVisibilityWindows,
  restoreRoleDefaults,
  restoreRolePermissionOverride,
  restoreUserDefaults,
  restoreUserPermissionOverride,
  updatePermissionOverride,
  updateUserPermissionOverride,
  updateVisibilityWindow,
  type PermissionCatalogItem,
  type PermissionMatrixResponse,
  type BuiltinPermissionRole,
  type PermissionRole,
  type PermissionProfileMatrix,
  type PermissionOverrideResponse,
  type RestoreRoleDefaultsResponse,
  type RestoreRolePermissionResponse,
  type UserPermissionMutationResponse,
  type UserPermissionOverrideResponse,
  type VisibilityWindow,
  type VisibilityWindowHours
} from "../../api/permissions";
import { ApiError, hasValidSession } from "../../api/client";
import { InfoTip } from "../../components/InfoTip";
import { listUsers } from "../../api/users";
import type { AuthUser } from "../../api/auth";
import { useSession } from "../../state/session";
import { refreshAfterMutation } from "../../api/queryInvalidation";
import { useGuardedMutation } from "../../hooks/useGuardedMutation";
import {
  archiveHotelRole,
  createHotelRole,
  fetchHotelRoles,
  hotelRolesQueryKey,
  renameHotelRole,
  type CreateHotelRolePayload,
  type HotelRole,
  type HotelRoleTemplate,
  type HotelRolesResponse,
  type RenameHotelRolePayload
} from "../../api/roles";

const builtinRoleOrder: BuiltinPermissionRole[] = ["owner", "co_owner", "manager", "receptionist", "housekeeping"];

const builtinRoleLabels: Record<BuiltinPermissionRole, string> = {
  owner: "Owner",
  co_owner: "Co-owner",
  manager: "Manager",
  receptionist: "Recepción",
  housekeeping: "Housekeeping"
};

const visibilityOptions = [
  { value: "12", label: "12 h" },
  { value: "24", label: "24 h" },
  { value: "48", label: "48 h" },
  { value: "72", label: "72 h" },
  { value: "168", label: "7 días" },
  { value: "always", label: "Siempre" }
] as const;

type VisibilityOptionValue = (typeof visibilityOptions)[number]["value"];
type RolePermissionMap = PermissionMatrixResponse["matrix"];
type RoleVersionMap = Record<string, number>;

const permissionKey = (role: string, code: string) => `${role}:${code}`;

const isReadPermission = (permission: PermissionCatalogItem) => /(?:^|[_:])(read|view)$/.test(permission.code);

const sourceLabel: Record<string, string> = {
  default: "Default",
  role_default: "Default del rol",
  override: "Override de rol",
  role_override: "Override de rol",
  user_override: "Override de usuario",
  legacy_role_deny: "Denegación heredada del rol",
  legacy_user_deny: "Denegación heredada del usuario",
  invariant: "Regla de seguridad",
  deny: "No otorgado"
};

const formatPermissionSource = (source: string) => sourceLabel[source] ?? source;

const roleFromUser = (user?: AuthUser | null): PermissionRole | null => user?.role || null;

type PermissionRoleColumn = {
  code: string;
  label: string;
  editable: boolean;
};

const visibilityValue = (window?: VisibilityWindow): VisibilityOptionValue | "custom" => {
  if (!window || (window.past_hours === null && window.future_hours === null)) return "always";
  if (window.past_hours === window.future_hours && window.past_hours !== null) return String(window.past_hours) as VisibilityOptionValue;
  return "custom";
};

type PermissionTableProps = {
  permissions: PermissionCatalogItem[];
  matrix: RolePermissionMap;
  visibilityWindows: VisibilityWindow[];
  roles: PermissionRoleColumn[];
  roleVersions: RoleVersionMap;
  isBusy: boolean;
  onToggle: (role: string, code: string, allowed: boolean, expectedVersion: number) => void;
  onRestorePermission: (role: string, code: string, expectedVersion: number) => void;
  onRestoreRole: (role: string) => void;
  onVisibilityChange: (role: string, value: VisibilityOptionValue) => void;
};

function PermissionTable({
  permissions,
  matrix,
  visibilityWindows,
  roles,
  roleVersions,
  isBusy,
  onToggle,
  onRestorePermission,
  onRestoreRole,
  onVisibilityChange
}: PermissionTableProps) {
  const windowsByRole = new Map(visibilityWindows.map((window) => [window.role, window]));

  const renderPermissionRow = (permission: PermissionCatalogItem) => (
    <tr key={permission.code} className="border-t border-slate-100">
      <th scope="row" className="sticky left-0 z-10 min-w-[280px] border-r border-slate-200 bg-white px-3 py-3 text-left align-top">
        <div className="flex items-start gap-2">
          <div className="min-w-0">
            <p className="font-medium text-slate-800">{permission.description}</p>
            <code className="text-[11px] text-slate-400">{permission.code}</code>
          </div>
          <InfoTip
            content={permission.help_es}
            label={`Más información sobre ${permission.description}`}
            tone="light"
          />
        </div>
      </th>
      {roles.map((role) => {
        const cell = matrix[role.code]?.[permission.code];
        const key = permissionKey(role.code, permission.code);
        const hasOverride = cell?.source === "override";
        const currentVersion = cell?.version ?? roleVersions[key] ?? undefined;
        const expectedVersion = currentVersion ?? 0;
        const restoreVersion = currentVersion ?? 1;
        const versionUnavailable = hasOverride && currentVersion === undefined;
        const locked = permission.locked || Boolean(cell?.locked);
        return (
          <td key={role.code} className="min-w-[126px] px-2 py-3 text-center align-top">
            <div className="flex flex-col items-center gap-1.5">
              <input
                type="checkbox"
                data-testid={`permission-toggle-${role.code}-${permission.code}`}
                aria-label={`${permission.description} para ${role.label}`}
                checked={Boolean(cell?.allowed)}
                disabled={!cell || locked || versionUnavailable || isBusy || !role.editable}
                onChange={(event) => onToggle(role.code, permission.code, event.target.checked, expectedVersion)}
                className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500 disabled:opacity-50"
              />
              <span
                className={`rounded-full px-2 py-0.5 text-[11px] ${
                  locked
                    ? "bg-amber-50 text-amber-700"
                    : hasOverride
                      ? "bg-brand-50 text-brand-700"
                      : "bg-slate-100 text-slate-500"
                }`}
              >
                {locked ? "Bloqueado" : formatPermissionSource(cell?.source ?? "deny")}
              </span>
              {hasOverride && !locked ? (
                <button
                  type="button"
                  className="text-[11px] font-semibold text-brand-700 underline underline-offset-2 disabled:opacity-50"
                  disabled={versionUnavailable || isBusy || !role.editable}
                  onClick={() => onRestorePermission(role.code, permission.code, restoreVersion)}
                >
                  Restaurar
                </button>
              ) : null}
            </div>
          </td>
        );
      })}
    </tr>
  );

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
        Las filas de lectura controlan quién puede ver una sección. Las filas de acciones controlan qué puede modificar cada rol.
        Los permisos bloqueados son reglas de seguridad del sistema.
      </div>
      {permissions.length === 0 ? <p className="text-sm text-slate-600">No hay permisos disponibles.</p> : null}
      {permissions.length > 0 ? (
        <div className="space-y-3">
          {Array.from(new Set(permissions.map((permission) => permission.module).sort((a, b) => a.localeCompare(b)))).map((module) => {
            const modulePermissions = permissions.filter((permission) => permission.module === module);
            const moduleReads = modulePermissions.filter(isReadPermission);
            const moduleActions = modulePermissions.filter((permission) => !isReadPermission(permission));
            return (
              <details key={module} open className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-800 marker:hidden">
                  <span className="capitalize">{module.split("_").join(" ")}</span>
                  <span className="text-xs font-normal text-slate-500">{modulePermissions.length} permisos</span>
                </summary>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[930px] border-separate border-spacing-0 text-sm">
                    <thead>
                      <tr>
                        <th className="sticky left-0 top-0 z-20 min-w-[280px] border-b border-r border-slate-200 bg-white px-3 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Permiso
                        </th>
                        {roles.map((role) => {
                          const window = windowsByRole.get(role.code);
                          const value = visibilityValue(window);
                          return (
                            <th key={role.code} className="min-w-[126px] border-b border-slate-200 bg-white px-2 py-2 text-center align-top">
                              <div className="flex flex-col items-center gap-1.5">
                                <span className="text-xs font-semibold text-slate-700">{role.label}</span>
                                <label className="flex w-full flex-col items-center gap-1 text-[10px] font-normal uppercase tracking-wide text-slate-400">
                                  Ventana
                                  <select
                                    aria-label={`Ventana de visibilidad para ${role.label}`}
                                    value={value}
                                    disabled={isBusy || !role.editable || !window}
                                    onChange={(event) => onVisibilityChange(role.code, event.target.value as VisibilityOptionValue)}
                                    className="h-8 w-full rounded-md border border-slate-200 bg-white px-1 text-xs font-medium normal-case tracking-normal text-slate-700"
                                  >
                                    {value === "custom" ? <option value="custom">Personalizada</option> : null}
                                    {visibilityOptions.map((option) => (
                                      <option key={option.value} value={option.value}>
                                        {option.label}
                                      </option>
                                    ))}
                                  </select>
                                </label>
                                <button
                                  type="button"
                                  className="text-[11px] font-semibold text-slate-500 underline underline-offset-2 disabled:opacity-50"
                                  disabled={isBusy || !role.editable}
                                  onClick={() => onRestoreRole(role.code)}
                                >
                                  Restaurar defaults
                                </button>
                              </div>
                            </th>
                          );
                        })}
                      </tr>
                    </thead>
                    <tbody>
                      {moduleReads.length > 0 ? (
                        <tr>
                          <th colSpan={roles.length + 1} className="border-b border-slate-200 bg-brand-50 px-3 py-2 text-left text-[11px] font-bold uppercase tracking-wide text-brand-700">
                            Lectura y visibilidad
                          </th>
                        </tr>
                      ) : null}
                      {moduleReads.map(renderPermissionRow)}
                      {moduleActions.length > 0 ? (
                        <tr>
                          <th colSpan={roles.length + 1} className="border-y border-slate-200 bg-amber-50 px-3 py-2 text-left text-[11px] font-bold uppercase tracking-wide text-amber-800">
                            Acciones y escritura
                          </th>
                        </tr>
                      ) : null}
                      {moduleActions.map(renderPermissionRow)}
                    </tbody>
                  </table>
                </div>
              </details>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

type UserOverridesPanelProps = {
  users: AuthUser[];
  currentEmail?: string | null;
  selectedUserId: number | null;
  selectedUser: AuthUser | null;
  permissions: PermissionCatalogItem[];
  roleProfiles?: PermissionProfileMatrix;
  roleName: (roleCode: string) => string;
  isRoleEditable: (roleCode: string) => boolean;
  userQuery: UseQueryResult<UserPermissionOverrideResponse, Error>;
  userVersions: RoleVersionMap;
  isBusy: boolean;
  onSelectUser: (userId: number) => void;
  onToggle: (userId: number, code: string, allowed: boolean, expectedVersion: number) => void;
  onRestorePermission: (userId: number, code: string, expectedVersion: number) => void;
  onRestoreAll: (userId: number) => void;
};

function UserOverridesPanel({
  users,
  currentEmail,
  selectedUserId,
  selectedUser,
  permissions,
  roleProfiles,
  roleName,
  isRoleEditable,
  userQuery,
  userVersions,
  isBusy,
  onSelectUser,
  onToggle,
  onRestorePermission,
  onRestoreAll
}: UserOverridesPanelProps) {
  const { t } = useTranslation();
  const targetUsers = users.filter((user) => user.email !== currentEmail);
  const userRole = userQuery.data?.role ?? roleFromUser(selectedUser);
  const canEditSelectedRole = Boolean(userRole && isRoleEditable(userRole));
  const details = userQuery.data?.details ?? {};

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-800">Overrides por usuario</h2>
          <p className="mt-1 max-w-2xl text-xs text-slate-500">
            Compará el permiso efectivo de una persona con el perfil de su rol. Un override individual tiene prioridad sobre el rol.
          </p>
        </div>
        {selectedUserId && userQuery.data ? (
          <button
            type="button"
            onClick={() => onRestoreAll(selectedUserId)}
            disabled={isBusy || userQuery.isError || userQuery.isFetching || !canEditSelectedRole}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Restaurar todos los overrides
          </button>
        ) : null}
      </div>

      {targetUsers.length === 0 ? (
        <p className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">No hay otros usuarios activos para configurar.</p>
      ) : (
        <>
          <label className="mt-4 block max-w-md text-xs font-semibold uppercase tracking-wide text-slate-500">
            Usuario
            <select
              aria-label="Usuario para configurar overrides"
              value={selectedUserId ?? ""}
              onChange={(event) => onSelectUser(Number(event.target.value))}
              className="mt-1 h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm font-normal normal-case tracking-normal text-slate-900"
            >
              {targetUsers.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.email} · {roleName(user.role)}
                </option>
              ))}
            </select>
          </label>

          {userQuery.isLoading ? <p className="mt-4 text-sm text-slate-600">Cargando permisos del usuario...</p> : null}
          {userQuery.isError ? <p className="mt-4 text-sm text-rose-600">No se pudieron cargar los overrides del usuario.</p> : null}
          {userQuery.data && !userRole ? (
            <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900" role="status">
              {t("hotelRoles.roleUnavailable")}
            </p>
          ) : null}
          {userQuery.data && userRole && !canEditSelectedRole ? (
            <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900" role="status">
              {userRole === "owner" || userRole === "co_owner"
                ? t("hotelRoles.protectedRoleReadOnly", { role: roleName(userRole) })
                : t("hotelRoles.inactiveRoleReadOnly", { role: roleName(userRole) })}
            </p>
          ) : null}
          {userQuery.data && userRole ? (
            <div className="mt-4 overflow-x-auto">
              <p className="mb-2 text-xs text-slate-500">
                Rol actual: <strong className="text-slate-700">{roleName(userRole)}</strong>. “Valor del rol” incluye el default y cualquier override de rol vigente.
              </p>
              <table className="w-full min-w-[760px] divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="sticky left-0 z-10 bg-slate-50 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Permiso</th>
                    <th className="px-3 py-2 text-center text-xs font-semibold uppercase tracking-wide text-slate-500">Valor del rol</th>
                    <th className="px-3 py-2 text-center text-xs font-semibold uppercase tracking-wide text-slate-500">Efectivo para usuario</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {permissions.map((permission) => {
                    const roleCell = roleProfiles?.[userRole]?.[permission.code];
                    const detail = details[permission.code];
                    const userOverride = detail?.source === "user_override";
                    const targetUserId = userQuery.data?.user_id ?? selectedUserId;
                    const key = permissionKey(String(targetUserId ?? ""), permission.code);
                    const currentVersion = detail?.version ?? userVersions[key] ?? undefined;
                    const expectedVersion = currentVersion ?? 0;
                    const restoreVersion = currentVersion ?? 1;
                    const versionUnavailable = userOverride && currentVersion === undefined;
                    const locked = permission.locked || Boolean(detail?.locked);
                    return (
                      <tr key={permission.code}>
                        <th scope="row" className="sticky left-0 z-10 bg-white px-3 py-2 text-left align-top">
                          <p className="font-medium text-slate-800">{permission.description}</p>
                          <code className="text-[11px] text-slate-400">{permission.code}</code>
                        </th>
                        <td className="px-3 py-2 text-center align-top">
                          <span className={`rounded-full px-2 py-0.5 text-xs ${roleCell?.allowed ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>
                            {roleCell?.allowed ? "Permitido" : "No otorgado"}
                          </span>
                          <span className="mt-1 block text-[11px] text-slate-400">{formatPermissionSource(roleCell?.source ?? "deny")}</span>
                          {roleCell?.legacy_permission_code ? (
                            <code className="mt-0.5 block text-[10px] text-slate-400">{roleCell.legacy_permission_code}</code>
                          ) : null}
                        </td>
                        <td className="px-3 py-2 text-center align-top">
                          <div className="flex flex-col items-center gap-1.5">
                            <input
                              type="checkbox"
                              data-testid={`user-permission-toggle-${permission.code}`}
                              aria-label={`${permission.description} para ${selectedUser?.email ?? "usuario"}`}
                              checked={Boolean(detail?.allowed)}
                              disabled={!detail || !roleCell || locked || versionUnavailable || isBusy || userQuery.isError || userQuery.isFetching || !canEditSelectedRole}
                              onChange={(event) => onToggle(userQuery.data.user_id, permission.code, event.target.checked, expectedVersion)}
                              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500 disabled:opacity-50"
                            />
                            <span className={`rounded-full px-2 py-0.5 text-[11px] ${userOverride ? "bg-brand-50 text-brand-700" : "bg-slate-100 text-slate-500"}`}>
                              {locked ? "Bloqueado" : formatPermissionSource(detail?.source ?? "deny")}
                            </span>
                            {detail?.legacy_permission_code ? (
                              <code className="text-[10px] text-slate-400">{detail.legacy_permission_code}</code>
                            ) : null}
                            {userOverride && !locked ? (
                              <button
                                type="button"
                                className="text-[11px] font-semibold text-brand-700 underline underline-offset-2 disabled:opacity-50"
                                disabled={versionUnavailable || isBusy || userQuery.isError || userQuery.isFetching || !canEditSelectedRole}
                                onClick={() => onRestorePermission(userQuery.data.user_id, permission.code, restoreVersion)}
                              >
                                Restaurar
                              </button>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}

export function SettingsPermissionsPage() {
  const { t } = useTranslation();
  const { session } = useSession();
  const qc = useQueryClient();
  // The permission administrator is owner-only in the backend. Keeping this
  // check exact also prevents a previewed role from loading sensitive data.
  const canManage = session.baseRole === "owner";
  const enabled = hasValidSession(session) && canManage;
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [roleVersions, setRoleVersions] = useState<RoleVersionMap>({});
  const [userVersions, setUserVersions] = useState<RoleVersionMap>({});
  const [message, setMessage] = useState<string | null>(null);
  const permissionErrorMessage = (error: unknown) =>
    error instanceof ApiError && error.status === 409
      ? t("hotelRoles.permissionConflict")
      : error instanceof ApiError && error.status === 403
        ? t("hotelRoles.permissionDenied")
        : error instanceof Error
          ? error.message
          : t("hotelRoles.permissionSaveError");

  const rolesQuery = useQuery<HotelRolesResponse>({
    queryKey: hotelRolesQueryKey(session.hotelId),
    enabled,
    queryFn: () => fetchHotelRoles(session)
  });
  const catalogQuery = useQuery({
    queryKey: ["permissions-catalog", session.hotelId],
    enabled,
    queryFn: () => fetchPermissionCatalog(session)
  });
  const matrixQuery = useQuery({
    queryKey: ["permissions-matrix", session.hotelId],
    enabled,
    queryFn: () => fetchPermissionMatrix(session)
  });
  const roleProfilesQuery = useQuery({
    queryKey: ["permissions-role-profiles", session.hotelId],
    enabled,
    queryFn: () => fetchRolePermissionProfiles(session)
  });
  const visibilityQuery = useQuery({
    queryKey: ["permissions-visibility-windows", session.hotelId],
    enabled,
    queryFn: () => fetchVisibilityWindows(session)
  });
  const usersQuery = useQuery({
    queryKey: ["permissions-users", session.hotelId],
    enabled,
    queryFn: () => listUsers(session)
  });
  const userOverridesQuery = useQuery<UserPermissionOverrideResponse>({
    queryKey: ["permissions-user-overrides", session.hotelId, selectedUserId],
    enabled: enabled && selectedUserId !== null,
    queryFn: () => fetchUserPermissionOverrides(selectedUserId as number, session)
  });

  useEffect(() => {
    const candidates = (usersQuery.data ?? []).filter((user) => user.email !== session.email);
    if (!candidates.some((user) => user.id === selectedUserId)) {
      setSelectedUserId(candidates[0]?.id ?? null);
    }
  }, [selectedUserId, session.email, usersQuery.data]);

  const permissions = useMemo(
    () => [...(catalogQuery.data?.permissions ?? [])].sort((a, b) => a.module.localeCompare(b.module) || Number(isReadPermission(b)) - Number(isReadPermission(a)) || a.code.localeCompare(b.code)),
    [catalogQuery.data?.permissions]
  );
  const selectedUser = useMemo(
    () => (usersQuery.data ?? []).find((user) => user.id === selectedUserId) ?? null,
    [selectedUserId, usersQuery.data]
  );

  const rolesByCode = useMemo(
    () => new Map((rolesQuery.data?.roles ?? []).map((role) => [role.code, role])),
    [rolesQuery.data?.roles]
  );
  const roleName = (roleCode: string) => {
    const role = rolesByCode.get(roleCode);
    if (role?.kind === "custom") return role.name;
    return t(`hotelRoleNames.${roleCode}`, {
      defaultValue: builtinRoleLabels[roleCode as BuiltinPermissionRole] ?? role?.name ?? roleCode
    });
  };
  const isRoleActive = (roleCode: string) => {
    if (builtinRoleOrder.includes(roleCode as BuiltinPermissionRole)) return true;
    const role = rolesByCode.get(roleCode);
    return role?.kind === "custom" && role.is_active;
  };
  const isRoleEditable = (roleCode: string) =>
    roleCode !== "owner" && roleCode !== "co_owner" && rolesQuery.isSuccess && !rolesQuery.isError && isRoleActive(roleCode);

  const roleColumns: PermissionRoleColumn[] = [
    ...builtinRoleOrder,
    ...(rolesQuery.data?.roles ?? [])
      .filter((role) => role.kind === "custom" && role.is_active)
      .sort((left, right) => left.name.localeCompare(right.name) || left.code.localeCompare(right.code))
      .map((role) => role.code)
  ].map((code) => {
    const windowExists = Boolean(visibilityQuery.data?.windows.some((window) => window.role === code));
    const matrixExists = Boolean(matrixQuery.data?.matrix[code]);
    const profileExists = Boolean(roleProfilesQuery.data?.matrix[code]);
    return {
      code,
      label: roleName(code),
      editable: isRoleEditable(code) && matrixExists && profileExists && windowExists
    };
  });
  const customRoleContractMismatch = roleColumns.some((role) =>
    rolesByCode.get(role.code)?.kind === "custom" &&
    (!matrixQuery.data?.matrix[role.code] || !roleProfilesQuery.data?.matrix[role.code] ||
      !visibilityQuery.data?.windows.some((window) => window.role === role.code))
  );

  const ensureEditableRole = (roleCode: string) => {
    if (!isRoleEditable(roleCode)) throw new Error(t("hotelRoles.readOnlyRoleError", { role: roleName(roleCode) }));
  };

  const invalidatePermissionQueries = () => refreshAfterMutation(qc, session.hotelId, ["security", "users", "settings"]);

  const roleOverrideMutation = useGuardedMutation<PermissionOverrideResponse, Error, { role: PermissionRole; code: string; allowed: boolean; expectedVersion: number }>({
    mutationFn: ({ role, code, allowed, expectedVersion }) => {
      ensureEditableRole(role);
      return updatePermissionOverride({ role, permission_code: code, allowed, expected_version: expectedVersion }, session);
    },
    onSuccess: async (response, variables) => {
      setRoleVersions((current) => ({ ...current, [permissionKey(variables.role, variables.code)]: response.version }));
      setMessage(null);
      await invalidatePermissionQueries();
    },
    onError: (error) => setMessage(permissionErrorMessage(error))
  });

  const restoreRolePermissionMutation = useGuardedMutation<RestoreRolePermissionResponse, Error, { role: PermissionRole; code: string; expectedVersion: number }>({
    mutationFn: ({ role, code, expectedVersion }) => {
      ensureEditableRole(role);
      return restoreRolePermissionOverride(role, code, expectedVersion, session);
    },
    onSuccess: async (_response, variables) => {
      setRoleVersions((current) => {
        const next = { ...current };
        delete next[permissionKey(variables.role, variables.code)];
        return next;
      });
      setMessage(null);
      await invalidatePermissionQueries();
    },
    onError: (error) => setMessage(permissionErrorMessage(error))
  });

  const restoreRoleMutation = useGuardedMutation<RestoreRoleDefaultsResponse, Error, PermissionRole>({
    mutationFn: (role) => {
      ensureEditableRole(role);
      return restoreRoleDefaults(role, session);
    },
    onSuccess: async (_response, role) => {
      setRoleVersions((current) => Object.fromEntries(
        Object.entries(current).filter(([key]) => !key.startsWith(`${role}:`))
      ));
      setMessage(null);
      await invalidatePermissionQueries();
    },
    onError: (error) => setMessage(permissionErrorMessage(error))
  });

  const visibilityMutation = useGuardedMutation<VisibilityWindow, Error, { role: PermissionRole; value: VisibilityOptionValue }>({
    mutationFn: ({ role, value }) => {
      ensureEditableRole(role);
      const hours = value === "always" ? null : Number(value) as VisibilityWindowHours;
      return updateVisibilityWindow({ role, past_hours: hours, future_hours: hours }, session);
    },
    onSuccess: async () => {
      setMessage(null);
      await invalidatePermissionQueries();
    },
    onError: (error) => setMessage(permissionErrorMessage(error))
  });

  const userOverrideMutation = useGuardedMutation<UserPermissionMutationResponse, Error, { userId: number; code: string; allowed: boolean; expectedVersion: number }>({
    mutationFn: ({ userId, code, allowed, expectedVersion }) => {
      const targetRole = usersQuery.data?.find((user) => user.id === userId)?.role;
      if (!targetRole) throw new Error(t("hotelRoles.roleUnavailable"));
      ensureEditableRole(targetRole);
      return updateUserPermissionOverride(userId, { permission_code: code, allowed, expected_version: expectedVersion }, session);
    },
    onSuccess: async (response, variables) => {
      if (typeof response.version === "number") {
        setUserVersions((current) => ({
          ...current,
          [permissionKey(String(variables.userId), variables.code)]: response.version as number
        }));
      }
      setMessage(null);
      await invalidatePermissionQueries();
    },
    onError: (error) => setMessage(permissionErrorMessage(error))
  });

  const restoreUserPermissionMutation = useGuardedMutation<UserPermissionMutationResponse, Error, { userId: number; code: string; expectedVersion: number }>({
    mutationFn: ({ userId, code, expectedVersion }) => {
      const targetRole = usersQuery.data?.find((user) => user.id === userId)?.role;
      if (!targetRole) throw new Error(t("hotelRoles.roleUnavailable"));
      ensureEditableRole(targetRole);
      return restoreUserPermissionOverride(userId, code, expectedVersion, session);
    },
    onSuccess: async (_response, variables) => {
      setUserVersions((current) => {
        const next = { ...current };
        delete next[permissionKey(String(variables.userId), variables.code)];
        return next;
      });
      setMessage(null);
      await invalidatePermissionQueries();
    },
    onError: (error) => setMessage(permissionErrorMessage(error))
  });

  const restoreUserMutation = useGuardedMutation<{ hotel_id: number; user_id: number; restored: number }, Error, number>({
    mutationFn: (userId) => {
      const targetRole = usersQuery.data?.find((user) => user.id === userId)?.role;
      if (!targetRole) throw new Error(t("hotelRoles.roleUnavailable"));
      ensureEditableRole(targetRole);
      return restoreUserDefaults(userId, session);
    },
    onSuccess: async (_response, userId) => {
      setUserVersions((current) => Object.fromEntries(
        Object.entries(current).filter(([key]) => !key.startsWith(`${userId}:`))
      ));
      setMessage(null);
      await invalidatePermissionQueries();
    },
    onError: (error) => setMessage(permissionErrorMessage(error))
  });

  const isBusy =
    roleOverrideMutation.isPending ||
    restoreRolePermissionMutation.isPending ||
    restoreRoleMutation.isPending ||
    visibilityMutation.isPending ||
    userOverrideMutation.isPending ||
    restoreUserPermissionMutation.isPending ||
    restoreUserMutation.isPending;

  if (!hasValidSession(session)) {
    return <p className="text-sm text-slate-600">Iniciá sesión con un hotel activo para editar permisos.</p>;
  }
  if (!canManage) {
    return <p className="text-sm text-slate-600">Solo el owner puede administrar permisos.</p>;
  }

  const loading = rolesQuery.isLoading || catalogQuery.isLoading || matrixQuery.isLoading || roleProfilesQuery.isLoading || visibilityQuery.isLoading;
  const queryError = rolesQuery.error || catalogQuery.error || matrixQuery.error || roleProfilesQuery.error || visibilityQuery.error;
  const matrixIsFetching = rolesQuery.isFetching || catalogQuery.isFetching || matrixQuery.isFetching || roleProfilesQuery.isFetching || visibilityQuery.isFetching;

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Configuración</p>
        <h1 className="text-balance text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">Permisos</h1>
        <p className="text-sm text-slate-600">
          Administrá qué puede ver y qué puede modificar cada rol. Los cambios quedan registrados como overrides auditables.
        </p>
      </header>

      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 shadow-sm">
        Ver una sección y poder editarla son permisos separados. Los permisos críticos del owner permanecen bloqueados por seguridad.
      </div>

      <HotelRoleManagement rolesQuery={rolesQuery} />

      {message ? <p className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700" role="alert">{message}</p> : null}
      {loading ? <p className="text-sm text-slate-600" role="status">Cargando permisos...</p> : null}
      {queryError ? <p className="text-sm text-rose-600">No se pudo cargar la configuración de permisos. {(queryError as Error).message}</p> : null}
      {customRoleContractMismatch && !queryError ? (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900" role="status">
          {t("hotelRoles.matrixContractMismatch")}
        </p>
      ) : null}

      {!loading && !queryError && matrixQuery.data && visibilityQuery.data && catalogQuery.data ? (
        <section className="space-y-4" data-testid="permissions-matrix">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-800">Matriz por módulo</h2>
              <p className="text-xs text-slate-500">Cada módulo se puede contraer para trabajar con una parte de la matriz.</p>
            </div>
            {matrixIsFetching ? <span className="text-xs text-slate-500">Actualizando...</span> : null}
          </div>
          <PermissionTable
            permissions={permissions}
            matrix={matrixQuery.data.matrix}
            visibilityWindows={visibilityQuery.data.windows}
            roles={roleColumns}
            roleVersions={roleVersions}
            isBusy={isBusy || matrixIsFetching}
            onToggle={(role, code, allowed, expectedVersion) => {
              if (!isRoleEditable(role)) return;
              void roleOverrideMutation.mutateAsync({ role, code, allowed, expectedVersion }).catch(() => undefined);
            }}
            onRestorePermission={(role, code, expectedVersion) => {
              if (!isRoleEditable(role)) return;
              void restoreRolePermissionMutation.mutateAsync({ role, code, expectedVersion }).catch(() => undefined);
            }}
            onRestoreRole={(role) => {
              if (!isRoleEditable(role)) return;
              void restoreRoleMutation.mutateAsync(role).catch(() => undefined);
            }}
            onVisibilityChange={(role, value) => {
              if (!isRoleEditable(role)) return;
              void visibilityMutation.mutateAsync({ role, value }).catch(() => undefined);
            }}
          />
        </section>
      ) : null}

      {usersQuery.isError ? <p className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700" role="alert">No se pudieron cargar los usuarios; los overrides individuales quedan bloqueados.</p> : null}
      {!usersQuery.isError && usersQuery.isSuccess && !rolesQuery.isError && rolesQuery.isSuccess && !roleProfilesQuery.isError && roleProfilesQuery.isSuccess && catalogQuery.isSuccess ? (
        <UserOverridesPanel
          users={usersQuery.data ?? []}
          currentEmail={session.email}
          selectedUserId={selectedUserId}
          selectedUser={selectedUser}
          permissions={permissions}
          roleProfiles={roleProfilesQuery.data?.matrix}
          roleName={roleName}
          isRoleEditable={isRoleEditable}
          userQuery={userOverridesQuery}
          userVersions={userVersions}
          isBusy={isBusy}
          onSelectUser={setSelectedUserId}
          onToggle={(userId, code, allowed, expectedVersion) => {
            void userOverrideMutation.mutateAsync({ userId, code, allowed, expectedVersion }).catch(() => undefined);
          }}
          onRestorePermission={(userId, code, expectedVersion) => {
            void restoreUserPermissionMutation.mutateAsync({ userId, code, expectedVersion }).catch(() => undefined);
          }}
          onRestoreAll={(userId) => {
            void restoreUserMutation.mutateAsync(userId).catch(() => undefined);
          }}
        />
      ) : null}
    </div>
  );
}

function HotelRoleManagement({ rolesQuery }: { rolesQuery: UseQueryResult<HotelRolesResponse, Error> }) {
  const { t } = useTranslation();
  const { session } = useSession();
  const queryClient = useQueryClient();
  const [newName, setNewName] = useState("");
  const [baseRole, setBaseRole] = useState<HotelRoleTemplate>("manager");
  const [editingCode, setEditingCode] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const [archiveCode, setArchiveCode] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ kind: "status" | "alert"; text: string } | null>(null);
  const queryKey = hotelRolesQueryKey(session.hotelId);
  const roleCatalogReady = rolesQuery.isSuccess && !rolesQuery.isError && !rolesQuery.isFetching;
  const canEditCustomRole = (code: string) =>
    roleCatalogReady && Boolean(rolesQuery.data?.roles.some((role) => role.code === code && role.kind === "custom" && role.is_active));

  const refreshRoles = () => queryClient.invalidateQueries({ queryKey });
  const errorText = (error: unknown, fallback: string) => {
    if (error instanceof ApiError && error.status === 409 && /rol fue modificado/i.test(error.message)) {
      return t("hotelRoles.stale");
    }
    return error instanceof Error ? error.message : fallback;
  };
  const archiveErrorText = (error: unknown) => {
    if (error instanceof ApiError && error.status === 409 && !/rol fue modificado/i.test(error.message)) {
      return t("hotelRoles.archiveConflict");
    }
    return errorText(error, t("hotelRoles.archiveError"));
  };

  const createMutation = useGuardedMutation<unknown, Error, CreateHotelRolePayload>({
    mutationFn: (payload) => {
      if (!roleCatalogReady) throw new Error(t("hotelRoles.roleUnavailable"));
      return createHotelRole(payload, session);
    },
    onSuccess: async () => {
      setNewName("");
      setFeedback({ kind: "status", text: t("hotelRoles.createSuccess") });
      await refreshRoles();
    },
    onError: (error) => setFeedback({ kind: "alert", text: errorText(error, t("hotelRoles.createError")) })
  });

  const renameMutation = useGuardedMutation<unknown, Error, { code: string } & RenameHotelRolePayload>({
    mutationFn: ({ code, ...payload }) => {
      if (!canEditCustomRole(code)) throw new Error(t("hotelRoles.readOnlyRoleError", { role: code }));
      return renameHotelRole(code, payload, session);
    },
    onSuccess: async () => {
      setEditingCode(null);
      setRenameDraft("");
      setFeedback({ kind: "status", text: t("hotelRoles.renameSuccess") });
      await refreshRoles();
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) void refreshRoles();
      setFeedback({ kind: "alert", text: errorText(error, t("hotelRoles.renameError")) });
    }
  });

  const archiveMutation = useGuardedMutation<unknown, Error, { code: string; expectedVersion: number }>({
    mutationFn: ({ code, expectedVersion }) => {
      const role = rolesQuery.data?.roles.find((candidate) => candidate.code === code);
      if (!canEditCustomRole(code) || !role || role.assigned_count !== 0 || role.pending_invitation_count !== 0) {
        throw new Error(t("hotelRoles.readOnlyRoleError", { role: role?.name ?? code }));
      }
      return archiveHotelRole(code, expectedVersion, session);
    },
    onSuccess: async () => {
      setArchiveCode(null);
      setFeedback({ kind: "status", text: t("hotelRoles.archiveSuccess") });
      await refreshRoles();
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) void refreshRoles();
      setFeedback({ kind: "alert", text: archiveErrorText(error) });
    }
  });

  const roles = useMemo(
    () => [...(rolesQuery.data?.roles ?? [])].sort((a, b) => Number(b.kind === "builtin") - Number(a.kind === "builtin") || a.name.localeCompare(b.name)),
    [rolesQuery.data?.roles]
  );
  const isBusy = createMutation.isPending || renameMutation.isPending || archiveMutation.isPending;

  const roleName = (role: HotelRole) =>
    role.kind === "builtin"
      ? t(`hotelRoleNames.${role.code}`, { defaultValue: role.name })
      : role.name;

  const submitCreate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = newName.trim();
    if (!name || isBusy) return;
    setFeedback(null);
    void createMutation.mutateAsync({ name, base_role: baseRole }).catch(() => undefined);
  };

  const submitRename = (event: FormEvent<HTMLFormElement>, role: HotelRole) => {
    event.preventDefault();
    const name = renameDraft.trim();
    if (!name || isBusy) return;
    setFeedback(null);
    void renameMutation.mutateAsync({ code: role.code, name, expected_version: role.version }).catch(() => undefined);
  };

  return (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" data-testid="hotel-role-management" aria-labelledby="hotel-roles-title">
      <div>
        <h2 id="hotel-roles-title" className="text-sm font-semibold text-slate-800">{t("hotelRoles.title")}</h2>
        <p className="mt-1 text-sm text-slate-600">{t("hotelRoles.description")}</p>
        <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">{t("hotelRoles.matrixNote")}</p>
      </div>

      {feedback ? (
        <p className={`rounded-lg border p-3 text-sm ${feedback.kind === "alert" ? "border-rose-200 bg-rose-50 text-rose-700" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`} role={feedback.kind} aria-live={feedback.kind === "alert" ? "assertive" : "polite"}>
          {feedback.text}
        </p>
      ) : null}

      {rolesQuery.isLoading ? <p className="text-sm text-slate-600" role="status">{t("hotelRoles.loading")}</p> : null}
      {rolesQuery.isError ? (
        <p className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700" role="alert">
          {t("hotelRoles.loadError")} {rolesQuery.error instanceof Error ? rolesQuery.error.message : ""}
        </p>
      ) : null}

      <form className="grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3 sm:grid-cols-[minmax(0,1fr)_minmax(12rem,0.8fr)_auto] sm:items-end" onSubmit={submitCreate}>
        <div>
          <label htmlFor="hotel-role-create-name" className="block text-xs font-semibold text-slate-700">{t("hotelRoles.createName")}</label>
          <input
            id="hotel-role-create-name"
            className="mt-1 h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm"
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            placeholder={t("hotelRoles.createNamePlaceholder")}
            maxLength={80}
            required
            aria-describedby="hotel-role-create-name-hint"
            disabled={isBusy || !roleCatalogReady}
          />
          <p id="hotel-role-create-name-hint" className="mt-1 text-xs text-slate-500">{t("hotelRoles.createNameHint")}</p>
        </div>
        <div>
          <label htmlFor="hotel-role-template" className="block text-xs font-semibold text-slate-700">{t("hotelRoles.template")}</label>
          <select
            id="hotel-role-template"
            className="mt-1 h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm"
            value={baseRole}
            onChange={(event) => setBaseRole(event.target.value as HotelRoleTemplate)}
            disabled={isBusy || !roleCatalogReady}
          >
            {(["manager", "receptionist", "housekeeping"] as const).map((role) => (
              <option key={role} value={role}>{t(`hotelRoleNames.${role}`)}</option>
            ))}
          </select>
          <p className="mt-1 text-xs text-slate-500">{t("hotelRoles.templateHelp")}</p>
        </div>
        <button
          type="submit"
          disabled={isBusy || !roleCatalogReady || !newName.trim()}
          className="h-10 rounded-lg bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {createMutation.isPending ? t("hotelRoles.creating") : t("hotelRoles.create")}
        </button>
      </form>

      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{t("hotelRoles.availableRoles")}</h3>
        {rolesQuery.isSuccess && roles.length === 0 ? <p className="mt-2 text-sm text-slate-600">{t("hotelRoles.empty")}</p> : null}
        <ul className="mt-2 divide-y divide-slate-200 rounded-lg border border-slate-200">
          {roles.map((role) => {
            const roleId = `hotel-role-${encodeURIComponent(role.code)}`;
            const isEditing = editingCode === role.code;
            const isConfirmingArchive = archiveCode === role.code;
            return (
              <li key={role.code} className="space-y-3 p-3 sm:p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-slate-800">{roleName(role)}</span>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">{role.kind === "builtin" ? t("hotelRoles.builtin") : t("hotelRoles.custom")}</span>
                      <span className={`rounded-full px-2 py-0.5 text-[11px] ${role.is_active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
                        {role.is_active ? t("hotelRoles.active") : t("hotelRoles.archived")}
                      </span>
                    </div>
                    <code className="mt-1 block break-all text-[11px] text-slate-400">{role.code}</code>
                    <p className="mt-1 text-xs text-slate-500">
                      {t("hotelRoles.assignedCount", { count: role.assigned_count })} · {t("hotelRoles.pendingInvitationCount", { count: role.pending_invitation_count })} · {t("hotelRoles.permissionCount", { count: role.permission_count })}
                    </p>
                    {role.kind === "custom" && role.base_role ? (
                      <p className="mt-1 text-xs text-slate-500">{t("hotelRoles.basedOn", { role: t(`hotelRoleNames.${role.base_role}`, { defaultValue: role.base_role }) })}</p>
                    ) : null}
                  </div>

                  {role.kind === "custom" && role.is_active ? (
                    <div className="flex shrink-0 flex-wrap gap-2">
                      {!isEditing && !isConfirmingArchive ? (
                        <>
                          <button
                            type="button"
                            className="min-h-9 rounded-lg border border-slate-300 px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                            disabled={isBusy || !roleCatalogReady}
                            onClick={() => { setFeedback(null); setEditingCode(role.code); setRenameDraft(role.name); setArchiveCode(null); }}
                          >
                            {t("hotelRoles.rename")}
                          </button>
                          <button
                            type="button"
                            className="min-h-9 rounded-lg border border-rose-200 px-3 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={isBusy || !roleCatalogReady || role.assigned_count > 0 || role.pending_invitation_count > 0}
                            aria-describedby={role.assigned_count > 0 || role.pending_invitation_count > 0 ? `${roleId}-archive-help` : undefined}
                            onClick={() => { setFeedback(null); setArchiveCode(role.code); setEditingCode(null); }}
                          >
                            {t("hotelRoles.archive")}
                          </button>
                        </>
                      ) : null}
                    </div>
                  ) : null}
                </div>

                {role.kind === "builtin" ? <p className="text-xs text-slate-500">{t("hotelRoles.builtinImmutable")}</p> : null}
                {role.kind === "custom" && role.is_active && (role.assigned_count > 0 || role.pending_invitation_count > 0) && !isEditing && !isConfirmingArchive ? (
                  <p id={`${roleId}-archive-help`} className="text-xs text-slate-500">
                    {t("hotelRoles.archiveBlocked", { assignedCount: role.assigned_count, invitationCount: role.pending_invitation_count })}
                  </p>
                ) : null}

                {isEditing ? (
                  <form className="flex flex-col gap-2 sm:flex-row sm:items-end" onSubmit={(event) => submitRename(event, role)}>
                    <div className="min-w-0 flex-1">
                      <label htmlFor={`${roleId}-rename`} className="block text-xs font-semibold text-slate-700">{t("hotelRoles.renameLabel", { name: role.name })}</label>
                      <input
                        id={`${roleId}-rename`}
                        className="mt-1 h-10 w-full rounded-lg border border-slate-300 px-3 text-sm"
                        value={renameDraft}
                        onChange={(event) => setRenameDraft(event.target.value)}
                        maxLength={80}
                        required
                        autoFocus
                        disabled={isBusy || !roleCatalogReady}
                      />
                    </div>
                    <button type="submit" className="h-10 rounded-lg bg-brand-600 px-4 text-sm font-semibold text-white disabled:opacity-50" disabled={isBusy || !roleCatalogReady || !renameDraft.trim()}>
                      {renameMutation.isPending ? t("hotelRoles.saving") : t("hotelRoles.save")}
                    </button>
                    <button type="button" className="h-10 rounded-lg border border-slate-300 px-4 text-sm font-semibold text-slate-700 disabled:opacity-50" disabled={isBusy || !roleCatalogReady} onClick={() => { setEditingCode(null); setRenameDraft(""); }}>
                      {t("hotelRoles.cancel")}
                    </button>
                  </form>
                ) : null}

                {isConfirmingArchive ? (
                  <div className="space-y-2 rounded-lg border border-rose-200 bg-rose-50 p-3" role="group" aria-label={`${t("hotelRoles.archiveConfirm")}: ${role.name}`}>
                    <p className="text-sm text-rose-900">{t("hotelRoles.archivePrompt", { name: role.name, assignedCount: role.assigned_count, invitationCount: role.pending_invitation_count })}</p>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="min-h-9 rounded-lg bg-rose-700 px-3 text-xs font-semibold text-white disabled:opacity-50"
                        disabled={isBusy || !roleCatalogReady || role.assigned_count !== 0 || role.pending_invitation_count !== 0}
                        onClick={() => { setFeedback(null); void archiveMutation.mutateAsync({ code: role.code, expectedVersion: role.version }).catch(() => undefined); }}
                      >
                        {archiveMutation.isPending ? t("hotelRoles.archiving") : t("hotelRoles.archiveConfirm")}
                      </button>
                      <button type="button" className="min-h-9 rounded-lg border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-700 disabled:opacity-50" disabled={isBusy || !roleCatalogReady} onClick={() => setArchiveCode(null)}>
                        {t("hotelRoles.cancel")}
                      </button>
                    </div>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
