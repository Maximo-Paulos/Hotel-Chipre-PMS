import { useTranslation } from "react-i18next";

import type { PaymentSurchargeQuote } from "../api/paymentSurcharges";
import { interfaceLanguageToLocale } from "../i18n";
import { formatFxRate, formatMoneyExact } from "../utils/currency";

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
  const { t, i18n } = useTranslation("reservations");
  const locale = interfaceLanguageToLocale(i18n.resolvedLanguage ?? i18n.language);
  const currency = quote.currency_code.toUpperCase();
  const reservationCurrency = quote.reservation_currency_code.toUpperCase();
  const fxRate = quote.fx_rate_snapshot == null ? null : Number(quote.fx_rate_snapshot);
  const cashChangeCurrency = quote.cash_change_currency_code?.toUpperCase() ?? reservationCurrency;
  const cashChangeFxRate = quote.cash_change_fx_rate == null ? null : Number(quote.cash_change_fx_rate);
  const fxRateLabel = currency !== reservationCurrency && fxRate !== null
    ? formatFxRate(reservationCurrency, currency, fxRate, i18n.language)
    : null;
  const cashChangeFxRateLabel = currency !== cashChangeCurrency &&
    cashChangeFxRate !== null && cashChangeFxRate > 0
    ? formatFxRate(currency, cashChangeCurrency, cashChangeFxRate, i18n.language)
    : null;
  const suggestion = quote.cash_tender_suggestion === null ? null : Number(quote.cash_tender_suggestion);
  const hasCashSuggestion = showCashSuggestion && suggestion !== null &&
    Math.abs(suggestion - Number(quote.final_amount)) >= 0.005;
  const fxSource = detailLabel(quote.fx_quote_details);
  const surchargeFxSource = detailLabel(quote.surcharge_fx_quote_details);
  const fallbackDetails = [quote.fx_quote_details, quote.surcharge_fx_quote_details].find(
    (details) => details?.fallback_used === true
  );
  const observedAt = typeof fallbackDetails?.quote_observed_at === "string"
    ? new Date(fallbackDetails.quote_observed_at).toLocaleString()
    : null;

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
          <dd className="font-medium">{formatMoneyExact(quote.base_amount, currency, locale)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>{t("page.form.paymentQuoteSurcharge")}</dt>
          <dd className="font-medium">{formatMoneyExact(quote.surcharge_amount, currency, locale)}</dd>
        </div>
        <div className="flex justify-between gap-2 sm:col-span-2">
          <dt className="font-semibold">{t("page.form.paymentQuoteTotal", { currency })}</dt>
          <dd className="font-semibold">{formatMoneyExact(quote.final_amount, currency, locale)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>{t("page.form.paymentQuoteApplied")}</dt>
          <dd>{formatMoneyExact(quote.applied_amount, reservationCurrency, locale)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>{t("page.form.paymentQuoteRemaining")}</dt>
          <dd>{formatMoneyExact(quote.remaining_balance, reservationCurrency, locale)}</dd>
        </div>
      </dl>
      {fxRateLabel && Number(quote.remaining_balance) > 0 ? (
        <p className="mt-1" data-testid="payment-quote-minor-unit-remainder">
          {t("page.form.paymentQuoteMinorUnitRemainder")}
        </p>
      ) : null}
      {fxRateLabel ? (
        <p className="mt-1" data-testid="payment-quote-fx-rate">
          {t("page.form.paymentQuoteFxRate", {
            rate: fxRateLabel
          })}
          {fxSource ? ` · ${fxSource}` : ""}
        </p>
      ) : null}
      {quote.payment_method === "cash" && currency !== cashChangeCurrency ? (
        cashChangeFxRateLabel ? (
          <p className="mt-1" data-testid="payment-quote-cash-change-rate">
            {t("page.form.paymentQuoteCashChangeFxRate", { rate: cashChangeFxRateLabel })}
          </p>
        ) : (
          <p className="mt-1 text-amber-900" role="status" data-testid="payment-quote-cash-change-unavailable">
            {t("page.form.cashChangeRateUnavailable", { currency: cashChangeCurrency })}
          </p>
        )
      ) : null}
      {quote.manual_fx_quote_id ? (
        <p className="mt-2 rounded border border-amber-300 bg-amber-50 p-2 font-medium text-amber-950" role="status" data-testid="payment-quote-manual-fx">
          {t("page.form.manualFxApprovedNotice", {
            reason: quote.manual_fx_reason ?? "",
            date: quote.manual_fx_created_at ? new Date(quote.manual_fx_created_at).toLocaleString() : ""
          })}
        </p>
      ) : null}
      {surchargeFxSource ? (
        <p className="mt-1">{t("page.form.paymentQuoteSurchargeFx", { source: surchargeFxSource })}</p>
      ) : null}
      {fallbackDetails ? (
        <p className="mt-2 rounded border border-amber-300 bg-amber-50 p-2 font-medium text-amber-950" role="alert" data-testid="payment-quote-fx-fallback">
          {t("page.form.paymentQuoteFxFallback", { date: observedAt ?? t("page.form.usdEstimateUnknownDate") })}
        </p>
      ) : null}
      {hasCashSuggestion ? (
        <p className="mt-1 rounded border border-violet-200 bg-violet-50 p-2 text-violet-950">
          {t("page.form.paymentQuoteCashSuggestion", {
            amount: formatMoneyExact(suggestion, currency, locale),
            exact: formatMoneyExact(quote.final_amount, currency, locale)
          })}
        </p>
      ) : null}
      <p className="mt-1 text-sky-900">{t("page.form.paymentQuoteSnapshot")}</p>
    </section>
  );
}
