import { type ReservationStatus } from "../api/reservations";

// Single source of truth for reservation status vocabulary and the status
// transitions that gate operator actions. Extracted from ReservationsPage
// so the new ReservationDetailDrawer (B1) shows the same labels/colors and
// enables the same actions instead of re-deriving its own rules.
export const reservationStatusConfig: Record<ReservationStatus, { label: string; className: string }> = {
  pending: { label: "Pendiente", className: "bg-slate-100 text-slate-800" },
  deposit_paid: { label: "Seña", className: "bg-amber-100 text-amber-800" },
  fully_paid: { label: "Pago completo", className: "bg-emerald-100 text-emerald-800" },
  pre_check_in: { label: "Pre check-in", className: "bg-teal-100 text-teal-800" },
  checked_in: { label: "Check-in", className: "bg-emerald-200 text-emerald-900" },
  checked_out: { label: "Check-out", className: "bg-sky-100 text-sky-800" },
  cancelled: { label: "Cancelada", className: "bg-rose-100 text-rose-800" },
  no_show: { label: "No-show", className: "bg-violet-100 text-violet-800" }
};

export const canCancelReservation = (status: ReservationStatus) =>
  status !== "cancelled" && status !== "checked_out" && status !== "checked_in";

export const canCheckInReservation = (status: ReservationStatus) =>
  ["pending", "deposit_paid", "fully_paid", "pre_check_in"].includes(status);

export const canCheckOutReservation = (status: ReservationStatus) => status === "checked_in";

// B3.1: PRE_CHECK_IN is only reachable from fully_paid (see VALID_TRANSITIONS
// in app/models/reservation.py) -- once already pre_check_in, only the final
// confirmation (canCheckInReservation) makes sense.
export const canPartialCheckIn = (status: ReservationStatus) => status === "fully_paid";
