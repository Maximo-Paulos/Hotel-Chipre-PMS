// Hotel-local "today" helpers. Never use `new Date().toISOString()` for a
// calendar date default -- toISOString() is always UTC, so any operator in
// a timezone behind UTC (e.g. Argentina, UTC-3) sees tomorrow's date instead
// of today's for several hours every night. These use the browser's local
// Date getters instead, which is the receptionist's own timezone -- the best
// client-side approximation of hotel-local time without a server round trip
// for hotel_timezone on every page.
const pad = (value: number) => String(value).padStart(2, "0");

const browserTimeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

const parseUtcTimestamp = (value: string | Date) => {
  if (value instanceof Date) return new Date(value.getTime());
  const normalized = /^\d{4}-\d{2}-\d{2}T/.test(value) && !/(?:Z|[+-]\d{2}(?::?\d{2})?)$/i.test(value)
    ? `${value}Z`
    : value;
  return new Date(normalized);
};

const normalizedTimeZone = (timeZone?: string | null) => {
  const requested = timeZone?.trim() || browserTimeZone();
  try {
    new Intl.DateTimeFormat("en", { timeZone: requested });
    return requested;
  } catch {
    return browserTimeZone();
  }
};

export const formatHotelDateTime = (
  value?: string | Date | null,
  timeZone?: string | null,
  locale = "es-AR"
) => {
  if (!value) return "-";
  const date = parseUtcTimestamp(value);
  if (Number.isNaN(date.getTime())) return "Fecha no disponible";
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "short",
    timeStyle: "medium",
    timeZone: normalizedTimeZone(timeZone),
    hourCycle: "h23"
  }).format(date);
};

export const formatHotelDate = (
  value?: string | Date | null,
  timeZone?: string | null,
  locale = "es-AR"
) => {
  if (!value) return "-";
  const date = parseUtcTimestamp(value);
  if (Number.isNaN(date.getTime())) return "Fecha no disponible";
  return new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: normalizedTimeZone(timeZone)
  }).format(date);
};

export const formatHotelTime = (
  value?: string | Date | null,
  timeZone?: string | null,
  locale = "es-AR"
) => {
  if (!value) return "-";
  const date = parseUtcTimestamp(value);
  if (Number.isNaN(date.getTime())) return "Fecha no disponible";
  return new Intl.DateTimeFormat(locale, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: normalizedTimeZone(timeZone),
    hourCycle: "h23"
  }).format(date);
};

export const formatLocalIsoDate = (value: Date) =>
  `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;

export const todayIso = () => formatLocalIsoDate(new Date());

/** Shift an ISO date (YYYY-MM-DD) by a number of days, returning ISO. */
export const addDaysIso = (iso: string, days: number) => {
  const base = new Date(`${iso}T00:00:00`);
  base.setDate(base.getDate() + days);
  return formatLocalIsoDate(base);
};

// Range presets shared by period reports (laundry spend D3, stock
// consumption D5) -- hotel-local, same reasoning as todayIso() above.
export const startOfCurrentWeekIso = () => {
  const now = new Date();
  const day = now.getDay();
  now.setDate(now.getDate() - (day === 0 ? 6 : day - 1));
  return formatLocalIsoDate(now);
};

export const startOfCurrentMonthIso = () => {
  const now = new Date();
  now.setDate(1);
  return formatLocalIsoDate(now);
};
