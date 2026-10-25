import { useTranslation } from "react-i18next";

import type { PaymentSurchargeQuote } from "../api/paymentSurcharges";
import { formatMoney } from "../utils/currency";

type PaymentQuoteSummaryProps = {
  quote: PaymentSurchargeQuote;
  showCashSuggestion?: boolean;
};

const detailLabel = (details: Record<string, unknown> | null): string | null => {
  if (!details) return null;
  for (const key of ["source", "provider", "market"]) {
    const value = details[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return null;
};

export function PaymentQuoteSummary({ quote, showCashSuggestion = false }: PaymentQuoteSummaryProps) {
  const { t } = useTranslation("reservations");
  const currency = quote.currency_code.toUpperCase();
  const reservationCurrency = quote.reservation_currency_code.toUpperCase();
  const fxRate = quote.fx_rate_snapshot === null ? null : Number(quote.fx_rate_snapshot);
  const suggestion = quote.cash_tender_suggestion === null ? null : Number(quote.cash_tender_suggestion);
  const hasCashSuggestion = showCashSuggestion && suggestion !== null &&
    Math.abs(suggestion - Number(quote.final_amount)) >= 0.005;
  const fxSource = detailLabel(quote.fx_quote_details);
  const surchargeFxSource = detailLabel(quote.surcharge_fx_quote_details);

  return (
    <section
      className="rounded border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-950"
      aria-label={t("page.form.paymentQuoteTitle")}
      role="status"
      data-testid="payment-backend-quote"
    >
      <p className="font-semibold">{t("page.form.paymentQuoteTitle")}</p>
      <dl className="mt-1 grid gap-x-3 gap-y-1 sm:grid-cols-2">
        <div className="flex justify-between gap-2">
          <dt>{t("page.form.paymentQuoteBase")}</dt>
          <dd className="font-medium">{formatMoney(quote.base_amount, currency)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>{t("page.form.paymentQuoteSurcharge")}</dt>
          <dd className="font-medium">{formatMoney(quote.surcharge_amount, currency)}</dd>
        </div>
        <div className="flex justify-between gap-2 sm:col-span-2">
          <dt className="font-semibold">{t("page.form.paymentQuoteTotal", { currency })}</dt>
          <dd className="font-semibold">{formatMoney(quote.final_amount, currency)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>{t("page.form.paymentQuoteApplied")}</dt>
          <dd>{formatMoney(quote.applied_amount, reservationCurrency)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>{t("page.form.paymentQuoteRemaining")}</dt>
          <dd>{formatMoney(quote.remaining_balance, reservationCurrency)}</dd>
        </div>
      </dl>
      {currency !== reservationCurrency && fxRate !== null && Number.isFinite(fxRate) ? (
        <p className="mt-1">
          {t("page.form.paymentQuoteFxRate", {
            fromCurrency: reservationCurrency,
            rate: fxRate.toLocaleString(undefined, { maximumFractionDigits: 8 }),
            toCurrency: currency
          })}
          {fxSource ? ` · ${fxSource}` : ""}
        </p>
      ) : null}
      {surchargeFxSource ? (
        <p className="mt-1">{t("page.form.paymentQuoteSurchargeFx", { source: surchargeFxSource })}</p>
      ) : null}
      {hasCashSuggestion ? (
        <p className="mt-1 rounded border border-violet-200 bg-violet-50 p-2 text-violet-950">
          {t("page.form.paymentQuoteCashSuggestion", {
            amount: formatMoney(suggestion, currency),
            exact: formatMoney(quote.final_amount, currency)
          })}
        </p>
      ) : null}
      <p className="mt-1 text-sky-900">{t("page.form.paymentQuoteSnapshot")}</p>
    </section>
  );
}
