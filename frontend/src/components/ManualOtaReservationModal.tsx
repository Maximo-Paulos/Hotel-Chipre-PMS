import { useState } from "react";

import { type Reservation } from "../api/reservations";
import { useCategories } from "../hooks/useCategories";
import { useGuestCreate } from "../hooks/useGuests";
import { useReservationMutations } from "../hooks/useReservations";
import { useRooms } from "../hooks/useRooms";
import { normalizeCurrencyCode } from "../utils/currency";

import GuestQuickCreatePanel, { emptyQuickGuestForm, hasQuickGuestFormData, type QuickGuestFormValues } from "./GuestQuickCreatePanel";

// B4: "Cargar reserva de OTA" -- POST /api/reservations/manual-ota. This is
// an upsert keyed by (channel, external_id): submitting the same pair again
// updates the existing reservation (adds a payment, corrects a date, etc.)
// instead of rejecting it as a duplicate, so there is no "duplicate" error
// path to show here -- both outcomes render the same success panel.
const CHANNEL_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "booking", label: "Booking.com" },
  { value: "expedia", label: "Expedia" },
  { value: "despegar", label: "Despegar" },
  { value: "other_ota", label: "Otra OTA" }
];

const todayIso = () => new Date().toISOString().slice(0, 10);
const tomorrowIso = () => {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
};

type FormState = {
  category_id: string;
  room_id: string;
  check_in_date: string;
  check_out_date: string;
  num_adults: string;
  num_children: string;
  channel: string;
  external_id: string;
  total_amount: string;
  target_currency: "ARS" | "USD";
  amount_paid: string;
};

const emptyFormState = (): FormState => ({
  category_id: "",
  room_id: "",
  check_in_date: todayIso(),
  check_out_date: tomorrowIso(),
  num_adults: "1",
  num_children: "0",
  channel: "booking",
  external_id: "",
  total_amount: "",
  target_currency: "ARS",
  amount_paid: ""
});

type ManualOtaReservationModalProps = {
  open: boolean;
  onClose: () => void;
};

