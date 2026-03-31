import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";

import { type Reservation, type ReservationSource, type ReservationStatus } from "../../api/reservations";
import { checkRoomAvailability, type RoomAvailabilityResponse } from "../../api/rooms";
import { type PaymentMethod } from "../../api/payments";
import { apiFetch } from "../../api/client";
import { useCategories } from "../../hooks/useCategories";
import { useGuestCreate } from "../../hooks/useGuests";
import { useReservationMutations, useReservations } from "../../hooks/useReservations";
import { usePaymentMutation, usePaymentSummary } from "../../hooks/usePayments";
import { useRooms } from "../../hooks/useRooms";
import { useSession } from "../../state/session";

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

const currency = new Intl.NumberFormat("es-AR", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

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
const DEMO_MODE = (import.meta.env.VITE_DEMO_MODE ?? "").toString().toLowerCase() === "true";

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
  const toastTimeout = useRef<number | null>(null);
  const [toast, setToast] = useState<{ type: "success" | "error" | "info"; message: string } | null>(null);
  const [calendarRange, setCalendarRange] = useState<"week" | "month">("week");
  const [detailsReservation, setDetailsReservation] = useState<Reservation | null>(null);

  const filters = {
    status: statusFilter,
    fromDate: fromDate || undefined,
    toDate: toDate || undefined
  };

  const { data: reservations = [], isLoading, isFetching, error } = useReservations(filters);
  const { roomsQuery } = useRooms();
  const { data: categoriesData = [] } = useCategories();
  const guestMutation = useGuestCreate();
  const paymentSummaryQuery = usePaymentSummary(editing?.id || undefined);
  const detailsSummaryQuery = usePaymentSummary(detailsReservation?.id || undefined);
  const paymentMutation = usePaymentMutation(editing?.id || undefined);
  const availabilityMutation = useMutation<RoomAvailabilityResponse, unknown, { category_id: number; check_in_date: string; check_out_date: string }>({
    mutationFn: (payload) => checkRoomAvailability(payload, session)
  });
  const seedMutation = useMutation({
    mutationFn: () => apiFetch("/api/seed", { method: "POST", session })
  });
  const resetMutation = useMutation({
    mutationFn: () => apiFetch("/api/reset", { method: "POST", session })
  });
  const { createMutation, updateMutation, cancelMutation, checkInMutation, checkOutMutation } = useReservationMutations(filters);

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

  const openCreate = () => {
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

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setFormError(null);

    const categoryIdNum = Number(formValues.category_id);
    const guestIdNum = Number(formValues.guest_id);
    if (!editing && (!guestIdNum || Number.isNaN(guestIdNum))) {
      setFormError("Ingresá el ID del huésped (número entero).");
      return;
    }
    if (!categoryIdNum || Number.isNaN(categoryIdNum)) {
      setFormError("Seleccioná una categoría (ID numérico).");
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
      showToast("error", "Completá categoría y fechas para consultar disponibilidad.");
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
      onSuccess: (guest: any) => {
        setFormValues((prev) => ({ ...prev, guest_id: String(guest.id) }));
        setGuestForm({ first_name: "", last_name: "", email: "", phone: "" });
        showToast("success", "Huésped creado y asignado");
      },
      onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo crear el huésped")
    });
  };

  const paymentSummary = paymentSummaryQuery.data;
  const detailsSummary = detailsSummaryQuery.data;

  const handlePayDeposit = () => {
    if (!editing || !paymentSummary) return;
    const due = Math.max(paymentSummary.deposit_required - paymentSummary.amount_paid, 0);
    if (due <= 0.01) {
      showToast("info", "La seña ya está cubierta.");
      return;
    }
    paymentMutation.mutate(
      {
        reservation_id: editing.id,
        amount: Number(due.toFixed(2)),
        payment_method: paymentMethod,
        transaction_type: "deposit"
      },
      {
        onSuccess: () => showToast("success", "Se registró la seña"),
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
        transaction_type: "full_payment"
      },
      {
        onSuccess: () => showToast("success", "Pago completo registrado"),
        onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo registrar el pago")
      }
    );
  };

  const openDetails = (reservation: Reservation) => {
    setDetailsReservation(reservation);
  };

  const closeDetails = () => setDetailsReservation(null);

  const handleSeed = () =>
    seedMutation.mutate(undefined, {
      onSuccess: () => showToast("success", "Base demo poblada"),
      onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo ejecutar seed")
    });

  const handleReset = () =>
    resetMutation.mutate(undefined, {
      onSuccess: () => showToast("success", "Base restablecida"),
      onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo resetear")
    });

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

      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
          <h1 className="text-2xl font-semibold text-slate-900">Reservas</h1>
          <p className="text-sm text-slate-600">Listado en vivo contra el backend con acciones rápidas.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-lg border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100"
            onClick={openCreate}
            type="button"
          >
            Crear reserva
          </button>
          {DEMO_MODE && (
            <>
              <button
                type="button"
                onClick={handleSeed}
                disabled={seedMutation.isLoading}
                className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-700 hover:border-emerald-300 disabled:opacity-60"
              >
                Seed demo
              </button>
              <button
                type="button"
                onClick={handleReset}
                disabled={resetMutation.isLoading}
                className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 hover:border-rose-300 disabled:opacity-60"
              >
                Reset demo
              </button>
            </>
          )}
          <Link
            to="/dashboard"
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300"
          >
            Dashboard
          </Link>
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="Activas" value={totals.active} helper="Pendientes + check-in" />
        <StatCard label="Check-ins hoy" value={totals.checkInsToday} helper={today} />
        <StatCard label="Checkouts hoy" value={totals.checkOutsToday} helper={today} />
        <StatCard label="Canceladas" value={totals.cancelled} helper="Últimos 7 días" />
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
                <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-emerald-700">+{day.arrivals} arrivos</span>
                <span className="rounded-full bg-sky-100 px-2 py-0.5 text-sky-700">{day.departures} salidas</span>
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
            <h2 className="text-lg font-semibold text-slate-900">Consulta rápida por categoría</h2>
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
                    <td className="px-4 py-2 text-slate-700">Huésped #{reservation.guest_id}</td>
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
                    <td className="px-4 py-2 text-right font-semibold text-slate-900">{currency.format(reservation.total_amount ?? 0)}</td>
                    <td className="px-4 py-2 text-right text-xs text-slate-700">
                      <div className="flex flex-wrap justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => openEdit(reservation)}
                          className="rounded-lg border border-slate-200 px-2 py-1 hover:border-slate-300"
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
                          disabled={!canCancel(reservation.status) || cancelMutation.isLoading}
                          onClick={() => handleCancel(reservation.id)}
                          className="rounded-lg border border-rose-200 px-2 py-1 text-rose-700 hover:border-rose-300 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Cancelar
                        </button>
                        <button
                          type="button"
                          disabled={!canCheckIn(reservation.status) || checkInMutation.isLoading}
                          onClick={() => handleCheckIn(reservation.id)}
                          className="rounded-lg border border-emerald-200 px-2 py-1 text-emerald-700 hover:border-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Check-in
                        </button>
                        <button
                          type="button"
                          disabled={!canCheckOut(reservation.status) || checkOutMutation.isLoading}
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
                <p className="text-xs text-slate-500">Completá los campos mínimos: huésped, categoría y fechas.</p>
              </div>
              <button onClick={closeForm} type="button" className="text-sm text-slate-500 hover:text-slate-800">
                Cerrar
              </button>
            </div>

            {formError && <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{formError}</div>}

            <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-semibold text-slate-600">
                  ID huésped
                  <input
                    type="number"
                    min={1}
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
                    <option value="">Elegí una categoría</option>
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
                    Crear huésped y asignar ID
                  </button>
                  <span>Se asigna automáticamente al campo ID huésped</span>
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
                        <p className="font-semibold">{currency.format(paymentSummary.total_amount ?? 0)}</p>
                      </div>
                      <div className="rounded-lg border border-emerald-100 bg-white/70 px-3 py-2 text-sm text-slate-800">
                        <p className="text-xs text-slate-500">Pagado</p>
                        <p className="font-semibold">{currency.format(paymentSummary.amount_paid ?? 0)}</p>
                      </div>
                      <div className="rounded-lg border border-emerald-100 bg-white/70 px-3 py-2 text-sm text-slate-800">
                        <p className="text-xs text-slate-500">Seña requerida</p>
                        <p className="font-semibold">{currency.format(paymentSummary.deposit_required ?? 0)}</p>
                      </div>
                      <div className="rounded-lg border border-emerald-100 bg-white/70 px-3 py-2 text-sm text-slate-800">
                        <p className="text-xs text-slate-500">Saldo</p>
                        <p className="font-semibold">{currency.format(paymentSummary.balance_due ?? 0)}</p>
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
                      Registrar seña
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
                            <span className="font-semibold">{currency.format(tx.amount)}</span>
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
                  className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
                  disabled={createMutation.isLoading || updateMutation.isLoading}
                >
                  {editing ? "Guardar cambios" : "Crear"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {detailsReservation && (
        <div className="fixed inset-0 z-20 flex items-center justify-center bg-slate-900/30 px-4 py-6">
          <div className="w-full max-w-3xl rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Ficha</p>
                <h3 className="text-lg font-semibold text-slate-900">Reserva {detailsReservation.confirmation_code}</h3>
                <p className="text-xs text-slate-500">
                  Huésped #{detailsReservation.guest_id} · Cat {detailsReservation.category_id} ·{" "}
                  {detailsReservation.room_id ? `Hab ${detailsReservation.room_id}` : "Sin asignar"}
                </p>
              </div>
              <button onClick={closeDetails} type="button" className="text-sm text-slate-500 hover:text-slate-800">
                Cerrar
              </button>
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
                    <p className="font-semibold">{currency.format(detailsSummary?.total_amount ?? detailsReservation.total_amount ?? 0)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Pagado</p>
                    <p className="font-semibold">{currency.format(detailsSummary?.amount_paid ?? detailsReservation.amount_paid ?? 0)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Depósito</p>
                    <p className="font-semibold">{currency.format(detailsSummary?.deposit_required ?? detailsReservation.deposit_amount ?? 0)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Saldo</p>
                    <p className="font-semibold">{currency.format(detailsSummary?.balance_due ?? detailsReservation.balance_due ?? 0)}</p>
                  </div>
                </div>
              </div>
            </div>

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
                          <p className="font-semibold">{currency.format(tx.amount)}</p>
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
    </div>
  );
}

function StatCard({ label, value, helper }: { label: string; value: number; helper: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <div className="mt-2 text-2xl font-semibold text-slate-900">{value}</div>
      <p className="text-xs text-slate-500">{helper}</p>
    </div>
  );
}
