import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { type NotificationPreference, type NotificationPreferenceUpdate } from "../../api/notifications";
import { listUsers } from "../../api/users";
import { hasValidSession } from "../../api/client";
import {
  DAILY_REPORT_ROLE_OPTIONS,
  DAILY_REPORT_SECTIONS,
  KNOWN_NOTIFICATION_EVENT_TYPES,
  notificationEventLabel
} from "../../constants/notificationEvents";
import {
  useDailyReportSchedule,
  useDailyReportScheduleMutation,
  useNotificationPreferenceMutation,
  useNotificationPreferences
} from "../../hooks/useNotifications";
import { useOnlineStatus } from "../../hooks/useOnlineStatus";
import { usePushSubscription } from "../../hooks/usePushSubscription";
import { useSession } from "../../state/session";
import { roleLabels } from "../../ui/UserBadge";

const CHANNEL_OPTIONS: { value: "in_app" | "push" | "email"; label: string }[] = [
  { value: "in_app", label: "En la app" },
  { value: "push", label: "Push" },
  { value: "email", label: "Email" }
];

function PushSubscriptionCard() {
  const push = usePushSubscription();

  if (!push.isOnline) {
    return (
      <Card title="Notificaciones push">
        <p className="text-sm text-slate-600">Sin conexión. Conectate para activar o revisar las notificaciones push.</p>
      </Card>
    );
  }

  if (!push.supported) {
    return (
      <Card title="Notificaciones push">
        <p className="text-sm text-slate-600">Este navegador no soporta notificaciones push.</p>
      </Card>
    );
  }

  if (push.iosNeedsInstall) {
    return (
      <Card title="Notificaciones push">
        <p className="text-sm text-slate-600">
          En iPhone/iPad, Safari solo permite activar notificaciones push desde la app ya instalada en la pantalla de
          inicio -- no desde una pestaña normal del navegador.
        </p>
        <p className="mt-2 text-sm text-slate-600">
          Para instalarla: tocá el botón <strong>Compartir</strong> en Safari y elegí{" "}
          <strong>Agregar a pantalla de inicio</strong>. Después abrí Hotel Chipre PMS desde el ícono que se creó y
          volvé a esta pantalla.
        </p>
      </Card>
    );
  }

  if (!push.vapidConfigured) {
    return (
      <Card title="Notificaciones push">
        <p className="text-sm text-slate-600">Las notificaciones push no están configuradas para este hotel todavía.</p>
      </Card>
    );
  }

  if (push.permission === "denied") {
    return (
      <Card title="Notificaciones push">
        <p className="text-sm text-rose-700">
          Las notificaciones están bloqueadas para este sitio a nivel del navegador o del sistema operativo. Habilitalas
          desde la configuración de notificaciones del dispositivo/navegador y volvé a intentar.
        </p>
      </Card>
    );
  }

  return (
    <Card title="Notificaciones push">
      {push.error && <p className="mb-2 text-sm text-rose-700">{push.error}</p>}
      {push.needsReconnect && (
        <p className="mb-2 text-sm text-amber-800">
          La suscripción push de este dispositivo se perdió o expiró. Reconectá para seguir recibiendo alertas acá.
        </p>
      )}
      {push.subscribed ? (
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-sm text-emerald-700">Notificaciones push activadas en este dispositivo.</p>
          <button
            type="button"
            onClick={() => push.unsubscribe()}
            disabled={push.loading}
            className="min-h-11 rounded-lg border border-slate-200 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          >
            {push.loading ? "..." : "Desactivar"}
          </button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-sm text-slate-600">
            Activá para recibir alertas de reservas, check-in/out y stock en este dispositivo, incluso con la app
            cerrada.
          </p>
          <button
            type="button"
            onClick={() => push.subscribe()}
            disabled={push.loading}
            className="min-h-11 shrink-0 rounded-lg bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
          >
            {push.loading ? "..." : push.needsReconnect ? "Reconectar" : "Activar notificaciones push"}
          </button>
        </div>
      )}
    </Card>
  );
}

