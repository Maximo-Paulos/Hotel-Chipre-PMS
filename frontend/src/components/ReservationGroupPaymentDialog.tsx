import { useTranslation } from "react-i18next";

import type { PaymentMethod } from "../api/payments";
import type { ReservationGroupSummary } from "../api/reservations";
import { formatMoney } from "../utils/currency";

import { CashTenderField } from "./CashTenderField";

export type ReservationGroupPaymentDialogProps = {
  group: ReservationGroupSummary;
  totalInput: string;
  onTotalInputChange: (value: string) => void;
  paymentMethod: PaymentMethod;
  paymentMethods: PaymentMethod[];
  onPaymentMethodChange: (method: PaymentMethod) => void;
  allocations: Record<number, string>;
  onAllocationChange: (reservationId: number, value: string) => void;
  requestedCents: number;
  allocatedCents: number;
  isManualPaymentMethod: boolean;
  paymentReference: string;
  onPaymentReferenceChange: (value: string) => void;
  paymentDescription: string;
  onPaymentDescriptionChange: (value: string) => void;
  paymentGross: number;
  cashReceivedAmountInput: string;
  onCashReceivedAmountChange: (value: string) => void;
  cashTipAmountInput: string;
  onCashTipAmountChange: (value: string) => void;
  cashTenderInvalid: boolean;
  cashTipInvalid: boolean;
  pending: boolean;
  error: string | null;
  onClearError: () => void;
  onClose: () => void;
  onSubmit: () => Promise<void>;
};

