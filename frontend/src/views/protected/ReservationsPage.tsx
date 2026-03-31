import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { type Reservation, type ReservationSource, type ReservationStatus } from "../../api/reservations";
import { useCategories } from "../../hooks/useCategories";
import { useGuestCreate } from "../../hooks/useGuests";
import { useReservationMutations, useReservations } from "../../hooks/useReservations";
import { useRooms } from "../../hooks/useRooms";

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

export function ReservationsPage() {
  const [statusFilter, setStatusFilter] = useState<ReservationStatus | "all" | "">("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Reservation | null>(null);
  const [formValues, setFormValues] = useState<FormState>(defaultFormState);
  const [formError, setFormError] = useState<string | null>(null);
  const [guestForm, setGuestForm] = useState({ first_name: "", last_name: "", email: "", phone: "" });

  const filters = {
    status: statusFilter,
    fromDate: fromDate || undefined,
    toDate: toDate || undefined
  };

  const { data: reservations = [], isLoading, isFetching, error } = useReservations(filters);
  const { roomsQuery } = useRooms();
  const { data: categoriesData = [] } = useCategories();
  const guestMutation = useGuestCreate();
  const { createMutation, updateMutation, cancelMutation, checkInMutation, checkOutMutation } = useReservationMutations(filters);

  const today = todayIso();

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
          onSuccess: closeForm,
          onError: (err: unknown) => setFormError(err instanceof Error ? err.message : "No se pudo guardar la reserva")
        }
      );
    } else {
      const createPayload = { ...commonPayload, guest_id: guestIdNum, source: formValues.source };
      createMutation.mutate(createPayload, {
        onSuccess: closeForm,
        onError: (err: unknown) => setFormError(err instanceof Error ? err.message : "No se pudo crear la reserva")
      });
    }
  };

  const canCancel = (status: ReservationStatus) => status !== "cancelled" && status !== "checked_out" && status !== "checked_in";
  const canCheckIn = (status: ReservationStatus) => ["pending", "deposit_paid", "fully_paid"].includes(status);
  const canCheckOut = (status: ReservationStatus) => status === "checked_in";

  return (
    <div className="space-y-6">
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
                          disabled={!canCancel(reservation.status) || cancelMutation.isLoading}
                          onClick={() => cancelMutation.mutate(reservation.id)}
                          className="rounded-lg border border-rose-200 px-2 py-1 text-rose-700 hover:border-rose-300 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Cancelar
                        </button>
                        <button
                          type="button"
                          disabled={!canCheckIn(reservation.status) || checkInMutation.isLoading}
                          onClick={() => checkInMutation.mutate(reservation.id)}
                          className="rounded-lg border border-emerald-200 px-2 py-1 text-emerald-700 hover:border-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Check-in
                        </button>
                        <button
                          type="button"
                          disabled={!canCheckOut(reservation.status) || checkOutMutation.isLoading}
                          onClick={() => checkOutMutation.mutate(reservation.id)}
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
                  Categoría ID
                  <input
                    type="number"
                    min={1}
                    value={formValues.category_id}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, category_id: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                </label>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-semibold text-slate-600">
                  Habitación (opcional)
                  <input
                    type="number"
                    min={1}
                    value={formValues.room_id}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, room_id: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
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
