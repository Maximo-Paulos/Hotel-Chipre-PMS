import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { hasValidSession } from "../../api/client";
import { listUserSessions, revokeUserSession } from "../../api/security";
import { useSession } from "../../state/session";
import { refreshSettingsState } from "../../api/queryInvalidation";
import { useGuardedMutation } from "../../hooks/useGuardedMutation";

const formatDate = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Fecha no disponible" : date.toLocaleString("es-AR");
};

export function SettingsSessionsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { session, logout } = useSession();
  const enabled = hasValidSession(session);
  const sessionsQuery = useQuery({
    queryKey: ["settings-sessions", session.hotelId],
    queryFn: () => listUserSessions(session),
    enabled,
    staleTime: 15 * 1000
  });
  const sessions = sessionsQuery.data ?? [];

  const revokeMutation = useGuardedMutation({
    mutationFn: (sessionId: number) => revokeUserSession(sessionId, session),
    onSuccess: async (_response, sessionId) => {
      const revokedSession = sessions.find((item) => item.id === sessionId);
      if (revokedSession?.current) {
        logout();
        navigate("/login?sessions=revoked", { replace: true });
        return;
      }
      await refreshSettingsState(queryClient, session.hotelId);
    }
  });

  const handleRevoke = async (sessionId: number, current: boolean, deviceLabel: string) => {
    const question = current
      ? "¿Cerrar la sesión de este dispositivo? Tendrás que volver a iniciar sesión."
      : `¿Revocar la sesión de ${deviceLabel}?`;
    if (!window.confirm(question)) return;
    try {
      await revokeMutation.mutateAsync(sessionId);
    } catch {
      // The mutation exposes the error state in the page; keeping the handler
      // awaited prevents a rejected promise from escaping the click event.
    }
  };

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Configuración</p>
        <h1 className="text-2xl font-semibold text-slate-900">Dispositivos y sesiones activas</h1>
        <p className="text-sm text-slate-600">
          Revisá dónde está abierta tu cuenta y revocá cualquier dispositivo que ya no reconozcas.
        </p>
      </header>

      {sessionsQuery.isError && (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          No se pudieron cargar las sesiones activas.
          <button type="button" onClick={() => void sessionsQuery.refetch()} className="ml-2 font-semibold underline">
            Reintentar
          </button>
        </div>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" aria-label="Sesiones activas">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Acceso de la cuenta</p>
            <h2 className="text-lg font-semibold text-slate-900">Tus dispositivos</h2>
          </div>
          {sessionsQuery.isFetching && <span className="text-xs text-slate-500">Actualizando...</span>}
        </div>

        {sessionsQuery.isLoading ? (
          <p className="mt-4 text-sm text-slate-500" role="status">Cargando dispositivos...</p>
        ) : sessions.length ? (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold text-slate-600">Dispositivo</th>
                  <th className="px-3 py-2 text-left font-semibold text-slate-600">Creada</th>
                  <th className="px-3 py-2 text-left font-semibold text-slate-600">Última actividad</th>
                  <th className="px-3 py-2 text-right font-semibold text-slate-600">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {sessions.map((item) => (
                  <tr key={item.id}>
                    <td className="px-3 py-3">
                      <div className="font-medium text-slate-900">{item.device_label}</div>
                      {item.current && (
                        <span className="mt-1 inline-flex rounded-full bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700">
                          Este dispositivo
                        </span>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-slate-600">{formatDate(item.created_at)}</td>
                    <td className="whitespace-nowrap px-3 py-3 text-slate-600">{formatDate(item.last_seen_at)}</td>
                    <td className="px-3 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => handleRevoke(item.id, item.current, item.device_label)}
                        disabled={revokeMutation.isPending}
                        className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-800 hover:bg-rose-100 disabled:opacity-60"
                        data-testid={`session-revoke-${item.id}`}
                      >
                        {revokeMutation.isPending ? "Revocando..." : item.current ? "Cerrar sesión" : "Revocar"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : !sessionsQuery.isError ? (
          <p className="mt-4 text-sm text-slate-500">No hay sesiones activas para mostrar.</p>
        ) : null}

        {revokeMutation.isError && (
          <p role="alert" className="mt-3 text-sm text-rose-700">No se pudo revocar la sesión. Reintentá.</p>
        )}
      </section>
    </div>
  );
}
