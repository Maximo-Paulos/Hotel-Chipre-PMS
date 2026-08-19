// The concrete event_type strings this backend actually enqueues today --
// see the enqueue_notifications_for_event call sites: app/services/
// reservation_service.py, checkin_service.py, guest_restriction_service.py,
// stock_service.py, notification_service.py (report.daily). event_type is a
// free string on the backend (no enum), so this list is a UI convenience for
// the preferences screen, not a contract -- an unlisted event_type still
// works fine through the "" (default) preference row.
export const KNOWN_NOTIFICATION_EVENT_TYPES: { value: string; label: string }[] = [
  { value: "reservation.created", label: "Reserva creada" },
  { value: "reservation.updated", label: "Reserva modificada" },
  { value: "reservation.cancelled", label: "Reserva cancelada" },
  { value: "reservation.no_show", label: "No-show" },
  { value: "reservation.checked_in", label: "Check-in realizado" },
  { value: "reservation.checked_out", label: "Check-out realizado" },
  { value: "guest.restriction.created", label: "Restricción de huésped creada" },
  { value: "guest.restriction.resolved", label: "Restricción de huésped resuelta" },
  { value: "guest.restriction.overridden", label: "Restricción de huésped anulada" },
  { value: "stock.low", label: "Stock bajo" },
  { value: "stock.out_of_stock", label: "Stock agotado" },
  { value: "report.daily", label: "Reporte diario" }
];

export const notificationEventLabel = (eventType: string): string =>
  KNOWN_NOTIFICATION_EVENT_TYPES.find((item) => item.value === eventType)?.label ?? eventType;

// Mirrors DEFAULT_DAILY_REPORT_SECTIONS in app/services/notification_service.py.
// Not part of the schema (DailyReportScheduleRead.sections is a free
// list[str]) -- this is the concrete set the backend actually understands
// when it builds the daily report.
export const DAILY_REPORT_SECTIONS: { value: string; label: string }[] = [
  { value: "occupancy", label: "Ocupación" },
  { value: "arrivals", label: "Llegadas" },
  { value: "departures", label: "Salidas" },
  { value: "pending_payments", label: "Pagos pendientes" },
  { value: "late_arrivals", label: "Llegadas tardías" },
  { value: "room_blocks", label: "Bloqueos de habitación" },
  { value: "cash_session", label: "Caja" },
  { value: "low_stock", label: "Stock bajo" },
  { value: "laundry_outbound", label: "Lavandería saliente" },
  { value: "critical_alerts", label: "Alertas críticas" }
];

// Backend accepts any role string for DailyReportSchedule.recipient_roles;
// this is the concrete set of roles that actually exist (see
// state/session.tsx's Role type / ui/UserBadge.tsx's roleLabels, reused for
// the labels themselves).
export const DAILY_REPORT_ROLE_OPTIONS: string[] = ["owner", "co_owner", "manager", "receptionist", "housekeeping"];
