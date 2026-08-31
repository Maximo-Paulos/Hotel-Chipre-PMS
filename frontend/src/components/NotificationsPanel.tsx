import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { type NotificationItem, type NotificationSeverity } from "../api/notifications";
import { notificationEventLabel } from "../constants/notificationEvents";
import { useDialogA11y } from "../hooks/useDialogA11y";
import { useNotificationMutations, useNotificationsInbox } from "../hooks/useNotifications";
import { useOnlineStatus } from "../hooks/useOnlineStatus";
import { useEffectivePermissions } from "../hooks/usePermissions";
import { useReservationDrawer } from "../hooks/useReservationDrawer";

type Props = {
  open: boolean;
  onClose: () => void;
};

const severityStyles: Record<NotificationSeverity, string> = {
  critical: "border-rose-200 bg-rose-50",
  warning: "border-amber-200 bg-amber-50",
  info: "border-slate-200 bg-white"
};

const severityDot: Record<NotificationSeverity, string> = {
  critical: "bg-rose-600",
  warning: "bg-amber-500",
  info: "bg-slate-400"
};

const severityLabel: Record<NotificationSeverity, string> = {
  critical: "Crítica",
  warning: "Advertencia",
  info: "Info"
};

const formatRelativeTime = (iso: string): string => {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.round(diffMs / 60_000);
  if (diffMin < 1) return "ahora";
  if (diffMin < 60) return `hace ${diffMin} min`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `hace ${diffHr} h`;
  const diffDay = Math.round(diffHr / 24);
  return `hace ${diffDay} d`;
};

export function NotificationsPanel({ open, onClose }: Props) {
  const containerRef = useDialogA11y(open, onClose);
  const isOnline = useOnlineStatus();
  const [showUnreadOnly, setShowUnreadOnly] = useState(false);
  const [limit, setLimit] = useState(20);
  const inboxQuery = useNotificationsInbox(showUnreadOnly, limit, 0);
  const { markReadMutation, markAllReadMutation } = useNotificationMutations();
  const { hasAnyPermission } = useEffectivePermissions();
  const { openReservation } = useReservationDrawer();
  const navigate = useNavigate();
  const canOpenReservations = hasAnyPermission(["reservation:create", "checkin:perform"]);

  if (!open) return null;

  const items = inboxQuery.data?.items ?? [];
  const unreadCount = inboxQuery.data?.unread_count ?? 0;

  // Only entities this frontend actually has a page/drawer for become
  // clickable. entity_type/entity_id are all NotificationRead exposes (see
  // api/notifications.ts) -- there is no guest_id on a guest_restriction
  // notification, so that one is deliberately not clickable rather than
  // guessing a route.
  const handleItemClick = async (item: NotificationItem) => {
    if (!item.is_read) {
      try {
        await markReadMutation.mutateAsync(item.id);
      } catch {
        // Navigating to the linked entity remains useful even if marking read fails.
      }
    }
    if (item.entity_type === "reservation" && item.entity_id && canOpenReservations) {
      openReservation(item.entity_id);
      onClose();
      return;
    }
    if (item.entity_type === "stock_item" && item.entity_id) {
      navigate("/operacion/stock");
      onClose();
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllReadMutation.mutateAsync();
    } catch {
      // The inbox remains visible so the operator can retry.
    }
  };

  const isClickable = (item: NotificationItem) =>
    (item.entity_type === "reservation" && Boolean(item.entity_id) && canOpenReservations) ||
    (item.entity_type === "stock_item" && Boolean(item.entity_id));

  return (
    <div
      className="fixed inset-0 z-50 flex animate-fade-in items-start justify-center bg-slate-900/40 px-4 py-6 sm:items-center"
      onClick={onClose}
    >
      <div
        ref={containerRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="notifications-panel-title"
        className="flex max-h-[85vh] w-full max-w-sm animate-scale-in flex-col rounded-xl border border-slate-200 bg-white shadow-xl outline-none"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-slate-100 p-5 pb-3">
          <div>
            <h2 id="notifications-panel-title" className="text-base font-semibold text-slate-900">
              Alertas
            </h2>
            {unreadCount > 0 && (
              <p className="mt-0.5 text-xs font-semibold text-brand-700" data-testid="notifications-unread-count">
                {unreadCount} sin leer
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar alertas"
            className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg text-lg leading-none text-slate-500 hover:bg-slate-100 hover:text-slate-800"
          >
            ×
          </button>
        </div>

        <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-5 py-2">
          <label className="flex min-h-11 items-center gap-2 text-xs font-medium text-slate-600">
            <input
              type="checkbox"
              checked={showUnreadOnly}
              onChange={(event) => setShowUnreadOnly(event.target.checked)}
            />
            Solo no leídas
          </label>
          {unreadCount > 0 && (
            <button
              type="button"
              onClick={() => void handleMarkAllRead()}
              disabled={markAllReadMutation.isPending || !isOnline}
              className="min-h-11 rounded-lg px-2 text-xs font-semibold text-brand-700 hover:bg-brand-50 disabled:opacity-60"
            >
              Marcar todas como leídas
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-3">
          {!isOnline ? (
            <p className="p-2 text-sm text-slate-600" role="status">
              Sin conexión. Las alertas se actualizan cuando vuelvas a estar online.
            </p>
          ) : inboxQuery.isLoading ? (
            <p className="p-2 text-sm text-slate-500" role="status">
              Cargando alertas...
            </p>
          ) : inboxQuery.isError ? (
            <div className="space-y-2 p-2">
              <p className="text-sm text-rose-700">No se pudieron cargar las alertas.</p>
              <button
                type="button"
                onClick={() => inboxQuery.refetch()}
                className="min-h-11 rounded-lg border border-slate-200 px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Reintentar
              </button>
            </div>
          ) : items.length === 0 ? (
            <p className="p-2 text-sm text-slate-600">
              {showUnreadOnly ? "No tenés alertas sin leer." : "Todavía no hay alertas para mostrar acá."}
            </p>
          ) : (
            <ul className="space-y-2">
              {items.map((item) => {
                const clickable = isClickable(item);
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => handleItemClick(item)}
                      disabled={!clickable && item.is_read}
                      data-testid={`notification-item-${item.id}`}
                      className={`flex w-full min-h-11 items-start gap-2 rounded-lg border p-3 text-left text-sm ${severityStyles[item.severity]} ${
                        clickable ? "cursor-pointer hover:brightness-95" : item.is_read ? "cursor-default" : "cursor-pointer"
                      }`}
                    >
                      <span
                        aria-hidden="true"
                        className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${severityDot[item.severity]}`}
                        title={severityLabel[item.severity]}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center justify-between gap-2">
                          <span className={`truncate font-semibold ${item.is_read ? "text-slate-700" : "text-slate-900"}`}>
                            {item.title}
                          </span>
                          {!item.is_read && (
                            <span className="h-2 w-2 shrink-0 rounded-full bg-brand-600" aria-label="No leída" />
                          )}
                        </span>
                        {item.body && <span className="mt-0.5 block break-words text-xs text-slate-600">{item.body}</span>}
                        <span className="mt-1 flex items-center gap-2 text-[11px] text-slate-400">
                          <span>{notificationEventLabel(item.event_type)}</span>
                          <span>·</span>
                          <span>{formatRelativeTime(item.created_at)}</span>
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          {isOnline && !inboxQuery.isLoading && items.length > 0 && items.length === limit && (
            <button
              type="button"
              onClick={() => setLimit((current) => current + 20)}
              className="mt-2 min-h-11 w-full rounded-lg border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              Cargar más
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default NotificationsPanel;
