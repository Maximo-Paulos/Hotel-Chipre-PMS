const formatterCache = new Map<string, Intl.NumberFormat>();
const exactFormatterCache = new Map<string, Intl.NumberFormat>();

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

function getExactFormatter(locale: string, currencyCode?: string | null): Intl.NumberFormat {
  const normalized = normalizeCurrencyCode(currencyCode);
  const cacheKey = `${locale}:${normalized}`;
  const cached = exactFormatterCache.get(cacheKey);
  if (cached) {
    return cached;
  }

  let formatter: Intl.NumberFormat;
  try {
    formatter = new Intl.NumberFormat(locale, {
      style: "currency",
      currency: normalized,
    });
  } catch {
    formatter = new Intl.NumberFormat(locale, {
      style: "currency",
      currency: "ARS",
    });
  }
  exactFormatterCache.set(cacheKey, formatter);
  return formatter;
}

export function formatMoney(amount: number | string | null | undefined, currencyCode?: string | null, locale = "es-AR"): string {
  const numericAmount = Number(amount);
  const safeAmount = Number.isFinite(numericAmount) ? numericAmount : 0;
  return getFormatter(locale, currencyCode).format(safeAmount);
}

export function formatMoneyExact(
  amount: number | string | null | undefined,
  currencyCode?: string | null,
  locale = "es-AR",
): string {
  const numericAmount = Number(amount);
  const safeAmount = Number.isFinite(numericAmount) ? numericAmount : 0;
  return getExactFormatter(locale, currencyCode).format(safeAmount);
}

export function formatFxRate(
  fromCurrency: string,
  toCurrency: string,
  rate: number | string | null | undefined,
  locale = "es-AR",
): string | null {
  const numericRate = Number(rate);
  if (!Number.isFinite(numericRate) || numericRate <= 0) return null;

  const from = normalizeCurrencyCode(fromCurrency);
  const to = normalizeCurrencyCode(toCurrency);
  const baseCurrency = to === "USD" && from !== "USD" ? "USD" : from;
  const quoteCurrency = baseCurrency === "USD" && to === "USD" ? from : to;
  const quoteRate = baseCurrency === "USD" && from !== "USD" ? 1 / numericRate : numericRate;

  if (!Number.isFinite(quoteRate) || quoteRate <= 0) return null;

  const numberLocale = locale.toLowerCase().startsWith("en")
    ? "en-US"
    : locale.toLowerCase().startsWith("es")
      ? "es-AR"
      : locale;
  const formattedRate = new Intl.NumberFormat(numberLocale, {
    maximumFractionDigits: 6,
  }).format(quoteRate);

  return `1 ${baseCurrency} = ${formattedRate} ${quoteCurrency}`;
}

export function resolveSingleCurrencyCode(
  currencyCodes: Array<string | null | undefined>,
): string | null {
  const uniqueCodes = [...new Set(currencyCodes.map((code) => normalizeCurrencyCode(code)))];
  return uniqueCodes.length === 1 ? uniqueCodes[0] : null;
}
