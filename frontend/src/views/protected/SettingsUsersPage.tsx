import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { inviteUser, listUsers, revokeUser, updateUserRole } from "../../api/users";
import { type AuthUser } from "../../api/auth";
import { useSession } from "../../state/session";

const roleLabels: Record<string, string> = {
  owner: "Owner",
  co_owner: "Co-owner",
  manager: "Manager",
  housekeeping: "Housekeeping"
};

export function SettingsUsersPage() {
  const { session } = useSession();
  const qc = useQueryClient();
  const usersQuery = useQuery<AuthUser[]>({
    queryKey: ["users", session.hotelId],
    queryFn: () => listUsers(session)
  });
  const inviteMutation = useMutation({
    mutationFn: (payload: { email: string; role: string; password?: string }) => inviteUser(payload as any, session),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users", session.hotelId] })
  });
  const revokeMutation = useMutation({
    mutationFn: (userId: number) => revokeUser(userId, session),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users", session.hotelId] })
  });
  const updateRoleMutation = useMutation({
    mutationFn: (payload: { userId: number; role: string }) => updateUserRole(payload.userId, payload.role as any, session),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users", session.hotelId] })
  });

  const [inviteForm, setInviteForm] = useState({ email: "", role: "manager" });

  const canManage = ["owner", "co_owner"].includes(session.role);

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Settings</p>
        <h1 className="text-2xl font-semibold text-slate-900">Usuarios y roles</h1>
        <p className="text-sm text-slate-600">Invitá usuarios a este hotel y asignales un rol.</p>
      </header>

      {canManage && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-800">Invitar usuario</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <input
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="email@hotel.com"
              value={inviteForm.email}
              onChange={(e) => setInviteForm((p) => ({ ...p, email: e.target.value }))}
            />
            <select
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
              value={inviteForm.role}
              onChange={(e) => setInviteForm((p) => ({ ...p, role: e.target.value }))}
            >
              <option value="co_owner">Co-owner</option>
              <option value="manager">Manager</option>
              <option value="housekeeping">Housekeeping</option>
            </select>
            <button
              type="button"
              onClick={() => inviteMutation.mutate(inviteForm)}
              disabled={inviteMutation.isLoading || !inviteForm.email}
              className="rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-60"
            >
              {inviteMutation.isLoading ? "Enviando..." : "Invitar"}
            </button>
          </div>
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
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-3 py-2 text-left font-semibold text-slate-600">Email</th>
                <th className="px-3 py-2 text-left font-semibold text-slate-600">Rol</th>
                <th className="px-3 py-2 text-left font-semibold text-slate-600">Estado</th>
                <th className="px-3 py-2 text-right font-semibold text-slate-600">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {(usersQuery.data || []).map((u) => (
                <tr key={u.id}>
                  <td className="px-3 py-2">{u.email}</td>
                  <td className="px-3 py-2">
                    {canManage && session.userId !== u.email ? (
                      <select
                        className="rounded-lg border border-slate-200 px-2 py-1 text-sm"
                        value={u.role}
                        onChange={(e) => updateRoleMutation.mutate({ userId: u.id, role: e.target.value })}
                      >
                        <option value="co_owner">Co-owner</option>
                        <option value="manager">Manager</option>
                        <option value="housekeeping">Housekeeping</option>
                      </select>
                    ) : (
                      roleLabels[u.role] || u.role
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
                        onClick={() => revokeMutation.mutate(u.id)}
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
