const formatterCache = new Map<string, Intl.NumberFormat>();

export function normalizeCurrencyCode(currencyCode?: string | null): string {
  const candidate = (currencyCode || "ARS").trim().toUpperCase();
  return candidate || "ARS";
}

function getFormatter(locale: string, currencyCode?: string | null): Intl.NumberFormat {
  const normalized = normalizeCurrencyCode(currencyCode);
  const cacheKey = `${locale}:${normalized}`;
  const cached = formatterCache.get(cacheKey);
  if (cached) {
    return cached;
  }

  let formatter: Intl.NumberFormat;
  try {
    formatter = new Intl.NumberFormat(locale, {
      style: "currency",
      currency: normalized,
      maximumFractionDigits: 0,
    });
  } catch {
    formatter = new Intl.NumberFormat(locale, {
      style: "currency",
      currency: "ARS",
      maximumFractionDigits: 0,
    });
  }
  formatterCache.set(cacheKey, formatter);
  return formatter;
}

export function formatMoney(amount: number | null | undefined, currencyCode?: string | null, locale = "es-AR"): string {
  const numericAmount = typeof amount === "number" && Number.isFinite(amount) ? amount : 0;
  return getFormatter(locale, currencyCode).format(numericAmount);
}

export function resolveSingleCurrencyCode(
  currencyCodes: Array<string | null | undefined>,
): string | null {
  const uniqueCodes = [...new Set(currencyCodes.map((code) => normalizeCurrencyCode(code)))];
  return uniqueCodes.length === 1 ? uniqueCodes[0] : null;
}
