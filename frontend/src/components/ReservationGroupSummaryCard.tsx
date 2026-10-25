import { useTranslation } from "react-i18next";

import type { ReservationGroupSummary } from "../api/reservations";
import { formatMoney } from "../utils/currency";

export type ReservationGroupSummaryCardProps = {
  group: ReservationGroupSummary;
  deferredBilling: boolean;
  showPaymentAction: boolean;
  paymentActionDisabled: boolean;
  onRegisterPayment: () => void;
};

export function ReservationGroupSummaryCard({
  group,
  deferredBilling,
  showPaymentAction,
  paymentActionDisabled,
  onRegisterPayment
}: ReservationGroupSummaryCardProps) {
  const { t } = useTranslation("reservations");

  return (
    <article
      data-testid={`reservation-group-summary-${group.id}`}
      className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-slate-900">{group.guest_name}</p>
          {group.company_name && <p className="text-xs text-slate-600">{group.company_name}</p>}
        </div>
        <span className="rounded-full bg-brand-100 px-2 py-1 text-xs font-semibold text-brand-800">
          {t("page.groups.rooms", { count: group.reservation_count })}
        </span>
      </div>
      <p className="mt-2 text-xs text-slate-600">
        {group.check_in_date} → {group.check_out_date} · {group.reservation_codes.join(", ")}
      </p>
      {deferredBilling ? (
        <p className="mt-3 text-xs text-amber-900">{t("page.groups.deferredCompanyBilling")}</p>
      ) : (
        <dl className="mt-3 grid grid-cols-3 gap-2 text-xs">
          <div>
            <dt className="text-slate-500">{t("page.groups.total")}</dt>
            <dd className="font-semibold">{formatMoney(group.total_amount, group.currency_code)}</dd>
          </div>
          <div>
            <dt className="text-slate-500">{t("page.groups.paid")}</dt>
            <dd className="font-semibold">{formatMoney(group.amount_paid, group.currency_code)}</dd>
          </div>
          <div>
            <dt className="text-slate-500">{t("page.groups.balance")}</dt>
            <dd className="font-semibold">{formatMoney(group.balance_due, group.currency_code)}</dd>
          </div>
        </dl>
      )}
      {showPaymentAction && (
        <button
          type="button"
          onClick={onRegisterPayment}
          disabled={paymentActionDisabled}
          className="mt-3 rounded-lg bg-brand-700 px-3 py-2 text-xs font-semibold text-white hover:bg-brand-800 disabled:opacity-50"
          data-testid={`reservation-group-payment-${group.id}`}
        >
          {t("page.groups.registerPayment")}
        </button>
      )}
    </article>
  );
}