export function ReservationGroupPaymentDialog({
  group,
  totalInput,
  onTotalInputChange,
  paymentMethod,
  paymentMethods,
  onPaymentMethodChange,
  allocations,
  onAllocationChange,
  requestedCents,
  allocatedCents,
  isManualPaymentMethod,
  paymentReference,
  onPaymentReferenceChange,
  paymentDescription,
  onPaymentDescriptionChange,
  paymentGross,
  cashReceivedAmountInput,
  onCashReceivedAmountChange,
  cashTipAmountInput,
  onCashTipAmountChange,
  cashTenderInvalid,
  cashTipInvalid,
  pending,
  error,
  onClearError,
  onClose,
  onSubmit
}: ReservationGroupPaymentDialogProps) {
  const { t } = useTranslation("reservations");

  return (
    <div className="fixed inset-0 z-40 flex animate-fade-in items-center justify-center bg-slate-900/40 px-4 py-6">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="group-payment-title"
        className="max-h-[90vh] w-full max-w-2xl animate-scale-in overflow-y-auto rounded-xl border border-slate-200 bg-white p-6 shadow-xl"
        data-testid="reservation-group-payment-dialog"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="group-payment-title" className="text-lg font-semibold text-slate-900">
              {t("page.groups.paymentTitle", { guest: group.guest_name })}
            </h2>
            <p className="mt-1 text-xs text-slate-600">{t("page.groups.paymentHint")}</p>
          </div>
          <button
            type="button"
            disabled={pending}
            onClick={onClose}
            className="text-sm text-slate-600 hover:text-slate-900 disabled:opacity-50"
          >
            {t("page.common.close")}
          </button>
        </div>

        {error && (
          <div className="mt-4 flex items-start justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">
            <p>{error}</p>
            <button type="button" onClick={onClearError} className="shrink-0 text-xs font-semibold underline">
              {t("page.groups.paymentCloseError")}
            </button>
          </div>
        )}

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="text-sm font-semibold text-slate-700">
            {t("page.groups.paymentTotal")}
            <div className="mt-1 flex items-center gap-2">
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={totalInput}
                onChange={(event) => onTotalInputChange(event.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2"
                data-testid="group-payment-received-amount"
              />
              <span className="text-xs text-slate-500">{group.currency_code}</span>
            </div>
          </label>
          <label className="text-sm font-semibold text-slate-700">
            {t("page.groups.paymentMethod")}
            <select
              value={paymentMethod}
              onChange={(event) => onPaymentMethodChange(event.target.value as PaymentMethod)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
              data-testid="group-payment-method"
            >
              {paymentMethods.map((method) => (
                <option key={method} value={method}>{t(`page.paymentMethods.${method}`)}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-4 rounded-lg border border-slate-200">
          <div className="grid grid-cols-[1fr_9rem] gap-3 border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700">
            <span>{t("page.groups.paymentAllocation")}</span>
            <span className="text-right">{group.currency_code}</span>
          </div>
          <div className="divide-y divide-slate-100">
            {group.reservations.map((child) => (
              <label key={child.id} className="grid grid-cols-[1fr_9rem] items-center gap-3 px-3 py-2 text-sm">
                <span className="min-w-0">
                  <span className="block font-medium text-slate-800">{child.confirmation_code}</span>
                  <span className="block text-xs text-slate-500">
                    {t("page.groups.balance")}: {formatMoney(child.balance_due, child.currency_code)}
                  </span>
                </span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  max={child.balance_due ?? undefined}
                  disabled={child.company_billing_deferred || child.balance_due === null}
                  value={allocations[child.id] ?? ""}
                  onChange={(event) => onAllocationChange(child.id, event.target.value)}
                  className="w-full rounded-lg border border-slate-200 px-2 py-2 text-right"
                  aria-label={`${t("page.groups.paymentAllocation")} ${child.confirmation_code}`}
                />
              </label>
            ))}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 bg-slate-50 px-3 py-2 text-xs">
            <span className="text-slate-600">{t("page.groups.paymentAllocated")}</span>
            <strong className={requestedCents === allocatedCents ? "text-emerald-700" : "text-rose-700"}>
              {formatMoney(allocatedCents / 100, group.currency_code)} / {formatMoney(totalInput, group.currency_code)}
            </strong>
          </div>
        </div>

        {isManualPaymentMethod && (
          <label className="mt-4 block text-sm font-semibold text-slate-700">
            {t("page.groups.paymentReference")}
            <input
              value={paymentReference}
              onChange={(event) => onPaymentReferenceChange(event.target.value)}
              maxLength={120}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
              data-testid="group-payment-reference"
            />
          </label>
        )}
        <label className="mt-4 block text-sm font-semibold text-slate-700">
          {t("page.groups.paymentDescription")}
          <input
            value={paymentDescription}
            onChange={(event) => onPaymentDescriptionChange(event.target.value)}
            maxLength={300}
            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
          />
        </label>
        <p className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
          {t("page.groups.paymentCashTotal")}: <strong>{formatMoney(paymentGross, group.currency_code)}</strong>
        </p>
        <p className="mt-1 text-xs text-amber-800" role="note">
          {t("page.groups.paymentEstimateNotice")}
        </p>
        {paymentMethod === "cash" ? (
          <div className="mt-4">
            <CashTenderField
              amount={cashReceivedAmountInput}
              tipAmount={cashTipAmountInput}
              expectedAmount={paymentGross}
              currency={group.currency_code}
              label={t("page.form.cashReceived", { currency: group.currency_code })}
              hint={t("page.form.cashReceivedHint")}
              changeLabel={t("page.form.cashChange")}
              tipToggleLabel={t("page.form.cashTipToggle")}
              tipAmountLabel={t("page.form.cashTipAmount")}
              tipHint={t("page.form.cashTipHint")}
              invalidAmountMessage={t("page.form.cashReceivedInvalid")}
              insufficientMessage={t("page.form.cashReceivedInsufficient", { amount: formatMoney(paymentGross, group.currency_code) })}
              tipInvalidMessage={t("page.form.cashTipInvalid")}
              onChange={onCashReceivedAmountChange}
              onTipAmountChange={onCashTipAmountChange}
              testId="group-payment-cash-received"
              disabled={pending}
            />
          </div>
        ) : null}
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            disabled={pending}
            onClick={onClose}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50"
          >
            {t("page.common.close")}
          </button>
          <button
            type="button"
            onClick={() => void onSubmit()}
            disabled={pending || requestedCents === 0 || requestedCents !== allocatedCents || cashTenderInvalid || cashTipInvalid}
            className="rounded-lg bg-brand-700 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-800 disabled:opacity-50"
            data-testid="group-payment-submit"
          >
            {pending ? t("common:saving") : t("page.groups.paymentSubmit")}
          </button>
        </div>
      </section>
    </div>
  );
}