function PreferencesCard() {
  const isOnline = useOnlineStatus();
  const preferencesQuery = useNotificationPreferences();
  const mutation = useNotificationPreferenceMutation();
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const rows = useMemo<NotificationPreference[]>(() => {
    const saved = new Map((preferencesQuery.data ?? []).map((row) => [row.event_type, row]));
    const eventTypes = ["", ...KNOWN_NOTIFICATION_EVENT_TYPES.map((item) => item.value)];
    return eventTypes.map(
      (eventType) =>
        saved.get(eventType) ?? {
          event_type: eventType,
          in_app_enabled: true,
          push_enabled: true,
          email_enabled: false,
          quiet_hours_start: null,
          quiet_hours_end: null
        }
    );
  }, [preferencesQuery.data]);

  const save = async (eventType: string, patch: Omit<NotificationPreferenceUpdate, "event_type">) => {
    setPendingKey(eventType);
    setSaveError(null);
    try {
      await mutation.mutateAsync({ event_type: eventType, ...patch });
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "No se pudo guardar la preferencia.");
    } finally {
      setPendingKey(null);
    }
  };

  return (
    <Card title="Preferencias por tipo de alerta">
      {saveError ? <p className="mb-3 text-sm text-rose-700" role="alert">{saveError}</p> : null}
      <p className="mb-3 text-sm text-slate-600">
        "Predeterminado" aplica a toda alerta sin una preferencia propia debajo. Un tipo específico siempre gana sobre
        el predeterminado.
      </p>
      {preferencesQuery.isLoading ? (
        <p className="text-sm text-slate-600">Cargando preferencias...</p>
      ) : (
        <div className="space-y-3">
          {rows.map((row) => {
            const disabled = !isOnline || pendingKey === row.event_type;
            return (
              <div key={row.event_type || "__default__"} className="rounded-lg border border-slate-200 p-3">
                <p className="text-sm font-semibold text-slate-800">
                  {row.event_type ? notificationEventLabel(row.event_type) : "Predeterminado (todas las alertas)"}
                </p>
                <div className="mt-2 flex flex-wrap gap-4">
                  {CHANNEL_OPTIONS.map((channel) => {
                    const key = `${channel.value}_enabled` as "in_app_enabled" | "push_enabled" | "email_enabled";
                    return (
                      <label key={channel.value} className="flex min-h-11 items-center gap-2 text-sm text-slate-700">
                        <input
                          type="checkbox"
                          checked={row[key]}
                          disabled={disabled}
                          onChange={(event) =>
                            void save(row.event_type, { [key]: event.target.checked } as Partial<NotificationPreferenceUpdate>)
                          }
                        />
                        {channel.label}
                      </label>
                    );
                  })}
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                  <span>Horario silencioso (hora local):</span>
                  <select
                    value={row.quiet_hours_start ?? ""}
                    disabled={disabled}
                    onChange={(event) =>
                      void save(row.event_type, {
                        quiet_hours_start: event.target.value === "" ? null : Number(event.target.value)
                      })
                    }
                    className="min-h-11 rounded-lg border border-slate-200 px-2 py-1"
                  >
                    <option value="">--</option>
                    {Array.from({ length: 24 }, (_, hour) => (
                      <option key={hour} value={hour}>
                        {hour}:00
                      </option>
                    ))}
                  </select>
                  <span>a</span>
                  <select
                    value={row.quiet_hours_end ?? ""}
                    disabled={disabled}
                    onChange={(event) =>
                      void save(row.event_type, {
                        quiet_hours_end: event.target.value === "" ? null : Number(event.target.value)
                      })
                    }
                    className="min-h-11 rounded-lg border border-slate-200 px-2 py-1"
                  >
                    <option value="">--</option>
                    {Array.from({ length: 24 }, (_, hour) => (
                      <option key={hour} value={hour}>
                        {hour}:00
                      </option>
                    ))}
                  </select>
                  {(row.quiet_hours_start !== null || row.quiet_hours_end !== null) && (
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => void save(row.event_type, { clear_quiet_hours: true })}
                      className="min-h-11 rounded-lg border border-slate-200 px-2 text-slate-700 hover:bg-slate-50"
                    >
                      Quitar
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

function DailyReportScheduleCard() {
  const isOnline = useOnlineStatus();
  const { session } = useSession();
  const scheduleQuery = useDailyReportSchedule(true);
  const mutation = useDailyReportScheduleMutation();
  const usersQuery = useQuery({
    queryKey: ["users", session.hotelId],
    queryFn: () => listUsers(session),
    enabled: hasValidSession(session)
  });

  const [hour, setHour] = useState(7);
  const [enabled, setEnabled] = useState(true);
  const [channels, setChannels] = useState<string[]>(["in_app"]);
  const [sections, setSections] = useState<string[]>(DAILY_REPORT_SECTIONS.map((s) => s.value));
  const [recipientUserIds, setRecipientUserIds] = useState<number[]>([]);
  const [recipientRoles, setRecipientRoles] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!scheduleQuery.data) return;
    setHour(scheduleQuery.data.hour);
    setEnabled(scheduleQuery.data.enabled);
    setChannels(scheduleQuery.data.channels);
    setSections(scheduleQuery.data.sections);
    setRecipientUserIds(scheduleQuery.data.recipient_user_ids);
    setRecipientRoles(scheduleQuery.data.recipient_roles);
  }, [scheduleQuery.data]);

  const toggle = (list: string[], value: string) =>
    list.includes(value) ? list.filter((item) => item !== value) : [...list, value];

  const handleSave = async () => {
    setError(null);
    try {
      await mutation.mutateAsync({ hour, recipient_user_ids: recipientUserIds, recipient_roles: recipientRoles, channels, sections, enabled });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "No se pudo guardar el reporte diario.");
    }
  };

  return (
    <Card title="Reporte diario (solo dueño/co-dueño)">
      {scheduleQuery.isLoading ? (
        <p className="text-sm text-slate-600">Cargando...</p>
      ) : (
        <div className="space-y-4">
          <label className="flex min-h-11 items-center gap-2 text-sm font-semibold text-slate-700">
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} disabled={!isOnline} />
            Enviar reporte diario
          </label>

          <label className="block text-sm font-semibold text-slate-700">
            Hora de envío (hora local del hotel)
            <select
              value={hour}
              onChange={(e) => setHour(Number(e.target.value))}
              disabled={!isOnline}
              className="mt-1 w-full max-w-[10rem] rounded-lg border border-slate-200 px-3 py-2 text-sm"
            >
              {Array.from({ length: 24 }, (_, h) => (
                <option key={h} value={h}>
                  {h}:00
                </option>
              ))}
            </select>
          </label>

          <div>
            <p className="text-sm font-semibold text-slate-700">Canales</p>
            <div className="mt-1 flex flex-wrap gap-4">
              {CHANNEL_OPTIONS.map((channel) => (
                <label key={channel.value} className="flex min-h-11 items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={channels.includes(channel.value)}
                    disabled={!isOnline}
                    onChange={() => setChannels((current) => toggle(current, channel.value))}
                  />
                  {channel.label}
                </label>
              ))}
            </div>
          </div>

          <div>
            <p className="text-sm font-semibold text-slate-700">Secciones incluidas</p>
            <div className="mt-1 grid gap-1 sm:grid-cols-2">
              {DAILY_REPORT_SECTIONS.map((section) => (
                <label key={section.value} className="flex min-h-11 items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={sections.includes(section.value)}
                    disabled={!isOnline}
                    onChange={() => setSections((current) => toggle(current, section.value))}
                  />
                  {section.label}
                </label>
              ))}
            </div>
          </div>

          <div>
            <p className="text-sm font-semibold text-slate-700">Destinatarios por rol</p>
            <div className="mt-1 flex flex-wrap gap-4">
              {DAILY_REPORT_ROLE_OPTIONS.map((role) => (
                <label key={role} className="flex min-h-11 items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={recipientRoles.includes(role)}
                    disabled={!isOnline}
                    onChange={() => setRecipientRoles((current) => toggle(current, role))}
                  />
                  {roleLabels[role as keyof typeof roleLabels]}
                </label>
              ))}
            </div>
          </div>

          <div>
            <p className="text-sm font-semibold text-slate-700">Destinatarios específicos</p>
            <div className="mt-1 grid gap-1 sm:grid-cols-2">
              {(usersQuery.data ?? []).map((user) => (
                <label key={user.id} className="flex min-h-11 items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={recipientUserIds.includes(user.id)}
                    disabled={!isOnline}
                    onChange={() =>
                      setRecipientUserIds((current) =>
                        current.includes(user.id) ? current.filter((id) => id !== user.id) : [...current, user.id]
                      )
                    }
                  />
                  {user.email}
                </label>
              ))}
            </div>
          </div>

          {error && <p className="text-sm text-rose-700">{error}</p>}
          {mutation.isSuccess && <p className="text-sm text-emerald-700">Guardado.</p>}
          <button
            type="button"
            onClick={handleSave}
            disabled={mutation.isPending || !isOnline}
            className="min-h-11 rounded-lg bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
          >
            {mutation.isPending ? "Guardando..." : "Guardar reporte diario"}
          </button>
        </div>
      )}
    </Card>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      {children}
    </section>
  );
}

export function SettingsNotificationsPage() {
  const { session } = useSession();
  const isOnline = useOnlineStatus();
  const realRole = session.baseRole ?? session.role;
  const canManageDailyReport = realRole === "owner" || realRole === "co_owner";

  if (!hasValidSession(session)) {
    return <p className="text-sm text-slate-600">Iniciá sesión con un hotel activo para ver las notificaciones.</p>;
  }

  return (
    <div className="space-y-5">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Configuración</p>
        <h1 className="text-2xl font-semibold text-slate-900">Notificaciones</h1>
        <p className="text-sm text-slate-600">Elegí cómo y cuándo recibir alertas de este hotel.</p>
        {!isOnline && (
          <p className="mt-2 rounded-md bg-amber-50 p-2 text-sm text-amber-900" role="status">
            Sin conexión: los cambios se habilitan de nuevo cuando vuelvas a estar online.
          </p>
        )}
      </header>

      <PushSubscriptionCard />
      <PreferencesCard />
      {canManageDailyReport && <DailyReportScheduleCard />}
    </div>
  );
}

export default SettingsNotificationsPage;
