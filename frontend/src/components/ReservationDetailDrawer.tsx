import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { type TFunction } from "i18next";

import { ApiError } from "../api/client";
import { type GuestUpdatePayload } from "../api/guests";
import { type RestrictionOverride } from "../api/guestRestrictions";
import { type PaymentMethod } from "../api/payments";
import { useDialogA11y } from "../hooks/useDialogA11y";
import {
  useReservation,
  useReservationMutations,
  useReservationOperationsSummary,
  useValidateGuestCheckin
} from "../hooks/useReservations";
import { useGuest } from "../hooks/useGuests";
import { usePaymentMutation, usePaymentSummary } from "../hooks/usePayments";
import { useRestrictionOverridePrompt } from "../hooks/useRestrictionOverridePrompt";
import { formatMoney, normalizeCurrencyCode } from "../utils/currency";
import {
  canCancelReservation,
  canCheckInReservation,
  canCheckOutReservation,
  canPartialCheckIn,
  reservationStatusConfig
} from "../utils/reservationStatus";

import { GuestRestrictionBadge } from "./GuestRestrictionBadge";
import { RestrictionOverrideModal } from "./RestrictionOverrideModal";

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

const paymentMethodValues: PaymentMethod[] = [
  "cash",
  "bank_transfer",
  "mercado_pago",
  "credit_card",
  "debit_card",
  "paypal"
];

function guestFullName(
  t: TFunction,
  guest?: { first_name: string; last_name: string } | null,
  fallbackId?: number
) {
  if (guest) return `${guest.first_name} ${guest.last_name}`.trim();
  return fallbackId ? t("drawer.guests.guestFallbackWithId", { id: fallbackId }) : t("drawer.guests.guestFallbackNone");
}

