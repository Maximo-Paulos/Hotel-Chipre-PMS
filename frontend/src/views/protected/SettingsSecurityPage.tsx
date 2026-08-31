import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { hasValidSession } from "../../api/client";
import { getSecurityEvents, getSecurityOverview, revokeAllSessions } from "../../api/security";
import { useSession } from "../../state/session";
import { useGuardedMutation } from "../../hooks/useGuardedMutation";

const formatEventAction = (action: string) => action.replace(/_/g, " ").replace(/:/g, " · ");

export function SettingsSecurityPage() {
  const navigate = useNavigate();
  const { session, logout } = useSession();
  const enabled = hasValidSession(session);
  const overviewQuery = useQuery({
    queryKey: ["settings-security", "overview", session.hotelId],
    queryFn: () => getSecurityOverview(session),
    enabled,
    staleTime: 15 * 1000
  });
  const eventsQuery = useQuery({
    queryKey: ["settings-security", "events", session.hotelId],
    queryFn: () => getSecurityEvents(20, session),
    enabled,
    staleTime: 15 * 1000
  });
  const revokeMutation = useGuardedMutation({
    mutationFn: () => revokeAllSessions(session),
    onSuccess: () => {
      logout();
      navigate("/login?sessions=revoked", { replace: true });
    }
  });

  const handleRevokeAll = async () => {
    const confirmed = window.confirm(
      "¿Cerrar todas tus sesiones? Tendrás que volver a iniciar sesión en este y en los demás dispositivos."
    );
    if (!confirmed) return;
    try {
      await revokeMutation.mutateAsync();
    } catch {
      // The mutation state renders the safe backend error below.
    }
  };

  const overview = overviewQuery.data;
  const events = eventsQuery.data?.events ?? [];

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Configuración</p>
        <h1 className="text-2xl font-semibold text-slate-900">Seguridad</h1>
        <p className="text-sm text-slate-600">Resumen de acceso, eventos recientes y control de tus sesiones.</p>
      </header>

      {(overviewQuery.isError || eventsQuery.isError) && (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          No se pudo cargar todo el estado de seguridad.
          <button
            type="button"
            onClick={() => {
              void overviewQuery.refetch();
              void eventsQuery.refetch();
            }}
            className="ml-2 font-semibold underline"
          >
            Reintentar
          </button>
        </div>
      )}

      {overviewQuery.isLoading ? (
        <p className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500 shadow-sm" role="status">
          Cargando resumen de seguridad...
        </p>
      ) : overview ? (
        <>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5" aria-label="Resumen de seguridad">
            <SecurityMetric label="Miembros activos" value={overview.active_members} />
            <SecurityMetric label="Invitaciones pendientes" value={overview.pending_invitations} />
            <SecurityMetric label="Eventos en 24 h" value={overview.security_events_24h} />
            <SecurityMetric label="Permisos denegados en 24 h" value={overview.permission_denials_24h} />
            <SecurityMetric label="Timeout de sesión" value={`${overview.session_timeout_minutes} min`} />
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Tu acceso</p>
                <h2 className="text-lg font-semibold text-slate-900">{overview.current_user.email}</h2>
                <p className="text-sm text-slate-600">
                  Rol {overview.current_user.role} · versión de sesión {overview.current_user.token_version}
                </p>
                <p className="text-xs text-slate-500">
                  Último ingreso: {overview.current_user.last_login ? new Date(overview.current_user.last_login).toLocaleString("es-AR") : "sin registro"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void handleRevokeAll()}
                disabled={revokeMutation.isPending}
                className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-800 hover:bg-rose-100 disabled:opacity-60"
                data-testid="security-revoke-all"
              >
                {revokeMutation.isPending ? "Cerrando sesiones..." : "Cerrar todas mis sesiones"}
              </button>
            </div>
            {revokeMutation.isError && (
              <p role="alert" className="mt-3 text-sm text-rose-700">No se pudieron cerrar las sesiones. Reintentá.</p>
            )}
          </section>
        </>
      ) : null}

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Auditoría</p>
            <h2 className="text-lg font-semibold text-slate-900">Eventos recientes</h2>
          </div>
          {eventsQuery.isFetching && <span className="text-xs text-slate-500">Actualizando...</span>}
        </div>
        {events.length ? (
          <ul className="mt-4 divide-y divide-slate-200" data-testid="security-events">
            {events.map((event) => (
              <li key={event.id} className="grid gap-1 py-3 text-sm sm:grid-cols-[minmax(0,1fr)_auto]">
                <div>
                  <p className="font-semibold capitalize text-slate-900">{formatEventAction(event.action)}</p>
                  <p className="text-xs text-slate-500">
                    {event.resource_type || "seguridad"}
                    {event.resource_id !== null && event.resource_id !== undefined ? ` #${event.resource_id}` : ""}
                    {event.actor_user_id ? ` · actor #${event.actor_user_id}` : ""}
                  </p>
                </div>
                <time className="text-xs text-slate-500" dateTime={event.created_at}>
                  {new Date(event.created_at).toLocaleString("es-AR")}
                </time>
              </li>
            ))}
          </ul>
        ) : !eventsQuery.isLoading ? (
          <p className="mt-4 text-sm text-slate-500">No hay eventos recientes para mostrar.</p>
        ) : (
          <p className="mt-4 text-sm text-slate-500" role="status">Cargando eventos...</p>
        )}
      </section>
    </div>
  );
}

function SecurityMetric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}
