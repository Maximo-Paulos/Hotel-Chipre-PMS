import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  inviteUser,
  listUserAliases,
  listUsers,
  resendInvitation,
  revokeUser,
  updateUserAlias,
  updateUserRole,
  type InvitePayload,
  type InviteResponse
} from "../../api/users";
import { type AuthUser } from "../../api/auth";
import { hasValidSession } from "../../api/client";
import { useSession } from "../../state/session";
import { refreshUserState } from "../../api/queryInvalidation";
import { useGuardedMutation } from "../../hooks/useGuardedMutation";
import { useEffectivePermissions } from "../../hooks/usePermissions";
import { roleLabels } from "../../ui/UserBadge";
import { fetchHotelRoles, hotelRolesQueryKey, type HotelRole } from "../../api/roles";

type InviteFormState = Omit<InvitePayload, "role"> & { role: string };

export function SettingsUsersPage() {
  const { t } = useTranslation();
  const { session } = useSession();
  const qc = useQueryClient();
  const { hasPermission } = useEffectivePermissions();
  const canManage = ["owner", "co_owner"].includes(session.baseRole ?? session.role ?? "")
    && hasPermission("settings:users:manage");
  const rolesQuery = useQuery({
    queryKey: hotelRolesQueryKey(session.hotelId),
    enabled: hasValidSession(session) && canManage,
    queryFn: () => fetchHotelRoles(session)
  });
  const activeAssignableRoles = useMemo(() => {
    const actorRole = session.baseRole ?? session.role;
    return (rolesQuery.data?.roles ?? []).filter((role) =>
      role.is_active && role.code !== "owner" && !(actorRole === "co_owner" && role.code === "co_owner")
    );
  }, [rolesQuery.data?.roles, session.baseRole, session.role]);
  const defaultAssignableRole = activeAssignableRoles.find((role) => role.code === "manager") ?? activeAssignableRoles[0];
  const roleDisplayName = (code: string) => {
    const role = rolesQuery.data?.roles.find((item) => item.code === code);
    if (role?.kind === "custom") return role.name;
    if (role) return t(`hotelRoleNames.${role.code}`, { defaultValue: role.name });
    return roleLabels[code as keyof typeof roleLabels] ?? code;
  };
  const roleOptionLabel = (role: HotelRole) =>
    role.kind === "custom" ? `${role.name} · ${t("hotelRoles.custom")}` : roleDisplayName(role.code);
  const usersQuery = useQuery<AuthUser[]>({
    queryKey: ["users", session.hotelId],
    enabled: hasValidSession(session),
    queryFn: () => listUsers(session)
  });
  const aliasesQuery = useQuery({
    queryKey: ["users", "aliases", session.hotelId],
    enabled: hasValidSession(session) && canManage,
    queryFn: () => listUserAliases(session)
  });
  const inviteMutation = useGuardedMutation({
    // The wire payload carries a string role code. The API helper still narrows
    // it to the legacy built-in union; backend support for custom codes is a
    // required companion change and is not implied by this local assertion.
    mutationFn: (payload: InviteFormState) => inviteUser({
      ...payload,
      role: payload.role as InvitePayload["role"]
    }, session),
    onSuccess: async () => {
      await Promise.all([
        refreshUserState(qc, session.hotelId),
        qc.invalidateQueries({ queryKey: ["users", "aliases", session.hotelId] }),
        qc.invalidateQueries({ queryKey: hotelRolesQueryKey(session.hotelId) })
      ]);
    }
  });
  const resendMutation = useGuardedMutation({
    mutationFn: (invitationId: number) => resendInvitation(invitationId, session)
  });
  const revokeMutation = useGuardedMutation({
    mutationFn: (userId: number) => revokeUser(userId, session),
    onSuccess: async () => {
      await Promise.all([
        refreshUserState(qc, session.hotelId),
        qc.invalidateQueries({ queryKey: hotelRolesQueryKey(session.hotelId) })
      ]);
    }
  });
  const updateRoleMutation = useGuardedMutation({
    mutationFn: (payload: { userId: number; role: string }) =>
      updateUserRole(payload.userId, payload.role as InvitePayload["role"], session),
    onSuccess: async () => {
      await Promise.all([
        refreshUserState(qc, session.hotelId),
        qc.invalidateQueries({ queryKey: hotelRolesQueryKey(session.hotelId) })
      ]);
    }
  });
  const updateAliasMutation = useGuardedMutation({
    mutationFn: (payload: { userId: number; alias: string | null }) =>
      updateUserAlias(payload.userId, payload.alias, session),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["users", "aliases", session.hotelId] }),
        qc.invalidateQueries({ queryKey: ["users", session.hotelId] })
      ]);
    }
  });

  const [inviteForm, setInviteForm] = useState<InviteFormState>({ email: "", role: "manager", alias: "" });
  const [inviteResult, setInviteResult] = useState<InviteResponse | null>(null);
  const [linkCopied, setLinkCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const [editingAliasUserId, setEditingAliasUserId] = useState<number | null>(null);
  const [aliasDraft, setAliasDraft] = useState("");
  const [aliasError, setAliasError] = useState<string | null>(null);

  useEffect(() => {
    if (!rolesQuery.data || activeAssignableRoles.some((role) => role.code === inviteForm.role)) return;
    setInviteForm((current) => ({ ...current, role: defaultAssignableRole?.code ?? "" }));
  }, [activeAssignableRoles, defaultAssignableRole, inviteForm.role, rolesQuery.data]);

  const aliasesByUserId = useMemo(
    () => new Map((aliasesQuery.data?.items ?? []).map((entry) => [entry.user_id, entry])),
    [aliasesQuery.data?.items]
  );

  const handleInvite = async () => {
    if (!activeAssignableRoles.some((role) => role.code === inviteForm.role)) return;
    try {
      const response = await inviteMutation.mutateAsync({
        ...inviteForm,
        email: inviteForm.email.trim(),
        alias: inviteForm.alias?.trim() || null
      }) as InviteResponse;
      setInviteResult(response);
      setLinkCopied(false);
      setCopyError(false);
      setInviteForm({ email: "", role: defaultAssignableRole?.code ?? "", alias: "" });
    } catch {
      // The mutation state renders the safe backend error below.
    }
  };

  const handleRoleChange = async (userId: number, role: string) => {
    if (!activeAssignableRoles.some((item) => item.code === role)) return;
    if (!window.confirm(t("hotelRoles.roleChangePermissionConfirm", { role: roleDisplayName(role) }))) return;
    try {
      await updateRoleMutation.mutateAsync({ userId, role });
    } catch {
      // The mutation state renders the safe backend error below.
    }
  };

  const handleRevoke = async (userId: number) => {
    try {
      await revokeMutation.mutateAsync(userId);
    } catch {
      // The mutation state renders the safe backend error below.
    }
  };

  const handleResend = async () => {
    if (!inviteResult) return;
    try {
      const response = await resendMutation.mutateAsync(inviteResult.invitation_id);
      setInviteResult((current) => current ? { ...current, ...response } : response);
    } catch {
      // The mutation state renders the safe backend error below.
    }
  };

  const copyInvitationLink = async () => {
    if (!inviteResult?.accept_url) return;
    try {
      await navigator.clipboard.writeText(inviteResult.accept_url);
      setLinkCopied(true);
      setCopyError(false);
    } catch {
      setLinkCopied(false);
      setCopyError(true);
    }
  };

  const startAliasEdit = (userId: number, currentAlias: string | null) => {
    setEditingAliasUserId(userId);
    setAliasDraft(currentAlias ?? "");
    setAliasError(null);
  };

  const saveAlias = async (userId: number) => {
    setAliasError(null);
    try {
      await updateAliasMutation.mutateAsync({ userId, alias: aliasDraft.trim() || null });
      setEditingAliasUserId(null);
      setAliasDraft("");
    } catch (err) {
      setAliasError((err as Error).message || "No se pudo guardar el alias.");
    }
  };

  if (!hasValidSession(session)) {
    return <p className="text-sm text-slate-600">Iniciá sesión con un hotel activo para administrar usuarios.</p>;
  }

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Configuración</p>
        <h1 className="text-balance text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">Usuarios y roles</h1>
        <p className="text-sm text-slate-600">Invitá usuarios a este hotel y asignales un rol.</p>
      </header>

      {canManage && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-800">Invitar usuario</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <input
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
              aria-label="Email de invitación"
              placeholder="email@hotel.com"
              value={inviteForm.email}
              onChange={(e) => setInviteForm((p) => ({ ...p, email: e.target.value }))}
              type="email"
              autoComplete="email"
              required
            />
            <input
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
              aria-label="Alias del usuario (opcional)"
              placeholder="Alias (opcional)"
              value={inviteForm.alias ?? ""}
              maxLength={80}
              onChange={(e) => setInviteForm((p) => ({ ...p, alias: e.target.value }))}
            />
            <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600" htmlFor="invite-user-role">
              {t("hotelRoles.inviteRole")}
              <select
                id="invite-user-role"
                className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal text-slate-900"
                value={activeAssignableRoles.some((role) => role.code === inviteForm.role) ? inviteForm.role : ""}
                disabled={rolesQuery.isLoading || rolesQuery.isError || activeAssignableRoles.length === 0 || inviteMutation.isPending}
                onChange={(e) => setInviteForm((p) => ({ ...p, role: e.target.value }))}
              >
                <option value="" disabled>{t("hotelRoles.selectAssignable")}</option>
                {activeAssignableRoles.map((role) => (
                  <option key={role.code} value={role.code}>{roleOptionLabel(role)}</option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => void handleInvite()}
              disabled={inviteMutation.isPending || !inviteForm.email.trim() || !activeAssignableRoles.some((role) => role.code === inviteForm.role)}
              className="rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-60"
            >
              {inviteMutation.isPending ? "Creando invitación..." : "Invitar"}
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500">{t("hotelRoles.assignmentBoundary")}</p>
          {rolesQuery.isLoading ? <p className="mt-2 text-sm text-slate-500" role="status">{t("hotelRoles.rolesLoading")}</p> : null}
          {rolesQuery.isError ? <p className="mt-2 text-sm text-rose-700" role="alert">{t("hotelRoles.rolesError")}</p> : null}
          {rolesQuery.isSuccess && activeAssignableRoles.length === 0 ? <p className="mt-2 text-sm text-slate-600" role="status">{t("hotelRoles.noAssignable")}</p> : null}
          {inviteResult && (
            <div className={inviteResult.email_delivery === "sent"
              ? "mt-3 space-y-2 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900"
              : "mt-3 space-y-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950"
            } role={inviteResult.email_delivery === "sent" ? "status" : "alert"}>
              <p>
                {inviteResult.email_delivery === "sent"
                  ? "Invitación creada y enviada por email."
                  : inviteResult.email_delivery === "failed"
                    ? "La invitación quedó creada, pero no se pudo enviar el email. Compartí el enlace o reintentá el envío."
                    : "La invitación quedó creada, pero el envío de email no está configurado. Compartí el enlace cuando el correo no esté disponible."
                }
              </p>
              <p className="text-xs opacity-80">{t("hotelRoles.latestInvitationLinkNotice")}</p>
              <div className="flex flex-wrap items-center gap-2">
                {inviteResult.accept_url && (
                  <a className="font-semibold text-brand-700 hover:underline" href={inviteResult.accept_url} target="_blank" rel="noreferrer">
                    Abrir invitación
                  </a>
                )}
                <button
                  type="button"
                  className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                  onClick={() => void copyInvitationLink()}
                  disabled={!inviteResult.accept_url}
                >
                  {linkCopied ? "Enlace copiado" : "Copiar enlace"}
                </button>
                {inviteResult.email_delivery !== "sent" && (
                  <button
                    type="button"
                    onClick={() => void handleResend()}
                    disabled={resendMutation.isPending}
                    className="rounded-lg bg-brand-600 px-3 py-2 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                  >
                    {resendMutation.isPending ? "Reintentando..." : "Reintentar envío"}
                  </button>
                )}
              </div>
              {copyError && <p className="text-xs">No se pudo copiar automáticamente. Abrí el enlace y copiá la dirección desde el navegador.</p>}
              {resendMutation.isError && <p role="alert" className="text-xs text-rose-700">{(resendMutation.error as Error).message || "No se pudo reintentar el envío."}</p>}
            </div>
          )}
          {inviteMutation.isError && (
            <p className="mt-2 text-sm text-rose-600">
              {(inviteMutation.error as Error).message || "No se pudo invitar"}
            </p>
          )}
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-800">Usuarios del hotel</h2>
          {usersQuery.isFetching && <span className="text-xs text-slate-500">Actualizando...</span>}
        </div>
        {canManage && (
          <p role="note" className="mt-2 text-xs text-slate-600">
            {t("hotelRoles.roleChangePermissionNotice")}
          </p>
        )}
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-3 py-2 text-left font-semibold text-slate-600">Email</th>
                {canManage && <th className="px-3 py-2 text-left font-semibold text-slate-600">Alias</th>}
                <th className="px-3 py-2 text-left font-semibold text-slate-600">Rol</th>
                <th className="px-3 py-2 text-left font-semibold text-slate-600">Estado</th>
                <th className="px-3 py-2 text-right font-semibold text-slate-600">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {(usersQuery.data || []).map((u) => (
                <tr key={u.id}>
                  <td className="px-3 py-2">{u.email}</td>
                  {canManage && (
                    <td className="min-w-48 px-3 py-2">
                      {(() => {
                        const membership = aliasesByUserId.get(u.id);
                        if (!membership) return <span className="text-slate-400">—</span>;
                        if (editingAliasUserId !== u.id) {
                          return (
                            <div className="flex items-center gap-2">
                              <span className="min-w-0 truncate text-slate-700">{membership.alias || <span className="text-slate-400">Sin alias</span>}</span>
                              <button
                                type="button"
                                onClick={() => startAliasEdit(u.id, membership.alias)}
                                className="shrink-0 rounded border border-slate-200 px-2 py-1 text-xs font-semibold text-brand-700 hover:bg-brand-50"
                                aria-label={`Editar alias de ${u.email}`}
                              >
                                Editar
                              </button>
                            </div>
                          );
                        }
                        return (
                          <div className="flex min-w-56 flex-col gap-2">
                            <input
                              aria-label={`Alias de ${u.email}`}
                              className="w-full rounded-lg border border-slate-200 px-2 py-1.5 text-sm"
                              value={aliasDraft}
                              maxLength={80}
                              onChange={(event) => setAliasDraft(event.target.value)}
                            />
                            <div className="flex flex-wrap gap-2">
                              <button
                                type="button"
                                onClick={() => void saveAlias(u.id)}
                                disabled={updateAliasMutation.isPending}
                                className="rounded bg-brand-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60"
                              >
                                Guardar
                              </button>
                              <button
                                type="button"
                                onClick={() => setEditingAliasUserId(null)}
                                disabled={updateAliasMutation.isPending}
                                className="rounded border border-slate-200 px-2 py-1 text-xs font-semibold text-slate-700"
                              >
                                Cancelar
                              </button>
                            </div>
                            {aliasError && <span role="alert" className="text-xs text-rose-700">{aliasError}</span>}
                          </div>
                        );
                      })()}
                    </td>
                  )}
                  <td className="px-3 py-2">
                    {canManage && session.userId !== u.email ? (
                      <select
                        className="rounded-lg border border-slate-200 px-2 py-1 text-sm"
                        aria-label={`Rol de ${u.email}`}
                        value={u.role}
                        disabled={rolesQuery.isLoading || rolesQuery.isError || updateRoleMutation.isPending}
                        onChange={(e) => void handleRoleChange(u.id, e.target.value)}
                      >
                        {!activeAssignableRoles.some((role) => role.code === u.role) ? (
                          <option value={u.role} disabled>{`${roleDisplayName(u.role)} — ${t("hotelRoles.unavailable")}`}</option>
                        ) : null}
                        {activeAssignableRoles.map((role) => (
                          <option key={role.code} value={role.code}>{roleOptionLabel(role)}</option>
                        ))}
                      </select>
                    ) : (
                      roleDisplayName(u.role)
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {u.is_active ? (
                      <span className="rounded-full bg-emerald-50 px-2 py-1 text-xs text-emerald-700">Activo</span>
                    ) : (
                      <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">Inactivo</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {canManage && session.userId !== u.email && (
                      <button
                        type="button"
                        onClick={() => void handleRevoke(u.id)}
                        className="text-sm font-semibold text-rose-600 hover:underline"
                      >
                        Revocar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {usersQuery.isError && <p className="mt-2 text-sm text-rose-600">No se pudieron cargar los usuarios.</p>}
          {aliasesQuery.isError && canManage && <p role="alert" className="mt-2 text-sm text-rose-600">No se pudieron cargar los aliases del equipo.</p>}
          {aliasesQuery.isLoading && canManage && <p role="status" className="mt-2 text-sm text-slate-500">Cargando aliases...</p>}
          {updateRoleMutation.isError && (
            <p className="mt-2 text-sm text-rose-600">
              {(updateRoleMutation.error as Error).message || "No se pudo actualizar el rol"}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
