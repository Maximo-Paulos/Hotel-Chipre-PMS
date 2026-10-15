import { formatMoney } from "./currency";

type AnalyticsValueLabels = Record<string, Record<string, string> | undefined>;

export function formatAnalyticsTableValue(
  value: unknown,
  key = "",
  row?: Record<string, unknown>,
  unavailableCurrencyLabel = "No disponible",
  valueLabels: AnalyticsValueLabels = {}
): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Sí" : "No";

  const currency = /_(ars|usd)$/.exec(key)?.[1];
  if (currency && value !== "" && Number.isFinite(Number(value))) {
    const requestedCurrency = currency.toUpperCase();
    const hasUnavailableCurrencyMetadata = Array.isArray(row?.unavailable_currencies);
    const unavailableCurrencies = hasUnavailableCurrencyMetadata
      ? (row.unavailable_currencies as unknown[]).map((item) => String(item).toUpperCase())
      : [];
    if (unavailableCurrencies.includes(requestedCurrency)) return unavailableCurrencyLabel;

    const explicitAvailabilityKey = `${key}_available`;
    const explicitAvailability = row?.[explicitAvailabilityKey];
    if (typeof explicitAvailability === "boolean" && !explicitAvailability) return unavailableCurrencyLabel;

    // Backend availability metadata is authoritative for aggregated money.
    // The source-currency fallback is only for older responses without it.
    if (!hasUnavailableCurrencyMetadata && typeof explicitAvailability !== "boolean") {
      const sourceCurrency = typeof row?.source_currency === "string" ? row.source_currency.toUpperCase() : null;
      const fxRate = Number(row?.fx_rate_snapshot);
      if (
        (sourceCurrency !== requestedCurrency || !sourceCurrency) &&
        (!Number.isFinite(fxRate) || fxRate <= 0)
      ) {
        return unavailableCurrencyLabel;
      }
    }
    return formatMoney(Number(value), requestedCurrency);
  }

  if (typeof value === "number") return String(value);
  if (typeof value === "string") return valueLabels[key]?.[value] ?? value;
  if (Array.isArray(value)) return `${value.length} items`;
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
