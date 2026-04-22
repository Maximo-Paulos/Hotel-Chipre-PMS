import React, { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";

import {
  type Reservation,
  type ReservationPendingAction,
  type ReservationSource,
  type ReservationStatus
} from "../../api/reservations";
import { type Guest } from "../../api/guests";
import { checkRoomAvailability, type RoomAvailabilityResponse } from "../../api/rooms";
import { type PaymentMethod } from "../../api/payments";
import { useCategories } from "../../hooks/useCategories";
import { useGuest, useGuestCreate } from "../../hooks/useGuests";
import {
  usePendingReservationActions,
  useReservation,
  useReservationActionMutations,
  useReservationMutations,
  useReservationOperationsSummary,
  useReservations
} from "../../hooks/useReservations";
import { usePaymentMutation, usePaymentSummary } from "../../hooks/usePayments";
import { useRooms } from "../../hooks/useRooms";
import { useSubscriptionStatus } from "../../hooks/useSubscription";
import { useSession } from "../../state/session";
import { formatMoney, normalizeCurrencyCode } from "../../utils/currency";
import ReservationStatCard from "../../components/StatCard";

type FormState = {
  guest_id: string;
  category_id: string;
  room_id: string;
  check_in_date: string;
  check_out_date: string;
  num_adults: string;
  num_children: string;
  notes: string;
  source: ReservationSource;
  status: ReservationStatus;
};

const paymentMethodOptions: { value: PaymentMethod; label: string }[] = [
  { value: "cash", label: "Efectivo" },
  { value: "credit_card", label: "Crédito" },
  { value: "debit_card", label: "Débito" },
  { value: "mercado_pago", label: "MercadoPago" },
  { value: "bank_transfer", label: "Transferencia" },
  { value: "paypal", label: "PayPal" }
];

const statusConfig: Record<ReservationStatus, { label: string; className: string }> = {
  pending: { label: "Pendiente", className: "bg-slate-100 text-slate-800" },
  deposit_paid: { label: "Seña", className: "bg-amber-100 text-amber-800" },
  fully_paid: { label: "Pago completo", className: "bg-emerald-100 text-emerald-800" },
  checked_in: { label: "Check-in", className: "bg-emerald-200 text-emerald-900" },
  checked_out: { label: "Check-out", className: "bg-sky-100 text-sky-800" },
  cancelled: { label: "Cancelada", className: "bg-rose-100 text-rose-800" }
};

const priorityConfig: Record<ReservationPendingAction["priority"], { label: string; className: string }> = {
  critical: { label: "Crítica", className: "bg-rose-100 text-rose-800" },
  high: { label: "Alta", className: "bg-amber-100 text-amber-800" },
  medium: { label: "Media", className: "bg-sky-100 text-sky-800" },
  low: { label: "Baja", className: "bg-slate-100 text-slate-700" }
};

const defaultFormState = (): FormState => ({
  guest_id: "",
  category_id: "",
  room_id: "",
  check_in_date: "",
  check_out_date: "",
  num_adults: "1",
  num_children: "0",
  notes: "",
  source: "direct",
  status: "pending"
});

const todayIso = () => new Date().toISOString().slice(0, 10);
const reservationGuestLabel = (reservation: {
  guest?: { first_name: string; last_name: string } | null;
  guest_id: number;
}) => (reservation.guest ? `${reservation.guest.first_name} ${reservation.guest.last_name}`.trim() : `Huesped #${reservation.guest_id}`);


export function ReservationsPage() {
  const { session } = useSession();
  const [statusFilter, setStatusFilter] = useState<ReservationStatus | "all" | "">("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Reservation | null>(null);
  const [formValues, setFormValues] = useState<FormState>(defaultFormState);
  const [formError, setFormError] = useState<string | null>(null);
  const [guestForm, setGuestForm] = useState({ first_name: "", last_name: "", email: "", phone: "" });
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("cash");
  const [availabilityForm, setAvailabilityForm] = useState<{
    category_id: string;
    check_in_date: string;
    check_out_date: string;
  }>({
    category_id: "",
    check_in_date: todayIso(),
    check_out_date: (() => {
      const d = new Date();
      d.setDate(d.getDate() + 1);
      return d.toISOString().slice(0, 10);
    })()
  });
  const [calendarRange, setCalendarRange] = useState<"week" | "month">("week");
  const [detailsReservationId, setDetailsReservationId] = useState<number | null>(null);
  const [guestIdOpen, setGuestIdOpen] = useState<number | null>(null);
  const toastTimeout = useRef<number | null>(null);
  const [toast, setToast] = useState<{ type: "success" | "error" | "info"; message: string } | null>(null);
  const { data: subscription } = useSubscriptionStatus();
  const writeBlocked = subscription?.can_write === false;
  const limitReached =
    subscription &&
    typeof subscription.room_limit === "number" &&
    subscription.room_limit > 0 &&
    subscription.rooms_in_use >= subscription.room_limit;
  const inactiveSubscription = subscription && subscription.status !== "active";
  const subscriptionBlocked = Boolean(subscription) && (inactiveSubscription || limitReached || writeBlocked);
  const subscriptionBlockReason = subscriptionBlocked
    ? writeBlocked
      ? "Suscripción en modo solo lectura: reactivá el plan para habilitar acciones de reserva."
      : inactiveSubscription
        ? "Suscripción inactiva: reactivá tu plan para operar reservas."
        : `Alcanzaste tu cupo de habitaciones (${subscription?.rooms_in_use}/${subscription?.room_limit}).`
    : null;

  const filters = {
    status: statusFilter,
    fromDate: fromDate || undefined,
    toDate: toDate || undefined
  };

  const { data: reservations = [], isLoading, isFetching, error } = useReservations(filters);
  const pendingActionsQuery = usePendingReservationActions(12);
  const { roomsQuery } = useRooms();
  const { data: categoriesData = [] } = useCategories();
  const guestMutation = useGuestCreate();
  const guestQuery = useGuest(guestIdOpen ?? undefined);
  const paymentSummaryQuery = usePaymentSummary(editing?.id || undefined);
  const detailsReservationQuery = useReservation(detailsReservationId ?? undefined);
  const detailsReservation =
    detailsReservationQuery.data ?? reservations.find((item) => item.id === detailsReservationId) ?? null;
  const detailsSummaryQuery = usePaymentSummary(detailsReservationId || undefined);
  const detailsOperationsQuery = useReservationOperationsSummary(detailsReservationId || undefined);
  const paymentMutation = usePaymentMutation(editing?.id || undefined);
  const availabilityMutation = useMutation<RoomAvailabilityResponse, unknown, { category_id: number; check_in_date: string; check_out_date: string }>({
    mutationFn: (payload) => checkRoomAvailability(payload, session)
  });
  const { createMutation, updateMutation, cancelMutation, checkInMutation, checkOutMutation } = useReservationMutations(filters);
  const { resolveExternalMutation, clearManualReviewMutation } = useReservationActionMutations(filters);

  const showToast = (type: "success" | "error" | "info", message: string) => {
    if (toastTimeout.current) {
      window.clearTimeout(toastTimeout.current);
    }
    setToast({ type, message });
    toastTimeout.current = window.setTimeout(() => setToast(null), 3800);
  };

  const today = todayIso();
  const totalRooms = roomsQuery.data?.length ?? 0;

  const categoryOptions = useMemo(
    () => categoriesData.map((cat) => ({ value: String(cat.id), label: `${cat.name} (#${cat.id})` })),
    [categoriesData]
  );

  const roomsByCategory = useMemo(() => {
    const rooms = roomsQuery.data ?? [];
    const grouped: Record<string, typeof rooms> = {};
    rooms.forEach((room) => {
      const key = String(room.category_id);
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(room);
    });
    return grouped;
  }, [roomsQuery.data]);

  const availableRooms = formValues.category_id ? roomsByCategory[formValues.category_id] ?? [] : roomsQuery.data ?? [];

  const calendarDays = useMemo(() => {
    const days: Array<{
      iso: string;
      label: string;
      occupancy: number;
      active: number;
      arrivals: number;
      departures: number;
    }> = [];
    const window = calendarRange === "month" ? 30 : 7;
    for (let i = 0; i < window; i += 1) {
      const date = new Date();
      date.setDate(date.getDate() + i);
      const iso = date.toISOString().slice(0, 10);
      const active = reservations.filter(
        (r) =>
          r.status !== "cancelled" &&
          new Date(r.check_in_date) <= date &&
          new Date(r.check_out_date) > date
      ).length;
      const arrivals = reservations.filter((r) => r.check_in_date === iso).length;
      const departures = reservations.filter((r) => r.check_out_date === iso).length;
      const occupancy = totalRooms > 0 ? Math.min(100, Math.round((active / totalRooms) * 100)) : 0;
      days.push({
        iso,
        label: date.toLocaleDateString("es-AR", { weekday: "short", month: "short", day: "numeric" }),
        occupancy,
        active,
        arrivals,
        departures
      });
    }
    return days;
  }, [calendarRange, reservations, totalRooms]);

  const totals = useMemo(() => {
    return reservations.reduce(
      (acc, item) => {
        if (item.status !== "cancelled" && item.status !== "checked_out") acc.active += 1;
        if (item.check_in_date === today) acc.checkInsToday += 1;
        if (item.check_out_date === today || item.status === "checked_out") acc.checkOutsToday += 1;
        if (item.status === "cancelled") acc.cancelled += 1;
        return acc;
      },
      { active: 0, checkInsToday: 0, checkOutsToday: 0, cancelled: 0 }
    );
  }, [reservations, today]);
  const pendingActions = pendingActionsQuery.data ?? [];
  const criticalPendingActions = pendingActions.filter((item) => item.priority === "critical").length;

  const openCreate = () => {
    if (subscriptionBlocked) {
      setToast({ type: "error", message: subscriptionBlockReason || "Acción bloqueada por suscripción." });
      return;
    }
    setEditing(null);
    setFormValues(defaultFormState());
    setFormError(null);
    setFormOpen(true);
  };

  const openEdit = (reservation: Reservation) => {
    setEditing(reservation);
    setFormValues({
      guest_id: String(reservation.guest_id),
      category_id: String(reservation.category_id),
      room_id: reservation.room_id ? String(reservation.room_id) : "",
      check_in_date: reservation.check_in_date,
      check_out_date: reservation.check_out_date,
      num_adults: String(reservation.num_adults),
      num_children: String(reservation.num_children),
      notes: reservation.notes || "",
      source: reservation.source,
      status: reservation.status
    });
    setFormError(null);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setEditing(null);
    setFormError(null);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError(null);
    if (subscriptionBlocked) {
      setFormError(subscriptionBlockReason || "Suscripción inactiva.");
      return;
    }

    const categoryIdNum = Number(formValues.category_id);
    let guestIdNum = Number(formValues.guest_id);
    if (!editing && (!guestIdNum || Number.isNaN(guestIdNum))) {
      const hasGuestData =
        guestForm.first_name.trim() !== "" ||
        guestForm.last_name.trim() !== "" ||
        guestForm.email.trim() !== "" ||
        guestForm.phone.trim() !== "";

      if (!hasGuestData) {
        setFormError("Ingresá el ID del huésped o completá los datos para crearlo automáticamente.");
        return;
      }

      try {
        const newGuest = await guestMutation.mutateAsync({
          first_name: guestForm.first_name.trim() || "Invitado",
          last_name: guestForm.last_name.trim() || "Sin apellido",
          email: guestForm.email.trim() || undefined,
          phone: guestForm.phone.trim() || undefined,
          terms_accepted: true
        });
        guestIdNum = newGuest.id;
        setFormValues((prev) => ({ ...prev, guest_id: String(newGuest.id) }));
        setGuestForm({ first_name: "", last_name: "", email: "", phone: "" });
        showToast("success", "Huésped creado y asignado automáticamente");
      } catch (err) {
        const msg = err instanceof Error ? err.message : "No se pudo crear el huésped";
        setFormError(msg);
        showToast("error", msg);
        return;
      }
    }    if (!categoryIdNum || Number.isNaN(categoryIdNum)) {
      setFormError("Seleccioná una Categoría (ID numérico).");
      return;
    }
    if (!formValues.check_in_date || !formValues.check_out_date) {
      setFormError("Elegí fechas de ingreso y salida.");
      return;
    }

    const baseDatesValid = new Date(formValues.check_out_date) > new Date(formValues.check_in_date);
    if (!baseDatesValid) {
      setFormError("La fecha de salida debe ser posterior al ingreso.");
      return;
    }

    const commonPayload = {
      category_id: categoryIdNum,
      room_id: formValues.room_id ? Number(formValues.room_id) : null,
      check_in_date: formValues.check_in_date,
      check_out_date: formValues.check_out_date,
      num_adults: Number(formValues.num_adults) || 1,
      num_children: Number(formValues.num_children) || 0,
      notes: formValues.notes || undefined
    };

    if (editing) {
      const updatePayload = { ...commonPayload, status: formValues.status };
      updateMutation.mutate(
        { id: editing.id, payload: updatePayload },
        {
          onSuccess: () => {
            showToast("success", "Reserva actualizada");
            closeForm();
          },
          onError: (err: unknown) => {
            const msg = err instanceof Error ? err.message : "No se pudo guardar la reserva";
            setFormError(msg);
            showToast("error", msg);
          }
        }
      );
    } else {
      const createPayload = { ...commonPayload, guest_id: guestIdNum, source: formValues.source };
      createMutation.mutate(createPayload, {
        onSuccess: () => {
          showToast("success", "Reserva creada");
          closeForm();
        },
        onError: (err: unknown) => {
          const msg = err instanceof Error ? err.message : "No se pudo crear la reserva";
          setFormError(msg);
          showToast("error", msg);
        }
      });
    }
  };

  const canCancel = (status: ReservationStatus) => status !== "cancelled" && status !== "checked_out" && status !== "checked_in";
  const canCheckIn = (status: ReservationStatus) => ["pending", "deposit_paid", "fully_paid"].includes(status);
  const canCheckOut = (status: ReservationStatus) => status === "checked_in";

  const handleCancel = (id: number) =>
    cancelMutation.mutate(id, {
      onSuccess: () => showToast("success", "Reserva cancelada"),
      onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo cancelar")
    });

  const handleCheckIn = (id: number) =>
    checkInMutation.mutate(id, {
      onSuccess: () => showToast("success", "Check-in registrado"),
      onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo hacer check-in")
    });

  const handleCheckOut = (id: number) =>
    checkOutMutation.mutate(id, {
      onSuccess: () => showToast("success", "Check-out registrado"),
      onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo hacer check-out")
    });

  const handleCheckAvailability = () => {
    if (!availabilityForm.category_id || !availabilityForm.check_in_date || !availabilityForm.check_out_date) {
      showToast("error", "Completá Categoría y fechas para consultar disponibilidad.");
      return;
    }
    const payload = {
      category_id: Number(availabilityForm.category_id),
      check_in_date: availabilityForm.check_in_date,
      check_out_date: availabilityForm.check_out_date
    };
    availabilityMutation.mutate(payload, {
      onSuccess: (data) => {
        if (data.status === "ok") {
          showToast("success", `Disponibles: ${data.count} habitaciones`);
        } else {
          showToast("info", data.message);
        }
      },
      onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo consultar disponibilidad")
    });
  };

  const handleCreateGuest = () => {
    guestMutation.mutate(guestForm, {
      onSuccess: (guest: Guest) => {
        setFormValues((prev) => ({ ...prev, guest_id: String(guest.id) }));
        setGuestForm({ first_name: "", last_name: "", email: "", phone: "" });
        showToast("success", "Huésped creado y asignado");
      },
      onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo crear el Huésped")
    });
  };

  const paymentSummary = paymentSummaryQuery.data;
  const detailsSummary = detailsSummaryQuery.data;
  const detailsOperations = detailsOperationsQuery.data;
  const detailsGuest = useGuest(detailsReservation?.guest_id || undefined).data;
  const editingCurrencyCode = normalizeCurrencyCode(paymentSummary?.currency_code ?? editing?.currency_code);
  const detailsCurrencyCode = normalizeCurrencyCode(
    detailsSummary?.currency_code ??
      detailsOperations?.financial_summary.currency_code ??
      detailsReservation?.currency_code
  );

  const handlePayDeposit = () => {
    if (!editing || !paymentSummary) return;
    const due = Math.max(paymentSummary.deposit_required - paymentSummary.amount_paid, 0);
    if (due <= 0.01) {
      showToast("info", "La Seña ya está cubierta.");
      return;
    }
    paymentMutation.mutate(
      {
        reservation_id: editing.id,
        amount: Number(due.toFixed(2)),
        payment_method: paymentMethod,
        transaction_type: "deposit",
        currency: editingCurrencyCode
      },
      {
        onSuccess: () => showToast("success", "Se registró la Seña"),
        onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo registrar el pago")
      }
    );
  };

  const handlePayFull = () => {
    if (!editing || !paymentSummary) return;
    const due = paymentSummary.balance_due ?? 0;
    if (due <= 0.01) {
      showToast("info", "No hay saldo pendiente.");
      return;
    }
    paymentMutation.mutate(
      {
        reservation_id: editing.id,
        amount: Number(due.toFixed(2)),
        payment_method: paymentMethod,
        transaction_type: "full_payment",
        currency: editingCurrencyCode
      },
      {
        onSuccess: () => showToast("success", "Pago completo registrado"),
        onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo registrar el pago")
      }
    );
  };

  const openDetails = (reservation: Reservation) => setDetailsReservationId(reservation.id);
  const openDetailsById = (reservationId: number) => setDetailsReservationId(reservationId);
  const closeDetails = () => setDetailsReservationId(null);
  const openGuest = (guestId: number) => setGuestIdOpen(guestId);
  const closeGuest = () => setGuestIdOpen(null);

  const handleResolveExternal = (reservationId: number) =>
    resolveExternalMutation.mutate(
      { reservationId, payload: { notes: "Cierre manual desde la bandeja operativa." } },
      {
        onSuccess: () => showToast("success", "Follow-up externo marcado como resuelto"),
        onError: (err: unknown) =>
          showToast("error", err instanceof Error ? err.message : "No se pudo cerrar la acción externa")
      }
    );

  const handleClearManualReview = (reservationId: number) =>
    clearManualReviewMutation.mutate(
      { reservationId, payload: { notes: "Revisión manual cerrada desde la bandeja operativa." } },
      {
        onSuccess: () => showToast("success", "Revisión manual cerrada"),
        onError: (err: unknown) =>
          showToast("error", err instanceof Error ? err.message : "No se pudo cerrar la revisión manual")
      }
    );

  const exportVoucher = () => {
    if (!detailsReservation) return;
    const summary = detailsSummary;
    const guest = detailsGuest;
    const win = window.open("", "_blank");
    if (!win) return;
    const html = `
      <html>
        <head>
          <title>Voucher ${detailsReservation.confirmation_code}</title>
          <style>
            body { font-family: Arial, sans-serif; padding: 16px; color: #0f172a; }
            h1 { margin: 0 0 8px 0; }
            .grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 8px; }
            .card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; }
            .muted { color: #475569; font-size: 12px; margin: 0; }
            .label { font-size: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.02em; }
          </style>
        </head>
        <body>
          <h1>Voucher / Confirmación</h1>
          <p class="muted">Código ${detailsReservation.confirmation_code}</p>
          <div class="grid">
            <div class="card">
              <p class="label">Reserva</p>
              <p>Ingreso: <strong>${detailsReservation.check_in_date}</strong></p>
              <p>Salida: <strong>${detailsReservation.check_out_date}</strong></p>
              <p>Hab/Cat: <strong>${detailsReservation.room_id ?? "Sin asignar"} / ${detailsReservation.category_id}</strong></p>
              <p>Estado: <strong>${statusConfig[detailsReservation.status]?.label ?? detailsReservation.status}</strong></p>
            </div>
            <div class="card">
              <p class="label">Huésped</p>
              <p>${guest ? `${guest.first_name} ${guest.last_name}` : `ID ${detailsReservation.guest_id}`}</p>
              <p>Email: ${guest?.email ?? "-"}</p>
              <p>Tel: ${guest?.phone ?? "-"}</p>
            </div>
          </div>
          <div class="card" style="margin-top:12px;">
            <p class="label">Finanzas</p>
            <p>Total: <strong>${formatMoney(summary?.total_amount ?? detailsReservation.total_amount ?? 0, detailsCurrencyCode)}</strong></p>
            <p>Pagado: <strong>${formatMoney(summary?.amount_paid ?? detailsReservation.amount_paid ?? 0, detailsCurrencyCode)}</strong></p>
            <p>Saldo: <strong>${formatMoney(summary?.balance_due ?? detailsReservation.balance_due ?? 0, detailsCurrencyCode)}</strong></p>
          </div>
        </body>
      </html>`;
    win.document.write(html);
    win.document.close();
    win.focus();
    win.print();
    win.close();
  };

  const guestHistory = useMemo(
    () => (guestIdOpen ? reservations.filter((r) => r.guest_id === guestIdOpen) : []),
    [guestIdOpen, reservations]
  );

  const reservationsByRoom = useMemo(() => {
    const map: Record<number, Reservation[]> = {};
    reservations.forEach((r) => {
      if (!r.room_id) return;
      if (!map[r.room_id]) map[r.room_id] = [];
      map[r.room_id].push(r);
    });
    return map;
  }, [reservations]);

  return (
    <div className="space-y-6">
      {toast && (
        <div className="fixed right-6 top-20 z-40 flex w-80 items-start gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-xl">
          <span
            className={`mt-1 h-2 w-2 rounded-full ${
              toast.type === "success" ? "bg-emerald-500" : toast.type === "error" ? "bg-rose-500" : "bg-amber-500"
            }`}
          />
          <div className="space-y-1">
            <p className="text-sm font-semibold text-slate-900">
              {toast.type === "success" ? "Listo" : toast.type === "error" ? "Error" : "Aviso"}
            </p>
            <p className="text-sm text-slate-700">{toast.message}</p>
          </div>
          <button className="ml-auto text-xs text-slate-500 hover:text-slate-800" onClick={() => setToast(null)} type="button">
            Cerrar
          </button>
        </div>
      )}
      {subscriptionBlocked && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {subscriptionBlockReason} Ajustá el plan en{" "}
          <Link to="/settings/subscription" className="font-semibold underline">
            Configuración &gt; Suscripción
          </Link>
          .
        </div>
      )}

      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
          <h1 className="text-2xl font-semibold text-slate-900">Reservas</h1>
          <p className="text-sm text-slate-600">Listado en vivo contra el backend con acciones rápidas.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-lg border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100 disabled:opacity-60"
            onClick={openCreate}
            type="button"
            disabled={subscriptionBlocked}
          >
            Crear reserva
          </button>
          <Link
            to="/dashboard"
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300"
          >
            Dashboard
          </Link>
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-4">
        <ReservationStatCard label="Activas" value={totals.active} helper="Pendientes + check-in" />
        <ReservationStatCard label="Check-ins hoy" value={totals.checkInsToday} helper={today} />
        <ReservationStatCard label="Checkouts hoy" value={totals.checkOutsToday} helper={today} />
        <ReservationStatCard label="Canceladas" value={totals.cancelled} helper="Últimos 7 días" />
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
            <h2 className="text-lg font-semibold text-slate-900">Acciones pendientes</h2>
            <p className="text-sm text-slate-600">
              Seguimiento operativo de revisiones manuales, conciliación OTA y cobros pendientes.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
              {pendingActions.length} abiertas
            </span>
            {criticalPendingActions > 0 ? (
              <span className="rounded-full bg-rose-100 px-3 py-1 text-xs font-semibold text-rose-700">
                {criticalPendingActions} críticas
              </span>
            ) : null}
          </div>
        </div>

        <div className="mt-4 space-y-3">
          {pendingActionsQuery.isLoading ? (
            <p className="text-sm text-slate-500">Cargando bandeja operativa...</p>
          ) : pendingActions.length === 0 ? (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              No hay acciones operativas pendientes en este hotel.
            </div>
          ) : (
            pendingActions.map((action) => {
              const priority = priorityConfig[action.priority];
              const isResolveExternal =
                action.code === "resolve_external_channel" || action.code === "resolve_adjustment_external_action";
              const isManualReview = action.code === "manual_review_required";

              return (
                <div key={action.action_key} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${priority.className}`}>
                          {priority.label}
                        </span>
                        <span className="text-xs font-semibold text-slate-700">{action.confirmation_code}</span>
                        <span className="text-xs text-slate-500">
                          {action.check_in_date} → {action.check_out_date}
                        </span>
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{action.title}</p>
                        <p className="text-sm text-slate-600">{action.detail}</p>
                      </div>
                      <div className="flex flex-wrap gap-3 text-xs text-slate-500">
                        <span>Estado: {action.reservation_status}</span>
                        <span>Origen: {action.source_provider_code || action.source}</span>
                        {action.payment_collection_model ? <span>Cobro: {action.payment_collection_model}</span> : null}
                        {action.settlement_status ? <span>Settlement: {action.settlement_status}</span> : null}
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => openDetailsById(action.reservation_id)}
                        className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300"
                      >
                        Ver ficha
                      </button>
                      {isManualReview ? (
                        <button
                          type="button"
                          onClick={() => handleClearManualReview(action.reservation_id)}
                          disabled={clearManualReviewMutation.isLoading}
                          className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-700 hover:border-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          Cerrar revisión
                        </button>
                      ) : null}
                      {isResolveExternal ? (
                        <button
                          type="button"
                          onClick={() => handleResolveExternal(action.reservation_id)}
                          disabled={resolveExternalMutation.isLoading}
                          className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800 hover:border-amber-300 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          Marcar resuelto
                        </button>
                      ) : null}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Agenda</p>
            <h2 className="text-lg font-semibold text-slate-900">Ocupación {calendarRange === "week" ? "semanal" : "mensual"}</h2>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setCalendarRange("week")}
              className={`rounded-lg px-3 py-1 text-xs font-semibold ${calendarRange === "week" ? "bg-brand-100 text-brand-800" : "bg-slate-100 text-slate-700"}`}
            >
              Semana
            </button>
            <button
              type="button"
              onClick={() => setCalendarRange("month")}
              className={`rounded-lg px-3 py-1 text-xs font-semibold ${calendarRange === "month" ? "bg-brand-100 text-brand-800" : "bg-slate-100 text-slate-700"}`}
            >
              Mes
            </button>
          </div>
        </div>
        <div className="mt-3 space-y-2">
          {calendarDays.map((day) => (
            <div key={day.iso} className="flex items-center gap-3">
              <div className="w-40 text-sm font-semibold text-slate-800">{day.label}</div>
              <div className="relative h-3 flex-1 rounded-full bg-slate-100">
                <div
                  className="absolute left-0 top-0 h-3 rounded-full bg-brand-500"
                  style={{ width: `${day.occupancy}%`, minWidth: day.occupancy > 0 ? "6px" : "0" }}
                />
              </div>
              <span className="w-12 text-xs text-right font-semibold text-slate-700">{day.occupancy}%</span>
              <div className="flex gap-2 text-[11px]">
                <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-emerald-700">+{day.arrivals} lleg.</span>
                <span className="rounded-full bg-sky-100 px-2 py-0.5 text-sky-700">{day.departures} sal.</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Filtros</p>
            <h2 className="text-lg font-semibold text-slate-900">Fecha y estado</h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
            <label className="flex flex-col text-xs font-semibold text-slate-600">
              Desde
              <input
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="mt-1 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-brand-400 focus:outline-none"
              />
            </label>
            <label className="flex flex-col text-xs font-semibold text-slate-600">
              Hasta
              <input
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="mt-1 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-brand-400 focus:outline-none"
              />
            </label>
            <label className="flex flex-col text-xs font-semibold text-slate-600">
              Estado
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as ReservationStatus | "all" | "")}
                className="mt-1 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-brand-400 focus:outline-none"
              >
                <option value="">Todos</option>
                <option value="pending">Pendiente</option>
                <option value="deposit_paid">Seña</option>
                <option value="fully_paid">Pago completo</option>
                <option value="checked_in">Check-in</option>
                <option value="checked_out">Check-out</option>
                <option value="cancelled">Cancelada</option>
              </select>
            </label>
            <button
              type="button"
              onClick={() => {
                setFromDate("");
                setToDate("");
                setStatusFilter("");
              }}
              className="self-end rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300"
            >
              Limpiar
            </button>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Disponibilidad</p>
            <h2 className="text-lg font-semibold text-slate-900">Consulta rápida por Categoría</h2>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            {availabilityMutation.isPending && <span className="text-slate-600">Consultando...</span>}
            {availabilityMutation.isError && <span className="text-rose-600">Error al consultar</span>}
          </div>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <label className="text-xs font-semibold text-slate-600">
            Categoría
            <select
              value={availabilityForm.category_id}
              onChange={(e) => setAvailabilityForm((prev) => ({ ...prev, category_id: e.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
            >
              <option value="">Elegí</option>
              {categoryOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs font-semibold text-slate-600">
            Check-in
            <input
              type="date"
              value={availabilityForm.check_in_date}
              onChange={(e) => setAvailabilityForm((prev) => ({ ...prev, check_in_date: e.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
            />
          </label>
          <label className="text-xs font-semibold text-slate-600">
            Check-out
            <input
              type="date"
              value={availabilityForm.check_out_date}
              onChange={(e) => setAvailabilityForm((prev) => ({ ...prev, check_out_date: e.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
            />
          </label>
          <div className="flex items-end">
            <button
              type="button"
              onClick={handleCheckAvailability}
              className="w-full rounded-lg border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100"
              disabled={availabilityMutation.isPending}
            >
              Consultar
            </button>
          </div>
        </div>
        {availabilityMutation.data && (
          <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-sm text-slate-700">
            {availabilityMutation.data.status === "ok" ? (
              <div className="space-y-1">
                <p>
                  Disponibles: <span className="font-semibold">{availabilityMutation.data.count}</span>
                </p>
                <p className="text-xs text-slate-600">IDs: {availabilityMutation.data.available_rooms.join(", ") || "sin coincidencias"}</p>
              </div>
            ) : (
              <p>{availabilityMutation.data.message}</p>
            )}
          </div>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-200 pb-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Matriz</p>
            <h2 className="text-lg font-semibold text-slate-900">Habitación vs fechas</h2>
            <p className="text-xs text-slate-500">Marcadores de estadía, check-in (verde) y check-out (celeste).</p>
          </div>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead>
              <tr>
                <th className="sticky left-0 z-10 bg-white px-2 py-1 text-left font-semibold text-slate-600">Hab</th>
                {calendarDays.map((d) => (
                  <th key={d.iso} className="px-2 py-1 text-center font-semibold text-slate-500">
                    {d.label.split(" ").slice(0, 2).join(" ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(roomsQuery.data ?? []).map((room) => {
                const roomRes = reservationsByRoom[room.id] ?? [];
                return (
                  <tr key={room.id} className="border-t border-slate-100">
                    <td className="sticky left-0 z-10 bg-white px-2 py-1 text-left font-semibold text-slate-800">
                      Hab {room.room_number || room.id}
                    </td>
                    {calendarDays.map((day) => {
                      const target = new Date(day.iso);
                      const res = roomRes.find(
                        (r) => new Date(r.check_in_date) <= target && new Date(r.check_out_date) > target
                      );
                      const isArrival = res?.check_in_date === day.iso;
                      const isDeparture = res?.check_out_date === day.iso;
                      return (
                        <td key={day.iso} className="px-1 py-1 text-center align-middle">
                          {res ? (
                            <div className="flex flex-col items-center gap-1">
                              <span className="h-1 w-full rounded-full bg-brand-300" />
                              <span className="text-[10px] text-slate-600">{res.confirmation_code}</span>
                              <div className="flex gap-1">
                                {isArrival && <span className="rounded-full bg-emerald-100 px-1 text-[10px] text-emerald-700">I</span>}
                                {isDeparture && <span className="rounded-full bg-sky-100 px-1 text-[10px] text-sky-700">O</span>}
                              </div>
                            </div>
                          ) : (
                            <span className="text-slate-300">·</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Listado</p>
            <h2 className="text-lg font-semibold text-slate-900">Reservas recientes</h2>
            {isFetching && <p className="text-xs text-slate-500">Actualizando...</p>}
            {error && <p className="text-xs text-rose-700">No se pudo cargar: {(error as Error).message}</p>}
          </div>
          <span className="text-xs text-slate-500">Total: {reservations.length}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">Código</th>
                <th className="px-4 py-2">Huésped</th>
                <th className="px-4 py-2">Hab./Cat</th>
                <th className="px-4 py-2">Ingreso</th>
                <th className="px-4 py-2">Salida</th>
                <th className="px-4 py-2">Estado</th>
                <th className="px-4 py-2 text-right">Monto</th>
                <th className="px-4 py-2 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {!isLoading && reservations.length === 0 && (
                <tr>
                  <td className="px-4 py-4 text-sm text-slate-500" colSpan={8}>
                    No hay reservas con los filtros actuales.
                  </td>
                </tr>
              )}
              {reservations.map((reservation) => {
                const cfg = statusConfig[reservation.status];
                return (
                  <tr key={reservation.id} className="hover:bg-slate-50/60">
                    <td className="px-4 py-2 font-semibold text-slate-900">{reservation.confirmation_code}</td>
                    <td className="px-4 py-2 text-slate-700">
                      <button className="text-left font-semibold text-brand-700 hover:underline" onClick={() => openGuest(reservation.guest_id)} type="button">
                        {reservationGuestLabel(reservation)}
                      </button>
                    </td>
                    <td className="px-4 py-2 text-slate-600">
                      {reservation.room_id ? `Hab ${reservation.room_id}` : "Sin asignar"} · Cat {reservation.category_id}
                    </td>
                    <td className="px-4 py-2 text-slate-600">{reservation.check_in_date}</td>
                    <td className="px-4 py-2 text-slate-600">{reservation.check_out_date}</td>
                    <td className="px-4 py-2">
                      <span className={`rounded-full px-2 py-1 text-xs font-semibold ${cfg?.className ?? "bg-slate-100 text-slate-800"}`}>
                        {cfg?.label ?? reservation.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right font-semibold text-slate-900">
                      {formatMoney(reservation.total_amount ?? 0, reservation.currency_code)}
                    </td>
                    <td className="px-4 py-2 text-right text-xs text-slate-700">
                      <div className="flex flex-wrap justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => openEdit(reservation)}
                          className="rounded-lg border border-slate-200 px-2 py-1 hover:border-slate-300 disabled:opacity-50"
                          disabled={subscriptionBlocked}
                        >
                          Editar
                        </button>
                        <button
                          type="button"
                          onClick={() => openDetails(reservation)}
                          className="rounded-lg border border-slate-200 px-2 py-1 hover:border-slate-300"
                        >
                          Ficha
                        </button>
                        <button
                          type="button"
                          disabled={!canCancel(reservation.status) || cancelMutation.isLoading || subscriptionBlocked}
                          onClick={() => handleCancel(reservation.id)}
                          className="rounded-lg border border-rose-200 px-2 py-1 text-rose-700 hover:border-rose-300 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Cancelar
                        </button>
                        <button
                          type="button"
                          disabled={!canCheckIn(reservation.status) || checkInMutation.isLoading || subscriptionBlocked}
                          onClick={() => handleCheckIn(reservation.id)}
                          className="rounded-lg border border-emerald-200 px-2 py-1 text-emerald-700 hover:border-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Check-in
                        </button>
                        <button
                          type="button"
                          disabled={!canCheckOut(reservation.status) || checkOutMutation.isLoading || subscriptionBlocked}
                          onClick={() => handleCheckOut(reservation.id)}
                          className="rounded-lg border border-sky-200 px-2 py-1 text-sky-700 hover:border-sky-300 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Check-out
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {formOpen && (
        <div className="fixed inset-0 z-30 flex items-center justify-center bg-slate-900/40 px-4 py-6">
          <div className="w-full max-w-2xl rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">{editing ? "Editar" : "Crear"}</p>
                <h3 className="text-lg font-semibold text-slate-900">Reserva</h3>
                <p className="text-xs text-slate-500">Completá los campos mínimos: Huésped, Categoría y fechas.</p>
              </div>
              <button onClick={closeForm} type="button" className="text-sm text-slate-500 hover:text-slate-800">
                Cerrar
              </button>
            </div>

            {subscriptionBlocked && (
              <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                {subscriptionBlockReason} No podrás crear o editar reservas hasta regularizarlo.{" "}
                <Link to="/settings/subscription" className="font-semibold underline">
                  Ir a Suscripción
                </Link>
                .
              </div>
            )}
            {formError && <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{formError}</div>}

            <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
              <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
                Datos de la reserva
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-semibold text-slate-600">
                  ID Huésped
                  <input
                    type="number"
                    min={1}
                    placeholder="Ej: 12 (deja vacío y usa Huésped rápido)"
                    value={formValues.guest_id}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, guest_id: e.target.value }))}
                    disabled={Boolean(editing)}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
                  />
                </label>
                <label className="text-xs font-semibold text-slate-600">
                  Categoría
                  <select
                    value={formValues.category_id}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, category_id: e.target.value, room_id: "" }))}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  >
                    <option value="">Elegí una Categoría</option>
                    {categoryOptions.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">Huésped rápido</p>
                    <p className="text-xs text-slate-600">Creá y asigná sin salir del formulario.</p>
                  </div>
                  {guestMutation.isLoading && <span className="text-xs text-slate-500">Guardando...</span>}
                </div>
                <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                  <input
                    placeholder="Nombre"
                    value={guestForm.first_name}
                    onChange={(e) => setGuestForm((prev) => ({ ...prev, first_name: e.target.value }))}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                  <input
                    placeholder="Apellido"
                    value={guestForm.last_name}
                    onChange={(e) => setGuestForm((prev) => ({ ...prev, last_name: e.target.value }))}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                  <input
                    placeholder="Email"
                    value={guestForm.email}
                    onChange={(e) => setGuestForm((prev) => ({ ...prev, email: e.target.value }))}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                  <input
                    placeholder="Teléfono"
                    value={guestForm.phone}
                    onChange={(e) => setGuestForm((prev) => ({ ...prev, phone: e.target.value }))}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                  <button
                    type="button"
                    onClick={handleCreateGuest}
                    disabled={guestMutation.isLoading || !guestForm.first_name || !guestForm.last_name}
                    className="rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Crear Huésped y asignar ID
                  </button>
                  <span>Se asigna automáticamente al campo ID Huésped</span>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-semibold text-slate-600">
                  Habitación (opcional)
                  <select
                    value={formValues.room_id}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, room_id: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  >
                    <option value="">Sin asignar</option>
                    {availableRooms.map((room) => (
                      <option key={room.id} value={room.id}>
                        {`Hab ${room.room_number || room.id} · Cat ${room.category_id}`}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-xs font-semibold text-slate-600">
                  Origen
                  <select
                    value={formValues.source}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, source: e.target.value as ReservationSource }))}
                    disabled={Boolean(editing)}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
                  >
                    <option value="direct">Directo</option>
                    <option value="booking">Booking.com</option>
                    <option value="expedia">Expedia</option>
                    <option value="other_ota">Otra OTA</option>
                  </select>
                </label>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-semibold text-slate-600">
                  Check-in
                  <input
                    type="date"
                    value={formValues.check_in_date}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, check_in_date: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                </label>
                <label className="text-xs font-semibold text-slate-600">
                  Check-out
                  <input
                    type="date"
                    value={formValues.check_out_date}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, check_out_date: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                </label>
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <label className="text-xs font-semibold text-slate-600">
                  Adultos
                  <input
                    type="number"
                    min={1}
                    value={formValues.num_adults}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, num_adults: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                </label>
                <label className="text-xs font-semibold text-slate-600">
                  Menores
                  <input
                    type="number"
                    min={0}
                    value={formValues.num_children}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, num_children: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                </label>
                <label className="text-xs font-semibold text-slate-600">
                  Estado
                  <select
                    value={formValues.status}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, status: e.target.value as ReservationStatus }))}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  >
                    <option value="pending">Pendiente</option>
                    <option value="deposit_paid">Seña</option>
                    <option value="fully_paid">Pago completo</option>
                    <option value="checked_in">Check-in</option>
                    <option value="checked_out">Check-out</option>
                    <option value="cancelled">Cancelada</option>
                  </select>
                </label>
              </div>

              <label className="text-xs font-semibold text-slate-600">
                Notas
                <textarea
                  value={formValues.notes}
                  placeholder="Notas internas (opcional)"
                  onChange={(e) => setFormValues((prev) => ({ ...prev, notes: e.target.value }))}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  rows={3}
                />
              </label>

              {editing && (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-wide text-emerald-700">Pagos y balance</p>
                      <p className="text-xs text-emerald-800">Resumen financiero y acciones rápidas.</p>
                    </div>
                    {paymentSummaryQuery.isFetching && <span className="text-xs text-emerald-700">Actualizando...</span>}
                  </div>
                  {paymentSummary ? (
                    <div className="mt-2 grid gap-2 sm:grid-cols-4">
                      <div className="rounded-lg border border-emerald-100 bg-white/70 px-3 py-2 text-sm text-slate-800">
                        <p className="text-xs text-slate-500">Total</p>
                        <p className="font-semibold">{formatMoney(paymentSummary.total_amount ?? 0, editingCurrencyCode)}</p>
                      </div>
                      <div className="rounded-lg border border-emerald-100 bg-white/70 px-3 py-2 text-sm text-slate-800">
                        <p className="text-xs text-slate-500">Pagado</p>
                        <p className="font-semibold">{formatMoney(paymentSummary.amount_paid ?? 0, editingCurrencyCode)}</p>
                      </div>
                      <div className="rounded-lg border border-emerald-100 bg-white/70 px-3 py-2 text-sm text-slate-800">
                        <p className="text-xs text-slate-500">Seña requerida</p>
                        <p className="font-semibold">{formatMoney(paymentSummary.deposit_required ?? 0, editingCurrencyCode)}</p>
                      </div>
                      <div className="rounded-lg border border-emerald-100 bg-white/70 px-3 py-2 text-sm text-slate-800">
                        <p className="text-xs text-slate-500">Saldo</p>
                        <p className="font-semibold">{formatMoney(paymentSummary.balance_due ?? 0, editingCurrencyCode)}</p>
                      </div>
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-slate-600">Cargando resumen...</p>
                  )}

                  <div className="mt-3 grid gap-2 sm:grid-cols-5 sm:items-end">
                    <label className="text-xs font-semibold text-slate-600 sm:col-span-2">
                      Medio de pago
                      <select
                        value={paymentMethod}
                        onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}
                        className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                      >
                        {paymentMethodOptions.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      onClick={handlePayDeposit}
                      disabled={paymentMutation.isLoading}
                      className="rounded-lg border border-amber-200 bg-amber-100 px-3 py-2 text-sm font-semibold text-amber-800 hover:border-amber-300 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Registrar Seña
                    </button>
                    <button
                      type="button"
                      onClick={handlePayFull}
                      disabled={paymentMutation.isLoading}
                      className="rounded-lg border border-emerald-200 bg-emerald-100 px-3 py-2 text-sm font-semibold text-emerald-800 hover:border-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Pago total
                    </button>
                    {paymentMutation.isError && (
                      <p className="text-xs text-rose-600">Error al registrar pago.</p>
                    )}
                  </div>

                  {paymentSummary?.transactions?.length ? (
                    <div className="mt-3 rounded-lg border border-emerald-100 bg-white/60 px-3 py-2 text-xs text-slate-700">
                      <p className="font-semibold text-slate-800">Movimientos</p>
                      <ul className="mt-1 space-y-1">
                        {paymentSummary.transactions.map((tx) => (
                          <li key={tx.id} className="flex items-center justify-between">
                            <span>
                              {tx.type} · {tx.method}
                            </span>
                            <span className="font-semibold">{formatMoney(tx.amount, tx.currency)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <p className="mt-2 text-xs text-slate-600">Sin pagos registrados.</p>
                  )}
                </div>
              )}

              <div className="flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={closeForm}
                  className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                  disabled={createMutation.isLoading || updateMutation.isLoading || subscriptionBlocked}
                >
                  {editing ? "Guardar cambios" : "Crear"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {detailsReservation && (
        <div className="fixed inset-0 z-30 flex items-center justify-center bg-slate-900/30 px-4 py-6">
          <div className="w-full max-w-3xl rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Ficha</p>
                <h3 className="text-lg font-semibold text-slate-900">Reserva {detailsReservation.confirmation_code}</h3>
                <p className="text-xs text-slate-500">
                  {reservationGuestLabel(detailsReservation)} - Cat {detailsReservation.category_id} -{" "}
                  {detailsReservation.room_id ? `Hab ${detailsReservation.room_id}` : "Sin asignar"}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={exportVoucher}
                  className="rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100"
                >
                  Exportar voucher PDF
                </button>
                <button onClick={closeDetails} type="button" className="text-sm text-slate-500 hover:text-slate-800">
                  Cerrar
                </button>
              </div>
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Timeline</p>
                <ul className="space-y-2 text-sm text-slate-800">
                  <li>
                    <span className="font-semibold">Check-in:</span> {detailsReservation.check_in_date}
                  </li>
                  <li>
                    <span className="font-semibold">Check-out:</span> {detailsReservation.check_out_date}
                  </li>
                  <li>
                    <span className="font-semibold">Estado:</span> {statusConfig[detailsReservation.status]?.label ?? detailsReservation.status}
                  </li>
                  {detailsSummary?.transactions?.length ? (
                    <li>
                      <span className="font-semibold">Último pago:</span>{" "}
                      {detailsSummary.transactions[detailsSummary.transactions.length - 1].created_at}
                    </li>
                  ) : null}
                </ul>
              </div>

              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Finanzas</p>
                <div className="grid grid-cols-2 gap-2 text-sm text-slate-800">
                  <div>
                    <p className="text-xs text-slate-500">Total</p>
                    <p className="font-semibold">{formatMoney(detailsSummary?.total_amount ?? detailsReservation.total_amount ?? 0, detailsCurrencyCode)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Pagado</p>
                    <p className="font-semibold">{formatMoney(detailsSummary?.amount_paid ?? detailsReservation.amount_paid ?? 0, detailsCurrencyCode)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Depósito</p>
                    <p className="font-semibold">{formatMoney(detailsSummary?.deposit_required ?? detailsReservation.deposit_amount ?? 0, detailsCurrencyCode)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Saldo</p>
                    <p className="font-semibold">{formatMoney(detailsSummary?.balance_due ?? detailsReservation.balance_due ?? 0, detailsCurrencyCode)}</p>
                  </div>
                </div>
                {detailsOperations?.financial_summary ? (
                  <div className="rounded-lg border border-slate-200 bg-white/70 p-3 text-xs text-slate-700">
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <p className="text-slate-500">Total operativo</p>
                        <p className="font-semibold">
                          {formatMoney(
                            detailsOperations.financial_summary.operational_total_amount ?? 0,
                            detailsOperations.financial_summary.currency_code
                          )}
                        </p>
                      </div>
                      <div>
                        <p className="text-slate-500">Saldo operativo</p>
                        <p className="font-semibold">
                          {formatMoney(
                            detailsOperations.financial_summary.operational_balance_due ?? 0,
                            detailsOperations.financial_summary.currency_code
                          )}
                        </p>
                      </div>
                      <div>
                        <p className="text-slate-500">Cobro</p>
                        <p className="font-semibold">{detailsOperations.payment_collection_model}</p>
                      </div>
                      <div>
                        <p className="text-slate-500">Settlement</p>
                        <p className="font-semibold">{detailsOperations.settlement_status}</p>
                      </div>
                    </div>
                    {detailsOperations.financial_summary.recommended_next_action ? (
                      <p className="mt-2 text-xs text-amber-700">
                        Próxima acción sugerida: {detailsOperations.financial_summary.recommended_next_action}
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
                  {detailsOperationsQuery.isFetching ? <span className="text-xs text-slate-500">Actualizando...</span> : null}
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm text-slate-800">
                  <div>
                    <p className="text-xs text-slate-500">Asignación</p>
                    <p className="font-semibold">{detailsOperations?.allocation_status ?? detailsReservation.allocation_status ?? "-"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Revisión manual</p>
                    <p className="font-semibold">{detailsOperations?.requires_manual_review ? "Sí" : "No"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Acciones pendientes</p>
                    <p className="font-semibold">{detailsOperations?.pending_action_count ?? 0}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Último movimiento</p>
                    <p className="font-semibold">{detailsOperations?.latest_room_move?.move_type ?? "-"}</p>
                  </div>
                </div>
                {detailsOperations?.ota_link ? (
                  <div className="rounded-lg border border-slate-200 bg-white/70 p-3 text-xs text-slate-700">
                    <p className="font-semibold text-slate-800">Canal externo</p>
                    <p>Estado: {detailsOperations.ota_link.provider_state}</p>
                    <p>Sync: {detailsOperations.ota_link.sync_status ?? "-"}</p>
                    {detailsOperations.ota_link.error_message ? (
                      <p className="mt-1 text-amber-700">{detailsOperations.ota_link.error_message}</p>
                    ) : null}
                  </div>
                ) : null}
              </div>

              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Acciones</p>
                {detailsOperations?.pending_actions?.length ? (
                  <div className="space-y-2">
                    {detailsOperations.pending_actions.map((action) => {
                      const priority = priorityConfig[action.priority];
                      const isResolveExternal =
                        action.code === "resolve_external_channel" || action.code === "resolve_adjustment_external_action";
                      const isManualReview = action.code === "manual_review_required";

                      return (
                        <div key={action.action_key} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${priority.className}`}>
                                  {priority.label}
                                </span>
                                <p className="text-sm font-semibold text-slate-900">{action.title}</p>
                              </div>
                              <p className="mt-1 text-xs text-slate-600">{action.detail}</p>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              {isManualReview ? (
                                <button
                                  type="button"
                                  onClick={() => handleClearManualReview(detailsReservation.id)}
                                  disabled={clearManualReviewMutation.isLoading}
                                  className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-700 hover:border-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  Cerrar revisión
                                </button>
                              ) : null}
                              {isResolveExternal ? (
                                <button
                                  type="button"
                                  onClick={() => handleResolveExternal(detailsReservation.id)}
                                  disabled={resolveExternalMutation.isLoading}
                                  className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800 hover:border-amber-300 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  Marcar resuelto
                                </button>
                              ) : null}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-slate-600">Sin acciones pendientes para esta reserva.</p>
                )}
              </div>
            </div>

            {detailsOperations?.open_adjustments?.length ? (
              <div className="mt-4 rounded-lg border border-slate-200 bg-white">
                <div className="border-b border-slate-200 px-3 py-2">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Ajustes operativos</p>
                </div>
                <div className="divide-y divide-slate-200 p-3">
                  {detailsOperations.open_adjustments.map((adjustment) => (
                    <div key={adjustment.id} className="flex items-start justify-between gap-3 py-2 text-sm">
                      <div>
                        <p className="font-semibold text-slate-900">{adjustment.kind}</p>
                        <p className="text-xs text-slate-600">
                          Estado: {adjustment.status} · Resolución externa: {adjustment.external_resolution_status ?? "-"}
                        </p>
                        {adjustment.notes ? <p className="mt-1 text-xs text-slate-500">{adjustment.notes}</p> : null}
                      </div>
                      <div className="text-right text-xs text-slate-600">
                        <p>{adjustment.currency_code ?? "-"}</p>
                        <p className="font-semibold">{formatMoney(adjustment.amount_delta ?? 0, adjustment.currency_code)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="mt-4 rounded-lg border border-slate-200 bg-white">
              <div className="border-b border-slate-200 px-3 py-2">
                <p className="text-xs uppercase tracking-wide text-slate-500">Pagos</p>
              </div>
              <div className="p-3 text-sm text-slate-800">
                {detailsSummary?.transactions?.length ? (
                  <ul className="divide-y divide-slate-200">
                    {detailsSummary.transactions.map((tx) => (
                      <li key={tx.id} className="flex items-center justify-between py-2">
                        <div>
                          <p className="font-semibold">{formatMoney(tx.amount, tx.currency)}</p>
                          <p className="text-xs text-slate-500">
                            {tx.type} · {tx.method} · {tx.status}
                          </p>
                        </div>
                        <span className="text-xs text-slate-500">{tx.created_at}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-slate-600">Sin transacciones registradas.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {guestIdOpen && (
        <div className="fixed inset-0 z-30 flex items-center justify-center bg-slate-900/30 px-4 py-6">
          <div className="w-full max-w-2xl rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Ficha de Huésped</p>
                <h3 className="text-lg font-semibold text-slate-900">
                  {guestQuery.data ? `${guestQuery.data.first_name} ${guestQuery.data.last_name}` : `Huésped #${guestIdOpen}`}
                </h3>
                <p className="text-xs text-slate-500">Contacto y reservas asociadas.</p>
              </div>
              <button onClick={closeGuest} type="button" className="text-sm text-slate-500 hover:text-slate-800">
                Cerrar
              </button>
            </div>

            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-800">
                <p className="text-xs uppercase tracking-wide text-slate-500">Contacto</p>
                <p className="mt-1">{guestQuery.data?.email ?? "Sin email"}</p>
                <p>{guestQuery.data?.phone ?? "Sin teléfono"}</p>
                <p className="text-xs text-slate-500">
                  Doc: {guestQuery.data?.document_type ?? "-"} {guestQuery.data?.document_number ?? ""}
                </p>
                <p className="text-xs text-slate-500">
                  {guestQuery.data?.city ?? ""} {guestQuery.data?.country ?? ""}
                </p>
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-800">
                <p className="text-xs uppercase tracking-wide text-slate-500">Histórico</p>
                {guestHistory.length ? (
                  <ul className="mt-2 space-y-2">
                    {guestHistory.map((r) => (
                      <li key={r.id} className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-2 py-1">
                        <span className="text-xs text-slate-600">
                          {r.check_in_date} → {r.check_out_date} · {statusConfig[r.status]?.label ?? r.status}
                        </span>
                        <button className="text-xs font-semibold text-brand-700 hover:underline" onClick={() => openDetails(r)} type="button">
                          Ver
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-xs text-slate-600">Sin reservas asociadas en esta vista.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}





