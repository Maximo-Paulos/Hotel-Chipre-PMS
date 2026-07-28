import { useEffect, useState } from "react";

import { ApiError } from "../api/client";
import { type GuestUpdatePayload } from "../api/guests";
import { type PaymentMethod } from "../api/payments";
import {
  useReservation,
  useReservationMutations,
  useReservationOperationsSummary,
  useValidateGuestCheckin
} from "../hooks/useReservations";
import { useGuest } from "../hooks/useGuests";
import { usePaymentMutation, usePaymentSummary } from "../hooks/usePayments";
import { formatMoney, normalizeCurrencyCode } from "../utils/currency";
import {
  canCancelReservation,
  canCheckInReservation,
  canCheckOutReservation,
  canPartialCheckIn,
  reservationStatusConfig
} from "../utils/reservationStatus";

type CheckinCaptureForm = {
  document_type: "" | "DNI" | "PASSPORT" | "CEDULA";
  document_number: string;
  nationality: string;
  country: string;
  birth_place: string;
  birth_country: string;
  marital_status: string;
  occupation: string;
  terms_accepted: boolean;
};

const emptyCaptureForm: CheckinCaptureForm = {
  document_type: "",
  document_number: "",
  nationality: "",
  country: "",
  birth_place: "",
  birth_country: "",
  marital_status: "",
  occupation: "",
  terms_accepted: false
};

type Props = {
  reservationId: number | null;
  onClose: () => void;
};

const paymentMethodOptions: Array<{ value: PaymentMethod; label: string }> = [
  { value: "cash", label: "Efectivo" },
  { value: "bank_transfer", label: "Transferencia" },
  { value: "mercado_pago", label: "Mercado Pago" },
  { value: "credit_card", label: "Tarjeta de crédito" },
  { value: "debit_card", label: "Tarjeta de débito" },
  { value: "paypal", label: "PayPal" }
];

function guestFullName(guest?: { first_name: string; last_name: string } | null, fallbackId?: number) {
  if (guest) return `${guest.first_name} ${guest.last_name}`.trim();
  return fallbackId ? `Huésped #${fallbackId}` : "Sin huésped";
}