export default function ManualOtaReservationModal({ open, onClose }: ManualOtaReservationModalProps) {
  const categoriesQuery = useCategories();
  const { roomsQuery } = useRooms();
  const { createManualOtaMutation } = useReservationMutations();
  const guestMutation = useGuestCreate();

  const [guestId, setGuestId] = useState("");
  const [guestForm, setGuestForm] = useState<QuickGuestFormValues>(emptyQuickGuestForm);
  const [form, setForm] = useState<FormState>(emptyFormState);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Reservation | null>(null);

  if (!open) return null;

  const availableRooms = form.category_id
    ? (roomsQuery.data ?? []).filter((room) => String(room.category_id) === form.category_id)
    : roomsQuery.data ?? [];

  const reset = () => {
    setGuestId("");
    setGuestForm(emptyQuickGuestForm());
    setForm(emptyFormState());
    setError(null);
    setCreated(null);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    let guestIdNum = Number(guestId);
    if (!guestIdNum || Number.isNaN(guestIdNum)) {
      if (!hasQuickGuestFormData(guestForm)) {
        setError("Ingresá el ID del huésped o completá los datos para crearlo automáticamente.");
        return;
      }
      try {
        const newGuest = await guestMutation.mutateAsync({
          first_name: guestForm.first_name.trim() || "Invitado",
          last_name: guestForm.last_name.trim() || "Sin apellido",
          email: guestForm.email.trim() || undefined,
          phone: guestForm.phone.trim() || undefined,
          document_type: guestForm.document_type,
          document_number: guestForm.document_number.trim() || undefined,
          terms_accepted: true
        });
        guestIdNum = newGuest.id;
        setGuestId(String(newGuest.id));
        setGuestForm(emptyQuickGuestForm());
      } catch (err) {
        setError(err instanceof Error ? err.message : "No se pudo crear el huésped");
        return;
      }
    }

    const categoryIdNum = Number(form.category_id);
    if (!categoryIdNum || Number.isNaN(categoryIdNum)) {
      setError("Seleccioná una categoría.");
      return;
    }
    if (!form.check_in_date || !form.check_out_date || form.check_out_date <= form.check_in_date) {
      setError("La fecha de salida debe ser posterior al ingreso.");
      return;
    }
    if (!form.external_id.trim()) {
      setError("El ID externo (código de la reserva en la OTA) es obligatorio.");
      return;
    }
    const totalAmount = form.total_amount.trim() === "" ? null : Number(form.total_amount);
    if (totalAmount !== null && (!Number.isFinite(totalAmount) || totalAmount < 0)) {
      setError("Ingresá un monto total válido.");
      return;
    }
    const amountPaid = form.amount_paid.trim() === "" ? null : Number(form.amount_paid);
    if (amountPaid !== null && (!Number.isFinite(amountPaid) || amountPaid < 0)) {
      setError("Ingresá un monto ya cobrado válido.");
      return;
    }

    createManualOtaMutation.mutate(
      {
        guest_id: guestIdNum,
        category_id: categoryIdNum,
        room_id: form.room_id ? Number(form.room_id) : null,
        check_in_date: form.check_in_date,
        check_out_date: form.check_out_date,
        num_adults: Number(form.num_adults) || 1,
        num_children: Number(form.num_children) || 0,
        channel: form.channel as "booking" | "expedia" | "despegar" | "other_ota",
        external_id: form.external_id.trim(),
        total_amount: totalAmount,
        target_currency: totalAmount !== null ? form.target_currency : null,
        amount_paid: amountPaid
      },
      {
        onSuccess: (reservation) => setCreated(reservation),
        onError: (err: unknown) =>
          setError(err instanceof Error ? err.message : "No se pudo guardar la reserva de OTA")
      }
    );
  };

  return (
    <div data-testid="manual-ota-modal" className="fixed inset-0 z-30 flex items-center justify-center bg-slate-900/40 px-4 py-6">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">OTA</p>
            <h3 className="text-lg font-semibold text-slate-900">Cargar reserva de OTA</h3>
            <p className="text-xs text-slate-500">
              Booking, Expedia u otra OTA gestionada por fuera del motor de reservas.
            </p>
          </div>
          <button onClick={handleClose} type="button" className="text-sm text-slate-500 hover:text-slate-800">
            Cerrar
          </button>
        </div>

        {error && (
          <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800" role="alert">
            {error}
          </div>
        )}

        {created ? (
          <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900" role="status">
            <p className="font-semibold">
              Reserva {created.confirmation_code} guardada en {normalizeCurrencyCode(created.currency_code)}.
            </p>
            <p className="mt-1 text-xs text-emerald-800">
              Si el canal + ID externo ya existían, se actualizó esa reserva en vez de crear una nueva.
            </p>
            {created.fx_rate_snapshot ? (
              <p className="mt-1">
                Cotización usada: 1 {form.target_currency} = {created.fx_rate_snapshot.toLocaleString("es-AR")} ARS.
              </p>
            ) : (
              <p className="mt-1 text-xs text-emerald-800">
                No hay una conversión automática configurada para esta categoría: el monto se guardó directamente
                en {normalizeCurrencyCode(created.currency_code)}, sin tasa aplicada.
              </p>
            )}
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                onClick={reset}
                className="rounded-lg border border-emerald-300 bg-white px-3 py-2 text-xs font-semibold text-emerald-800 hover:bg-emerald-100"
              >
                Cargar otra
              </button>
              <button
                type="button"
                onClick={handleClose}
                className="rounded-lg border border-emerald-300 bg-white px-3 py-2 text-xs font-semibold text-emerald-800 hover:bg-emerald-100"
              >
                Cerrar
              </button>
            </div>
          </div>
        ) : (
          <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
            <GuestQuickCreatePanel
              guestId={guestId}
              onGuestIdChange={setGuestId}
              form={guestForm}
              onFormChange={setGuestForm}
              onGuestCreated={() => undefined}
              onError={setError}
            />

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-xs font-semibold text-slate-600">
                Categoría
                <select
                  value={form.category_id}
                  onChange={(e) => setForm((prev) => ({ ...prev, category_id: e.target.value, room_id: "" }))}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                >
                  <option value="">Elegí una categoría</option>
                  {(categoriesQuery.data ?? []).map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs font-semibold text-slate-600">
                Habitación (opcional)
                <select
                  value={form.room_id}
                  onChange={(e) => setForm((prev) => ({ ...prev, room_id: e.target.value }))}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                >
                  <option value="">Sin asignar</option>
                  {availableRooms.map((room) => (
                    <option key={room.id} value={room.id}>
                      {`Hab ${room.room_number || room.id}`}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-xs font-semibold text-slate-600">
                Check-in
                <input
                  type="date"
                  value={form.check_in_date}
                  onChange={(e) => setForm((prev) => ({ ...prev, check_in_date: e.target.value }))}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                />
              </label>
              <label className="text-xs font-semibold text-slate-600">
                Check-out
                <input
                  type="date"
                  value={form.check_out_date}
                  onChange={(e) => setForm((prev) => ({ ...prev, check_out_date: e.target.value }))}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                />
              </label>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-xs font-semibold text-slate-600">
                Adultos
                <input
                  type="number"
                  min={1}
                  value={form.num_adults}
                  onChange={(e) => setForm((prev) => ({ ...prev, num_adults: e.target.value }))}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                />
              </label>
              <label className="text-xs font-semibold text-slate-600">
                Niños
                <input
                  type="number"
                  min={0}
                  value={form.num_children}
                  onChange={(e) => setForm((prev) => ({ ...prev, num_children: e.target.value }))}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                />
              </label>
            </div>

            <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">Datos del canal</div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-xs font-semibold text-slate-600">
                Canal
                <select
                  value={form.channel}
                  onChange={(e) => setForm((prev) => ({ ...prev, channel: e.target.value }))}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                >
                  {CHANNEL_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs font-semibold text-slate-600">
                ID externo (código en la OTA)
                <input
                  value={form.external_id}
                  onChange={(e) => setForm((prev) => ({ ...prev, external_id: e.target.value }))}
                  placeholder="Ej: 4567891234"
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                />
              </label>
            </div>

            <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">Montos</div>
            <div className="grid gap-3 sm:grid-cols-3">
              <label className="text-xs font-semibold text-slate-600">
                Monto total
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.total_amount}
                  onChange={(e) => setForm((prev) => ({ ...prev, total_amount: e.target.value }))}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                />
              </label>
              <label className="text-xs font-semibold text-slate-600">
                Moneda
                <select
                  value={form.target_currency}
                  onChange={(e) => setForm((prev) => ({ ...prev, target_currency: e.target.value as "ARS" | "USD" }))}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                >
                  <option value="ARS">ARS</option>
                  <option value="USD">USD</option>
                </select>
              </label>
              <label className="text-xs font-semibold text-slate-600">
                Ya cobrado
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.amount_paid}
                  onChange={(e) => setForm((prev) => ({ ...prev, amount_paid: e.target.value }))}
                  placeholder="0.00"
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                />
              </label>
            </div>

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={handleClose}
                className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={createManualOtaMutation.isPending || guestMutation.isPending}
                className="rounded-lg border border-violet-200 bg-violet-600 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-700 disabled:opacity-60"
              >
                {createManualOtaMutation.isPending ? "Guardando..." : "Guardar reserva de OTA"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
