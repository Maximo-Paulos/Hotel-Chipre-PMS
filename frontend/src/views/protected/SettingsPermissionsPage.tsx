import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";

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

const roleOrder: PermissionRole[] = ["owner", "co_owner", "manager", "receptionist", "housekeeping"];

const roleLabels: Record<PermissionRole, string> = {
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

const permissionKey = (role: PermissionRole, code: string) => `${role}:${code}`;

const isReadPermission = (permission: PermissionCatalogItem) => /(?:^|[_:])(read|view)$/.test(permission.code);

const sourceLabel: Record<string, string> = {
  default: "Default",
  role_default: "Default del rol",
  override: "Override de rol",
  role_override: "Override de rol",
  user_override: "Override de usuario",
  invariant: "Regla de seguridad",
  deny: "No otorgado"
};

const formatPermissionSource = (source: string) => sourceLabel[source] ?? source;

const conflictMessage = (error: unknown) =>
  error instanceof ApiError && error.status === 409
    ? "Esto cambió mientras editabas, recargá para continuar."
    : error instanceof Error
      ? error.message
      : "No se pudo guardar el cambio.";

const roleFromUser = (user?: AuthUser | null): PermissionRole | null =>
  user && roleOrder.includes(user.role as PermissionRole) ? (user.role as PermissionRole) : null;

const visibilityValue = (window?: VisibilityWindow): VisibilityOptionValue | "custom" => {
  if (!window || (window.past_hours === null && window.future_hours === null)) return "always";
  if (window.past_hours === window.future_hours && window.past_hours !== null) return String(window.past_hours) as VisibilityOptionValue;
  return "custom";
};

type PermissionTableProps = {
  permissions: PermissionCatalogItem[];
  matrix: RolePermissionMap;
  visibilityWindows: VisibilityWindow[];
  roleVersions: RoleVersionMap;
  isBusy: boolean;
  onToggle: (role: PermissionRole, code: string, allowed: boolean, expectedVersion: number) => void;
  onRestorePermission: (role: PermissionRole, code: string, expectedVersion: number) => void;
  onRestoreRole: (role: PermissionRole) => void;
  onVisibilityChange: (role: PermissionRole, value: VisibilityOptionValue) => void;
};

function PermissionTable({
  permissions,
  matrix,
  visibilityWindows,
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
      {roleOrder.map((role) => {
        const cell = matrix[role]?.[permission.code];
        const key = permissionKey(role, permission.code);
        const hasOverride = cell?.source === "override";
        const expectedVersion = roleVersions[key] ?? 0;
        // The read endpoints currently omit override versions. New toggles
        // safely start at 0; an existing override is expected to be version 1
        // until the backend returns its version, and a mismatch is surfaced as
        // a conflict instead of silently overwriting it.
        const restoreVersion = roleVersions[key] ?? 1;
        const locked = permission.locked || Boolean(cell?.locked);
        return (
          <td key={role} className="min-w-[126px] px-2 py-3 text-center align-top">
            <div className="flex flex-col items-center gap-1.5">
              <input
                type="checkbox"
                data-testid={`permission-toggle-${role}-${permission.code}`}
                aria-label={`${permission.description} para ${roleLabels[role]}`}
                checked={Boolean(cell?.allowed)}
                disabled={!cell || locked || isBusy}
                onChange={(event) => onToggle(role, permission.code, event.target.checked, expectedVersion)}
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
                  disabled={isBusy}
                  onClick={() => onRestorePermission(role, permission.code, restoreVersion)}
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
                        {roleOrder.map((role) => {
                          const window = windowsByRole.get(role);
                          const value = visibilityValue(window);
                          return (
                            <th key={role} className="min-w-[126px] border-b border-slate-200 bg-white px-2 py-2 text-center align-top">
                              <div className="flex flex-col items-center gap-1.5">
                                <span className="text-xs font-semibold text-slate-700">{roleLabels[role]}</span>
                                <label className="flex w-full flex-col items-center gap-1 text-[10px] font-normal uppercase tracking-wide text-slate-400">
                                  Ventana
                                  <select
                                    aria-label={`Ventana de visibilidad para ${roleLabels[role]}`}
                                    value={value}
                                    disabled={isBusy}
                                    onChange={(event) => onVisibilityChange(role, event.target.value as VisibilityOptionValue)}
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
                                  disabled={isBusy}
                                  onClick={() => onRestoreRole(role)}
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
                          <th colSpan={roleOrder.length + 1} className="border-b border-slate-200 bg-blue-50 px-3 py-2 text-left text-[11px] font-bold uppercase tracking-wide text-blue-700">
                            Lectura y visibilidad
                          </th>
                        </tr>
                      ) : null}
                      {moduleReads.map(renderPermissionRow)}
                      {moduleActions.length > 0 ? (
                        <tr>
                          <th colSpan={roleOrder.length + 1} className="border-y border-slate-200 bg-amber-50 px-3 py-2 text-left text-[11px] font-bold uppercase tracking-wide text-amber-800">
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
  userQuery,
  userVersions,
  isBusy,
  onSelectUser,
  onToggle,
  onRestorePermission,
  onRestoreAll
}: UserOverridesPanelProps) {
  const targetUsers = users.filter((user) => user.email !== currentEmail);
  const userRole = userQuery.data?.role ?? roleFromUser(selectedUser);
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
            disabled={isBusy}
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
                  {user.email} · {roleLabels[user.role as PermissionRole] ?? user.role}
                </option>
              ))}
            </select>
          </label>

          {userQuery.isLoading ? <p className="mt-4 text-sm text-slate-600">Cargando permisos del usuario...</p> : null}
          {userQuery.isError ? <p className="mt-4 text-sm text-rose-600">No se pudieron cargar los overrides del usuario.</p> : null}
          {userQuery.data && userRole ? (
            <div className="mt-4 overflow-x-auto">
              <p className="mb-2 text-xs text-slate-500">
                Rol actual: <strong className="text-slate-700">{roleLabels[userRole]}</strong>. “Valor del rol” incluye el default y cualquier override de rol vigente.
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
                    const key = permissionKey(userRole, permission.code);
                    const expectedVersion = userVersions[key] ?? 0;
                    const restoreVersion = userVersions[key] ?? 1;
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
                        </td>
                        <td className="px-3 py-2 text-center align-top">
                          <div className="flex flex-col items-center gap-1.5">
                            <input
                              type="checkbox"
                              data-testid={`user-permission-toggle-${permission.code}`}
                              aria-label={`${permission.description} para ${selectedUser?.email ?? "usuario"}`}
                              checked={Boolean(detail?.allowed)}
                              disabled={!detail || locked || isBusy}
                              onChange={(event) => onToggle(userQuery.data.user_id, permission.code, event.target.checked, expectedVersion)}
                              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500 disabled:opacity-50"
                            />
                            <span className={`rounded-full px-2 py-0.5 text-[11px] ${userOverride ? "bg-brand-50 text-brand-700" : "bg-slate-100 text-slate-500"}`}>
                              {locked ? "Bloqueado" : formatPermissionSource(detail?.source ?? "deny")}
                            </span>
                            {userOverride && !locked ? (
                              <button
                                type="button"
                                className="text-[11px] font-semibold text-brand-700 underline underline-offset-2 disabled:opacity-50"
                                disabled={isBusy}
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

  const invalidatePermissionQueries = () => {
    void qc.invalidateQueries({ queryKey: ["permissions-matrix", session.hotelId] });
    void qc.invalidateQueries({ queryKey: ["permissions-role-profiles", session.hotelId] });
    void qc.invalidateQueries({ queryKey: ["permissions-user-overrides", session.hotelId] });
    void qc.invalidateQueries({ queryKey: ["permissions", "effective"] });
  };

  const roleOverrideMutation = useMutation<PermissionOverrideResponse, Error, { role: PermissionRole; code: string; allowed: boolean; expectedVersion: number }>({
    mutationFn: ({ role, code, allowed, expectedVersion }) => updatePermissionOverride({ role, permission_code: code, allowed, expected_version: expectedVersion }, session),
    onSuccess: (response, variables) => {
      setRoleVersions((current) => ({ ...current, [permissionKey(variables.role, variables.code)]: response.version }));
      setMessage(null);
      invalidatePermissionQueries();
    },
    onError: (error) => setMessage(conflictMessage(error))
  });

  const restoreRolePermissionMutation = useMutation<RestoreRolePermissionResponse, Error, { role: PermissionRole; code: string; expectedVersion: number }>({
    mutationFn: ({ role, code, expectedVersion }) => restoreRolePermissionOverride(role, code, expectedVersion, session),
    onSuccess: () => {
      setMessage(null);
      invalidatePermissionQueries();
    },
    onError: (error) => setMessage(conflictMessage(error))
  });

  const restoreRoleMutation = useMutation<RestoreRoleDefaultsResponse, Error, PermissionRole>({
    mutationFn: (role) => restoreRoleDefaults(role, session),
    onSuccess: () => {
      setMessage(null);
      invalidatePermissionQueries();
    },
    onError: (error) => setMessage(conflictMessage(error))
  });

  const visibilityMutation = useMutation<VisibilityWindow, Error, { role: PermissionRole; value: VisibilityOptionValue }>({
    mutationFn: ({ role, value }) => {
      const hours = value === "always" ? null : Number(value) as VisibilityWindowHours;
      return updateVisibilityWindow({ role, past_hours: hours, future_hours: hours }, session);
    },
    onSuccess: () => {
      setMessage(null);
      void qc.invalidateQueries({ queryKey: ["permissions-visibility-windows", session.hotelId] });
    },
    onError: (error) => setMessage(conflictMessage(error))
  });

  const userOverrideMutation = useMutation<UserPermissionMutationResponse, Error, { userId: number; code: string; allowed: boolean; expectedVersion: number }>({
    mutationFn: ({ userId, code, allowed, expectedVersion }) => updateUserPermissionOverride(userId, { permission_code: code, allowed, expected_version: expectedVersion }, session),
    onSuccess: (response, variables) => {
      if (typeof response.version === "number") {
        const userRole = userOverridesQuery.data?.role ?? roleFromUser(selectedUser);
        if (userRole) setUserVersions((current) => ({ ...current, [permissionKey(userRole, variables.code)]: response.version as number }));
      }
      setMessage(null);
      invalidatePermissionQueries();
    },
    onError: (error) => setMessage(conflictMessage(error))
  });

  const restoreUserPermissionMutation = useMutation<UserPermissionMutationResponse, Error, { userId: number; code: string; expectedVersion: number }>({
    mutationFn: ({ userId, code, expectedVersion }) => restoreUserPermissionOverride(userId, code, expectedVersion, session),
    onSuccess: () => {
      setMessage(null);
      invalidatePermissionQueries();
    },
    onError: (error) => setMessage(conflictMessage(error))
  });

  const restoreUserMutation = useMutation<{ hotel_id: number; user_id: number; restored: number }, Error, number>({
    mutationFn: (userId) => restoreUserDefaults(userId, session),
    onSuccess: () => {
      setMessage(null);
      invalidatePermissionQueries();
    },
    onError: (error) => setMessage(conflictMessage(error))
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

  const loading = catalogQuery.isLoading || matrixQuery.isLoading || roleProfilesQuery.isLoading || visibilityQuery.isLoading || usersQuery.isLoading;
  const queryError = catalogQuery.error || matrixQuery.error || roleProfilesQuery.error || visibilityQuery.error;

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Configuración</p>
        <h1 className="text-2xl font-semibold text-slate-900">Permisos</h1>
        <p className="text-sm text-slate-600">
          Administrá qué puede ver y qué puede modificar cada rol. Los cambios quedan registrados como overrides auditables.
        </p>
      </header>

      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 shadow-sm">
        Ver una sección y poder editarla son permisos separados. Los permisos críticos del owner permanecen bloqueados por seguridad.
      </div>

      {message ? <p className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700" role="alert">{message}</p> : null}
      {loading ? <p className="text-sm text-slate-600" role="status">Cargando permisos...</p> : null}
      {queryError ? <p className="text-sm text-rose-600">No se pudo cargar la configuración de permisos. {(queryError as Error).message}</p> : null}

      {!loading && !queryError && matrixQuery.data && visibilityQuery.data ? (
        <section className="space-y-4" data-testid="permissions-matrix">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-800">Matriz por módulo</h2>
              <p className="text-xs text-slate-500">Cada módulo se puede contraer para trabajar con una parte de la matriz.</p>
            </div>
            {matrixQuery.isFetching || visibilityQuery.isFetching ? <span className="text-xs text-slate-500">Actualizando...</span> : null}
          </div>
          <PermissionTable
            permissions={permissions}
            matrix={matrixQuery.data.matrix}
            visibilityWindows={visibilityQuery.data.windows}
            roleVersions={roleVersions}
            isBusy={isBusy}
            onToggle={(role, code, allowed, expectedVersion) => roleOverrideMutation.mutate({ role, code, allowed, expectedVersion })}
            onRestorePermission={(role, code, expectedVersion) => restoreRolePermissionMutation.mutate({ role, code, expectedVersion })}
            onRestoreRole={(role) => restoreRoleMutation.mutate(role)}
            onVisibilityChange={(role, value) => visibilityMutation.mutate({ role, value })}
          />
        </section>
      ) : null}

      {!usersQuery.isError && !roleProfilesQuery.isError ? (
        <UserOverridesPanel
          users={usersQuery.data ?? []}
          currentEmail={session.email}
          selectedUserId={selectedUserId}
          selectedUser={selectedUser}
          permissions={permissions}
          roleProfiles={roleProfilesQuery.data?.matrix}
          userQuery={userOverridesQuery}
          userVersions={userVersions}
          isBusy={isBusy}
          onSelectUser={setSelectedUserId}
          onToggle={(userId, code, allowed, expectedVersion) => userOverrideMutation.mutate({ userId, code, allowed, expectedVersion })}
          onRestorePermission={(userId, code, expectedVersion) => restoreUserPermissionMutation.mutate({ userId, code, expectedVersion })}
          onRestoreAll={(userId) => restoreUserMutation.mutate(userId)}
        />
      ) : null}
    </div>
  );
}
