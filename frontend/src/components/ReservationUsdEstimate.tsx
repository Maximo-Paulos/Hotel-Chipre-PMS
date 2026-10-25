import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { ApiError, hasValidSession } from "../api/client";
import { getFxConversionQuote } from "../api/fxRates";
import { useEffectivePermissions } from "../hooks/usePermissions";
import { useSession } from "../state/session";
import { formatMoney } from "../utils/currency";

type Props = {
  amount: number;
};

export default function ReservationUsdEstimate({ amount }: Props) {
  const { t, i18n } = useTranslation("reservations");
  const { session } = useSession();
  const { hasPermission } = useEffectivePermissions();
  const canViewEstimate = hasPermission("cash:operate");
  const fxQuoteQuery = useQuery({
    queryKey: ["reservation-usd-fx-quote", session.hotelId ?? null, "ARS", "USD"],
    queryFn: () => getFxConversionQuote("ARS", "USD", session),
    enabled: Boolean(canViewEstimate && hasValidSession(session)),
    staleTime: 30_000,
    retry: false
  });
  const estimate = useMemo(() => {
    const rate = Number(fxQuoteQuery.data?.rate);
    if (!Number.isFinite(amount) || !Number.isFinite(rate) || rate <= 0) {
      return null;
    }
    const convertedAmount = amount * rate;
    return Number.isFinite(convertedAmount)
      ? Math.round((convertedAmount + Number.EPSILON) * 100) / 100
      : null;
  }, [amount, fxQuoteQuery.data?.rate]);

  const fxDetails = fxQuoteQuery.data?.quote_details;
  const fxSide = fxDetails?.configured_ars_to_usd_rate_side ?? fxDetails?.target_quote?.side;
  const fxSideLabel = fxSide
    ? t(fxSide === "compra" ? "page.form.usdEstimateBuySide" : "page.form.usdEstimateSellSide")
    : null;
  const fxMarketLabel = fxQuoteQuery.data
    ? t(fxQuoteQuery.data.configured_market === "blue"
        ? "page.form.usdEstimateBlueMarket"
        : "page.form.usdEstimateOfficialMarket")
    : null;
  const fxRateLabel = fxQuoteQuery.data?.rate.toLocaleString(
    i18n.language === "en" ? "en-US" : "es-AR",
    { maximumFractionDigits: 8 }
  );
  const fxSpreadLabel = fxDetails?.spread_pct == null
    ? null
    : fxDetails.spread_pct.toLocaleString(
        i18n.language === "en" ? "en-US" : "es-AR",
        { maximumFractionDigits: 2 }
      );
  const statusMessage = !canViewEstimate
    ? t("page.form.usdEstimatePermissionDenied")
    : fxQuoteQuery.isError
      ? fxQuoteQuery.error instanceof ApiError && fxQuoteQuery.error.status === 403
        ? t("page.form.usdEstimatePermissionDenied")
        : t("page.form.usdEstimateUnavailable")
      : fxQuoteQuery.isFetching || !fxQuoteQuery.data
        ? t("page.form.usdEstimateLoading")
        : estimate === null
          ? t("page.form.usdEstimateUnavailable")
          : null;

  return (
    <div
      className="mt-3 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-950"
      data-testid="reservation-usd-estimate"
      aria-live="polite"
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-sky-800">
        {t("page.form.usdEstimateTitle")}
      </p>
      <p className="mt-1 text-base font-semibold" data-testid="reservation-usd-estimate-value">
        {statusMessage ?? formatMoney(estimate, "USD")}
      </p>
      {statusMessage === null && fxQuoteQuery.data ? (
        <p className="mt-1 text-xs text-sky-900">
          {t("page.form.usdEstimateRate", { rate: fxRateLabel, market: fxMarketLabel })}
          {fxSideLabel ? t("page.form.usdEstimateSide", { side: fxSideLabel }) : ""}
          {fxSpreadLabel !== null ? t("page.form.usdEstimateSpread", { spread: fxSpreadLabel }) : ""}
        </p>
      ) : null}
      <p className="mt-1 text-xs text-sky-900">{t("page.form.usdEstimateDisclaimer")}</p>
    </div>
  );
}