export function ReservationDetailDrawer({ reservationId, onClose }: Props) {
  const { t } = useTranslation("reservations");
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
  const restrictionOverridePrompt = useRestrictionOverridePrompt();

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

  const handleAddCompanion = async () => {
    if (!reservationId) return;
    if (!companionForm.first_name.trim() || !companionForm.last_name.trim()) {
      setCompanionError(t("drawer.errors.companionRequired"));
      return;
    }
    setCompanionError(null);
    try {
      await addGuestsMutation.mutateAsync({
        id: reservationId,
        guests: [
          {
            first_name: companionForm.first_name.trim(),
            last_name: companionForm.last_name.trim(),
            document_number: companionForm.document_number.trim() || undefined
          }
        ]
      });
      setCompanionForm({ first_name: "", last_name: "", document_number: "" });
    } catch (err) {
      setCompanionError(err instanceof ApiError ? err.message : t("drawer.errors.addCompanionFailed"));
    }
  };
  // Bug documented in frontend/src/api/payments.ts: total_amount/balance_due
  // ignore consumption charges. Always prefer the operational figures for
  // anything the operator will actually collect.
  const currencyCode = normalizeCurrencyCode(summary?.currency_code ?? reservation?.currency_code);
  const operationalBalanceDue = summary?.operational_balance_due ?? summary?.balance_due;

  const runAction = async (label: string, action: () => Promise<unknown>, onSuccess: () => void) => {
    setActionError(null);
    setActionMessage(null);
    try {
      await action();
      onSuccess();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : t("drawer.errors.actionFailed", { label }));
    }
  };

  const handlePay = async () => {
    if (!reservationId) return;
    const amount = Number(paymentAmount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setActionError(t("drawer.errors.invalidAmount"));
      return;
    }
    setActionError(null);
    setActionMessage(null);
    try {
      // usePaymentMutation keeps this promise pending until the server-backed
      // reservation, operations, payment, cash and analytics queries have
      // refetched. The drawer must not report success or become closable before
      // that confirmation arrives.
      await paymentMutation.mutateAsync({
        reservation_id: reservationId,
        amount,
        payment_method: paymentMethod,
        transaction_type: reservation?.status === "pending" ? "deposit" : "balance_payment",
        currency: currencyCode
      });
      setPaymentAmount("");
      setActionMessage(t("drawer.messages.paymentRegistered"));
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : t("drawer.errors.paymentFailed"));
    }
  };

  const handleClose = () => {
    if (
      paymentMutation.isPending ||
      addGuestsMutation.isPending ||
      partialCheckInMutation.isPending ||
      checkInMutation.isPending ||
      checkOutMutation.isPending ||
      cancelMutation.isPending
    ) {
      return;
    }
    onClose();
  };

  const submitCheckIn = async (restrictionOverride?: RestrictionOverride): Promise<void> => {
    if (!reservationId || !reservation) return;
    setActionError(null);
    setActionMessage(null);
    try {
      await checkInMutation.mutateAsync({
        id: reservation.id,
        guest: needsCheckinCapture ? buildGuestPatch() : undefined,
        restriction_override: restrictionOverride
      });
      setActionMessage(t("drawer.messages.checkInDone"));
    } catch (err) {
      // The guest has an active GuestRestriction -- prompt for an override
      // reason and retry through the same atomic endpoint.
      if (restrictionOverridePrompt.handleError(err, (override) => void submitCheckIn(override))) return;
      setActionError(err instanceof ApiError ? err.message : t("drawer.errors.checkInFailed"));
    }
  };

  const containerRef = useDialogA11y(open, handleClose);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex" role="dialog" aria-modal="true" aria-labelledby="reservation-drawer-title">
      <div className="flex-1 animate-fade-in bg-black/30" onClick={handleClose} />
      <div
        ref={containerRef}
        tabIndex={-1}
        className="flex w-full max-w-xl animate-slide-in-right flex-col border-l border-slate-200 bg-white shadow-xl outline-none"
      >
        <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-wide text-slate-500">{t("drawer.reservationLabel")}</p>
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
            onClick={handleClose}
            disabled={paymentMutation.isPending}
            aria-label={t("drawer.closeAria")}
            className="text-lg leading-none text-slate-500 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            ×
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4 text-sm text-slate-700">
          {reservationQuery.isLoading && <p className="text-slate-500">{t("drawer.loading")}</p>}
          {reservationQuery.isError && (
            <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-rose-700">
              {t("drawer.loadError")}
            </p>
          )}

          {reservation && (
            <>
              <section className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">{t("drawer.stay.title")}</p>
                <p className="mt-1 font-semibold text-slate-900">
                  {reservation.check_in_date} → {reservation.check_out_date}
                </p>
                <p className="text-xs text-slate-500">
                  {reservation.room_id
                    ? t("drawer.stay.roomNumber", { id: reservation.room_id })
                    : t("drawer.stay.noRoomAssigned")}{" "}
                  · {t("drawer.stay.category")}{" "}
                  {reservation.category_id}
                </p>
              </section>

              <section className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">{t("drawer.guests.title")}</p>
                <p data-testid="drawer-guest-name" className="mt-1 font-semibold text-slate-900">{guestFullName(t, reservation.guest, reservation.guest_id)}</p>
                <p className="text-xs text-slate-500">{t("drawer.guests.primary")}</p>
                {reservation.guest_id ? (
                  <GuestRestrictionBadge guestId={reservation.guest_id} className="mt-1" />
                ) : null}
                {reservation.additional_guests && reservation.additional_guests.length > 0 ? (
                  <ul className="mt-2 space-y-1">
                    {reservation.additional_guests.map((guest) => (
                      <li key={guest.id} className="text-sm text-slate-800">
                        {guestFullName(t, guest)}
                        <span className="ml-2 text-xs text-slate-500">{t("drawer.guests.companion")}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-xs text-slate-500">{t("drawer.guests.noCompanions")}</p>
                )}

                {reservation.status !== "cancelled" && reservation.status !== "checked_out" && (
                  <div className="mt-3 border-t border-slate-200 pt-3">
                    <p className="text-xs uppercase tracking-wide text-slate-500">{t("drawer.guests.addCompanion")}</p>
                    <div className="mt-2 flex flex-wrap items-end gap-2">
                      <input
                        type="text"
                        placeholder={t("drawer.guests.firstNamePlaceholder")}
                        value={companionForm.first_name}
                        onChange={(event) => setCompanionForm((prev) => ({ ...prev, first_name: event.target.value }))}
                        className="w-28 rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label={t("drawer.guests.firstNameAria")}
                      />
                      <input
                        type="text"
                        placeholder={t("drawer.guests.lastNamePlaceholder")}
                        value={companionForm.last_name}
                        onChange={(event) => setCompanionForm((prev) => ({ ...prev, last_name: event.target.value }))}
                        className="w-28 rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label={t("drawer.guests.lastNameAria")}
                      />
                      <input
                        type="text"
                        placeholder={t("drawer.guests.documentPlaceholder")}
                        value={companionForm.document_number}
                        onChange={(event) =>
                          setCompanionForm((prev) => ({ ...prev, document_number: event.target.value }))
                        }
                        className="w-36 rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label={t("drawer.guests.documentAria")}
                      />
                      <button
                        type="button"
                        onClick={handleAddCompanion}
                        disabled={addGuestsMutation.isPending}
                        className="rounded-lg border border-slate-300 bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {addGuestsMutation.isPending ? t("drawer.guests.adding") : t("drawer.guests.add")}
                      </button>
                    </div>
                    {companionError && <p className="mt-2 text-xs text-rose-700">{companionError}</p>}
                  </div>
                )}
              </section>

              {needsCheckinCapture && (
                <section className="rounded-lg border border-amber-200 bg-amber-50 p-3" data-testid="checkin-capture-form">
                  <p className="text-xs uppercase tracking-wide text-amber-800">{t("drawer.checkinCapture.title")}</p>
                  {checkinValidation.data && checkinValidation.data.errors.length > 0 && (
                    <p className="mt-1 text-xs text-amber-800">{checkinValidation.data.errors.join("; ")}</p>
                  )}
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.checkinCapture.documentType")}</span>
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
                        <option value="">{t("drawer.checkinCapture.documentTypeUnspecified")}</option>
                        <option value="DNI">{t("drawer.checkinCapture.documentTypeDni")}</option>
                        <option value="PASSPORT">{t("drawer.checkinCapture.documentTypePassport")}</option>
                        <option value="CEDULA">{t("drawer.checkinCapture.documentTypeCedula")}</option>
                      </select>
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.checkinCapture.documentNumber")}</span>
                      <input
                        type="text"
                        value={captureForm.document_number}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, document_number: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.checkinCapture.nationality")}</span>
                      <input
                        type="text"
                        value={captureForm.nationality}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, nationality: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.checkinCapture.country")}</span>
                      <input
                        type="text"
                        value={captureForm.country}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, country: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.checkinCapture.birthPlace")}</span>
                      <input
                        type="text"
                        value={captureForm.birth_place}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, birth_place: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label={t("drawer.checkinCapture.birthPlace")}
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.checkinCapture.birthCountry")}</span>
                      <input
                        type="text"
                        value={captureForm.birth_country}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, birth_country: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label={t("drawer.checkinCapture.birthCountry")}
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.checkinCapture.maritalStatus")}</span>
                      <input
                        type="text"
                        value={captureForm.marital_status}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, marital_status: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label={t("drawer.checkinCapture.maritalStatus")}
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.checkinCapture.occupation")}</span>
                      <input
                        type="text"
                        value={captureForm.occupation}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, occupation: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label={t("drawer.checkinCapture.occupation")}
                      />
                    </label>
                  </div>
                  <label className="mt-2 flex items-center gap-2 text-xs text-slate-700">
                    <input
                      type="checkbox"
                      checked={captureForm.terms_accepted}
                      onChange={(event) => setCaptureForm((prev) => ({ ...prev, terms_accepted: event.target.checked }))}
                    />
                    {t("drawer.checkinCapture.acceptTerms")}
                  </label>
                </section>
              )}

              <section className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs uppercase tracking-wide text-slate-500">{t("drawer.billing.title")}</p>
                  {summaryQuery.isFetching && <span className="text-xs text-slate-500">{t("drawer.billing.updating")}</span>}
                </div>
                {summaryQuery.isLoading ? (
                  <p className="mt-2 text-slate-500">{t("drawer.billing.loadingSummary")}</p>
                ) : summary ? (
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    <div>
                      <p className="text-xs text-slate-500">{t("drawer.billing.operationalTotal")}</p>
                      <p className="font-semibold">
                        {formatMoney(operations?.financial_summary?.operational_total_amount ?? summary.total_amount, currencyCode)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">{t("drawer.billing.paid")}</p>
                      <p className="font-semibold">{formatMoney(summary.amount_paid, currencyCode)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">{t("drawer.billing.operationalBalance")}</p>
                      <p className="font-semibold text-slate-900" data-testid="drawer-balance-due">
                        {formatMoney(operationalBalanceDue ?? 0, currencyCode)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">{t("drawer.billing.depositRequired")}</p>
                      <p className="font-semibold">{formatMoney(summary.deposit_required, currencyCode)}</p>
                    </div>
                  </div>
                ) : (
                  <p className="mt-2 text-rose-700">{t("drawer.billing.loadError")}</p>
                )}
                {(reservation.quoted_amount_ars != null || reservation.quoted_amount_usd != null) && (
                  <div className="mt-3 rounded-md border border-slate-200 bg-white p-2">
                    <p className="text-xs font-semibold text-slate-700">{t("drawer.billing.amountsTitle")}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {t("drawer.billing.amountsHint")}
                    </p>
                    <div className="mt-1 grid grid-cols-2 gap-2">
                      <div>
                        <p className="text-xs text-slate-500">{t("drawer.billing.inPesos")}</p>
                        <p className="font-semibold">
                          {reservation.quoted_amount_ars != null ? formatMoney(reservation.quoted_amount_ars, "ARS") : "—"}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">{t("drawer.billing.inDollars")}</p>
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
                  <p className="text-xs uppercase tracking-wide text-slate-500">{t("drawer.payment.title")}</p>
                  <div className="mt-2 flex flex-wrap items-end gap-2">
                    <label className="flex-1 space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.payment.amountLabel")}</span>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={paymentAmount}
                        onChange={(event) => setPaymentAmount(event.target.value)}
                        placeholder={operationalBalanceDue ? String(operationalBalanceDue) : "0"}
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                        aria-label={t("drawer.payment.amountAria")}
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.payment.methodLabel")}</span>
                      <select
                        value={paymentMethod}
                        onChange={(event) => setPaymentMethod(event.target.value as PaymentMethod)}
                        className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                        aria-label={t("drawer.payment.methodAria")}
                      >
                        {paymentMethodValues.map((value) => (
                          <option key={value} value={value}>
                            {t(`drawer.payment.methods.${value}`)}
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
                      {paymentMutation.isPending ? t("drawer.payment.submitting") : t("drawer.payment.submit")}
                    </button>
                  </div>
                </section>
              )}

              {operations?.pending_actions && operations.pending_actions.length > 0 && (
                <section className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                  <p className="text-xs uppercase tracking-wide text-amber-800">{t("drawer.pendingActionsTitle")}</p>
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
                      void runAction(
                        t("drawer.actions.labels.partialCheckIn"),
                        () => partialCheckInMutation.mutateAsync({ id: reservation.id, guest: needsCheckinCapture ? buildGuestPatch() : undefined }),
                        () => setActionMessage(t("drawer.messages.partialCheckInDone"))
                      )
                    }
                    className="rounded-lg border border-teal-200 bg-teal-50 px-3 py-2 text-xs font-semibold text-teal-700 hover:border-teal-300 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {t("drawer.actions.partialCheckIn")}
                  </button>
                )}
                <button
                  type="button"
                  disabled={!canCheckInReservation(reservation.status) || checkInMutation.isPending}
                  onClick={() => void submitCheckIn()}
                  className="rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700 hover:border-brand-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {t("drawer.actions.confirmCheckIn")}
                </button>
                <button
                  type="button"
                  disabled={!canCheckOutReservation(reservation.status) || checkOutMutation.isPending}
                  onClick={() =>
                    void runAction(
                      t("drawer.actions.labels.checkOut"),
                      () => checkOutMutation.mutateAsync(reservation.id),
                      () => setActionMessage(t("drawer.messages.checkOutDone"))
                    )
                  }
                  className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-700 hover:border-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {t("drawer.actions.checkOut")}
                </button>
                <button
                  type="button"
                  disabled={!canCancelReservation(reservation.status) || cancelMutation.isPending}
                  onClick={() =>
                    void runAction(
                      t("drawer.actions.labels.cancel"),
                      () => cancelMutation.mutateAsync(reservation.id),
                      () => setActionMessage(t("drawer.messages.cancelled"))
                    )
                  }
                  className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700 hover:border-rose-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {t("drawer.actions.cancel")}
                </button>
              </section>
            </>
          )}
        </div>
      </div>

      {restrictionOverridePrompt.phase !== "idle" ? (
        <RestrictionOverrideModal
          phase={restrictionOverridePrompt.phase}
          onSubmit={restrictionOverridePrompt.submit}
          onCancel={restrictionOverridePrompt.dismiss}
          isPending={checkInMutation.isPending}
        />
      ) : null}
    </div>
  );
}

export default ReservationDetailDrawer;