export function ReservationDetailDrawer({ reservationId, onClose }: Props) {
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("cash");
  const [paymentAmount, setPaymentAmount] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [captureForm, setCaptureForm] = useState<CheckinCaptureForm>(emptyCaptureForm);
  const [companionForm, setCompanionForm] = useState({ first_name: "", last_name: "", document_number: "" });
  const [companionError, setCompanionError] = useState<string | null>(null);

  const reservationQuery = useReservation(reservationId ?? undefined);
  const operationsQuery = useReservationOperationsSummary(reservationId ?? undefined);
  const summaryQuery = usePaymentSummary(reservationId ?? undefined);
  const paymentMutation = usePaymentMutation(reservationId ?? undefined);
  const { cancelMutation, checkInMutation, partialCheckInMutation, checkOutMutation, addGuestsMutation } =
    useReservationMutations();

  const open = Boolean(reservationId);
  const reservation = reservationQuery.data;
  const operations = operationsQuery.data;
  const summary = summaryQuery.data;

  // B3.3/B3.4: FULLY_PAID/PRE_CHECK_IN is exactly when the guest's check-in
  // data (birth place/country, marital status, occupation, etc.) still
  // matters -- ask the backend if anything's missing before showing the
  // capture form, instead of waiting for a 400 on the actual check-in.
  const checkinDataRelevant = reservation?.status === "fully_paid" || reservation?.status === "pre_check_in";
  const guestQuery = useGuest(checkinDataRelevant ? reservation?.guest_id : undefined);
  const checkinValidation = useValidateGuestCheckin(checkinDataRelevant ? reservation?.guest_id : undefined);
  const needsCheckinCapture = checkinDataRelevant && checkinValidation.data?.valid === false;

  useEffect(() => {
    if (!guestQuery.data) return;
    setCaptureForm({
      document_type: guestQuery.data.document_type ?? "",
      document_number: guestQuery.data.document_number ?? "",
      nationality: guestQuery.data.nationality ?? "",
      country: guestQuery.data.country ?? "",
      birth_place: guestQuery.data.birth_place ?? "",
      birth_country: guestQuery.data.birth_country ?? "",
      marital_status: guestQuery.data.marital_status ?? "",
      occupation: guestQuery.data.occupation ?? "",
      terms_accepted: guestQuery.data.terms_accepted ?? false
    });
  }, [guestQuery.data]);

  const buildGuestPatch = (): GuestUpdatePayload => ({
    document_type: captureForm.document_type || undefined,
    document_number: captureForm.document_number.trim() || undefined,
    nationality: captureForm.nationality.trim() || undefined,
    country: captureForm.country.trim() || undefined,
    birth_place: captureForm.birth_place.trim() || undefined,
    birth_country: captureForm.birth_country.trim() || undefined,
    marital_status: captureForm.marital_status.trim() || undefined,
    occupation: captureForm.occupation.trim() || undefined,
    terms_accepted: captureForm.terms_accepted
  });

  const handleAddCompanion = () => {
    if (!reservationId) return;
    if (!companionForm.first_name.trim() || !companionForm.last_name.trim()) {
      setCompanionError("Completá nombre y apellido del acompañante.");
      return;
    }
    setCompanionError(null);
    addGuestsMutation.mutate(
      {
        id: reservationId,
        guests: [
          {
            first_name: companionForm.first_name.trim(),
            last_name: companionForm.last_name.trim(),
            document_number: companionForm.document_number.trim() || undefined
          }
        ]
      },
      {
        onSuccess: () => setCompanionForm({ first_name: "", last_name: "", document_number: "" }),
        onError: (err) =>
          setCompanionError(err instanceof ApiError ? err.message : "No se pudo agregar el acompañante.")
      }
    );
  };
  // Bug documented in frontend/src/api/payments.ts: total_amount/balance_due
  // ignore consumption charges. Always prefer the operational figures for
  // anything the operator will actually collect.
  const currencyCode = normalizeCurrencyCode(summary?.currency_code ?? reservation?.currency_code);
  const operationalBalanceDue = summary?.operational_balance_due ?? summary?.balance_due;

  const runAction = (label: string, action: () => void) => {
    setActionError(null);
    setActionMessage(null);
    try {
      action();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : `No se pudo completar: ${label}.`);
    }
  };

  const handlePay = () => {
    if (!reservationId) return;
    const amount = Number(paymentAmount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setActionError("Ingresá un importe válido para cobrar.");
      return;
    }
    setActionError(null);
    setActionMessage(null);
    paymentMutation.mutate(
      {
        reservation_id: reservationId,
        amount,
        payment_method: paymentMethod,
        transaction_type: reservation?.status === "pending" ? "deposit" : "balance_payment",
        currency: currencyCode
      },
      {
        onSuccess: () => {
          setPaymentAmount("");
          setActionMessage("Pago registrado.");
        },
        onError: (err) => setActionError(err instanceof ApiError ? err.message : "No se pudo registrar el pago.")
      }
    );
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex" role="dialog" aria-modal="true" aria-labelledby="reservation-drawer-title">
      <div className="flex-1 animate-fade-in bg-black/30" onClick={onClose} />
      <div className="flex w-full max-w-xl animate-slide-in-right flex-col border-l border-slate-200 bg-white shadow-xl">
        <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-wide text-slate-500">Reserva</p>
            <h3 id="reservation-drawer-title" className="truncate text-lg font-semibold text-slate-900">
              {reservation ? reservation.confirmation_code : `#${reservationId}`}
            </h3>
            {reservation && (
              <span
                className={`mt-1 inline-block rounded-full px-2 py-1 text-xs font-semibold ${reservationStatusConfig[reservation.status]?.className ?? "bg-slate-100 text-slate-800"}`}
              >
                {reservationStatusConfig[reservation.status]?.label ?? reservation.status}
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar detalle de reserva"
            className="text-lg leading-none text-slate-500 hover:text-slate-800"
          >
            ×
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4 text-sm text-slate-700">
          {reservationQuery.isLoading && <p className="text-slate-500">Cargando reserva...</p>}
          {reservationQuery.isError && (
            <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-rose-700">
              No se pudo cargar la reserva. Cerrá y volvé a intentar.
            </p>
          )}

          {reservation && (
            <>
              <section className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Estadía</p>
                <p className="mt-1 font-semibold text-slate-900">
                  {reservation.check_in_date} → {reservation.check_out_date}
                </p>
                <p className="text-xs text-slate-500">
                  {reservation.room_id ? `Habitación #${reservation.room_id}` : "Sin habitación asignada"} · Categoría{" "}
                  {reservation.category_id}
                </p>
              </section>

              <section className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Huéspedes</p>
                <p data-testid="drawer-guest-name" className="mt-1 font-semibold text-slate-900">{guestFullName(reservation.guest, reservation.guest_id)}</p>
                <p className="text-xs text-slate-500">Titular</p>
                {reservation.additional_guests && reservation.additional_guests.length > 0 ? (
                  <ul className="mt-2 space-y-1">
                    {reservation.additional_guests.map((guest) => (
                      <li key={guest.id} className="text-sm text-slate-800">
                        {guestFullName(guest)}
                        <span className="ml-2 text-xs text-slate-500">Acompañante</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-xs text-slate-500">Sin acompañantes cargados.</p>
                )}

                {reservation.status !== "cancelled" && reservation.status !== "checked_out" && (
                  <div className="mt-3 border-t border-slate-200 pt-3">
                    <p className="text-xs uppercase tracking-wide text-slate-500">Agregar acompañante</p>
                    <div className="mt-2 flex flex-wrap items-end gap-2">
                      <input
                        type="text"
                        placeholder="Nombre"
                        value={companionForm.first_name}
                        onChange={(event) => setCompanionForm((prev) => ({ ...prev, first_name: event.target.value }))}
                        className="w-28 rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label="Nombre del acompañante"
                      />
                      <input
                        type="text"
                        placeholder="Apellido"
                        value={companionForm.last_name}
                        onChange={(event) => setCompanionForm((prev) => ({ ...prev, last_name: event.target.value }))}
                        className="w-28 rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label="Apellido del acompañante"
                      />
                      <input
                        type="text"
                        placeholder="Documento (opcional)"
                        value={companionForm.document_number}
                        onChange={(event) =>
                          setCompanionForm((prev) => ({ ...prev, document_number: event.target.value }))
                        }
                        className="w-36 rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label="Documento del acompañante"
                      />
                      <button
                        type="button"
                        onClick={handleAddCompanion}
                        disabled={addGuestsMutation.isPending}
                        className="rounded-lg border border-slate-300 bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {addGuestsMutation.isPending ? "Agregando..." : "Agregar"}
                      </button>
                    </div>
                    {companionError && <p className="mt-2 text-xs text-rose-700">{companionError}</p>}
                  </div>
                )}
              </section>

              {needsCheckinCapture && (
                <section className="rounded-lg border border-amber-200 bg-amber-50 p-3" data-testid="checkin-capture-form">
                  <p className="text-xs uppercase tracking-wide text-amber-800">Completar datos para el check-in</p>
                  {checkinValidation.data && checkinValidation.data.errors.length > 0 && (
                    <p className="mt-1 text-xs text-amber-800">{checkinValidation.data.errors.join("; ")}</p>
                  )}
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">Tipo de documento</span>
                      <select
                        value={captureForm.document_type}
                        onChange={(event) =>
                          setCaptureForm((prev) => ({
                            ...prev,
                            document_type: event.target.value as CheckinCaptureForm["document_type"]
                          }))
                        }
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                      >
                        <option value="">Sin especificar</option>
                        <option value="DNI">DNI</option>
                        <option value="PASSPORT">Pasaporte</option>
                        <option value="CEDULA">Cédula</option>
                      </select>
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">Número de documento</span>
                      <input
                        type="text"
                        value={captureForm.document_number}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, document_number: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">Nacionalidad</span>
                      <input
                        type="text"
                        value={captureForm.nationality}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, nationality: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">País</span>
                      <input
                        type="text"
                        value={captureForm.country}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, country: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">Lugar de nacimiento</span>
                      <input
                        type="text"
                        value={captureForm.birth_place}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, birth_place: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label="Lugar de nacimiento"
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">País de nacimiento</span>
                      <input
                        type="text"
                        value={captureForm.birth_country}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, birth_country: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label="País de nacimiento"
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">Estado civil</span>
                      <input
                        type="text"
                        value={captureForm.marital_status}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, marital_status: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label="Estado civil"
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">Profesión</span>
                      <input
                        type="text"
                        value={captureForm.occupation}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, occupation: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label="Profesión"
                      />
                    </label>
                  </div>
                  <label className="mt-2 flex items-center gap-2 text-xs text-slate-700">
                    <input
                      type="checkbox"
                      checked={captureForm.terms_accepted}
                      onChange={(event) => setCaptureForm((prev) => ({ ...prev, terms_accepted: event.target.checked }))}
                    />
                    Acepta términos y condiciones
                  </label>
                </section>
              )}

              <section className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Cobros</p>
                  {summaryQuery.isFetching && <span className="text-xs text-slate-500">Actualizando...</span>}
                </div>
                {summaryQuery.isLoading ? (
                  <p className="mt-2 text-slate-500">Cargando resumen financiero...</p>
                ) : summary ? (
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    <div>
                      <p className="text-xs text-slate-500">Total operativo</p>
                      <p className="font-semibold">
                        {formatMoney(operations?.financial_summary?.operational_total_amount ?? summary.total_amount, currencyCode)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Pagado</p>
                      <p className="font-semibold">{formatMoney(summary.amount_paid, currencyCode)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Saldo operativo</p>
                      <p className="font-semibold text-slate-900" data-testid="drawer-balance-due">
                        {formatMoney(operationalBalanceDue ?? 0, currencyCode)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Depósito requerido</p>
                      <p className="font-semibold">{formatMoney(summary.deposit_required, currencyCode)}</p>
                    </div>
                  </div>
                ) : (
                  <p className="mt-2 text-rose-700">No se pudo cargar el resumen financiero.</p>
                )}
                {(reservation.quoted_amount_ars != null || reservation.quoted_amount_usd != null) && (
                  <div className="mt-3 rounded-md border border-slate-200 bg-white p-2">
                    <p className="text-xs font-semibold text-slate-700">Montos para informar al huésped</p>
                    <p className="mt-1 text-xs text-slate-500">
                      Cargados a mano por la OTA, no son una conversión entre sí.
                    </p>
                    <div className="mt-1 grid grid-cols-2 gap-2">
                      <div>
                        <p className="text-xs text-slate-500">En pesos</p>
                        <p className="font-semibold">
                          {reservation.quoted_amount_ars != null ? formatMoney(reservation.quoted_amount_ars, "ARS") : "—"}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">En dólares</p>
                        <p className="font-semibold">
                          {reservation.quoted_amount_usd != null ? formatMoney(reservation.quoted_amount_usd, "USD") : "—"}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </section>

              {reservation.status !== "cancelled" && reservation.status !== "checked_out" && (
                <section className="rounded-lg border border-slate-200 bg-white p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Cobrar</p>
                  <div className="mt-2 flex flex-wrap items-end gap-2">
                    <label className="flex-1 space-y-1 text-xs">
                      <span className="text-slate-600">Importe</span>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={paymentAmount}
                        onChange={(event) => setPaymentAmount(event.target.value)}
                        placeholder={operationalBalanceDue ? String(operationalBalanceDue) : "0"}
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                        aria-label="Importe a cobrar"
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">Método</span>
                      <select
                        value={paymentMethod}
                        onChange={(event) => setPaymentMethod(event.target.value as PaymentMethod)}
                        className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                        aria-label="Método de pago"
                      >
                        {paymentMethodOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      onClick={handlePay}
                      disabled={paymentMutation.isPending}
                      className="rounded-lg border border-emerald-200 bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {paymentMutation.isPending ? "Cobrando..." : "Registrar cobro"}
                    </button>
                  </div>
                </section>
              )}

              {operations?.pending_actions && operations.pending_actions.length > 0 && (
                <section className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                  <p className="text-xs uppercase tracking-wide text-amber-800">Acciones pendientes</p>
                  <ul className="mt-2 space-y-1">
                    {operations.pending_actions.map((action) => (
                      <li key={action.action_key} className="text-sm text-amber-900">
                        {action.title}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {(actionError || actionMessage) && (
                <div
                  className={`rounded-lg border px-3 py-2 text-sm ${
                    actionError ? "border-rose-200 bg-rose-50 text-rose-700" : "border-emerald-200 bg-emerald-50 text-emerald-800"
                  }`}
                >
                  {actionError || actionMessage}
                </div>
              )}

              <section className="flex flex-wrap gap-2 border-t border-slate-200 pt-3">
                {canPartialCheckIn(reservation.status) && (
                  <button
                    type="button"
                    disabled={partialCheckInMutation.isPending}
                    onClick={() =>
                      runAction("check-in parcial", () =>
                        partialCheckInMutation.mutate(
                          { id: reservation.id, guest: needsCheckinCapture ? buildGuestPatch() : undefined },
                          {
                            onSuccess: () => setActionMessage("Check-in parcial registrado."),
                            onError: (err) =>
                              setActionError(err instanceof ApiError ? err.message : "No se pudo hacer el check-in parcial.")
                          }
                        )
                      )
                    }
                    className="rounded-lg border border-teal-200 bg-teal-50 px-3 py-2 text-xs font-semibold text-teal-700 hover:border-teal-300 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Check-in parcial
                  </button>
                )}
                <button
                  type="button"
                  disabled={!canCheckInReservation(reservation.status) || checkInMutation.isPending}
                  onClick={() =>
                    runAction("check-in", () =>
                      checkInMutation.mutate(
                        { id: reservation.id, guest: needsCheckinCapture ? buildGuestPatch() : undefined },
                        {
                          onSuccess: () => setActionMessage("Check-in registrado."),
                          onError: (err) => setActionError(err instanceof ApiError ? err.message : "No se pudo hacer check-in.")
                        }
                      )
                    )
                  }
                  className="rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700 hover:border-brand-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Confirmar check-in
                </button>
                <button
                  type="button"
                  disabled={!canCheckOutReservation(reservation.status) || checkOutMutation.isPending}
                  onClick={() =>
                    runAction("check-out", () =>
                      checkOutMutation.mutate(reservation.id, {
                        onSuccess: () => setActionMessage("Check-out registrado."),
                        onError: (err) => setActionError(err instanceof ApiError ? err.message : "No se pudo hacer check-out.")
                      })
                    )
                  }
                  className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-700 hover:border-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Check-out
                </button>
                <button
                  type="button"
                  disabled={!canCancelReservation(reservation.status) || cancelMutation.isPending}
                  onClick={() =>
                    runAction("cancelación", () =>
                      cancelMutation.mutate(reservation.id, {
                        onSuccess: () => setActionMessage("Reserva cancelada."),
                        onError: (err) => setActionError(err instanceof ApiError ? err.message : "No se pudo cancelar.")
                      })
                    )
                  }
                  className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700 hover:border-rose-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Cancelar
                </button>
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default ReservationDetailDrawer;
