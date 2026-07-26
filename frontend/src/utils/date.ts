// Hotel-local "today" helpers. Never use `new Date().toISOString()` for a
// calendar date default -- toISOString() is always UTC, so any operator in
// a timezone behind UTC (e.g. Argentina, UTC-3) sees tomorrow's date instead
// of today's for several hours every night. These use the browser's local
// Date getters instead, which is the receptionist's own timezone -- the best
// client-side approximation of hotel-local time without a server round trip
// for hotel_timezone on every page.
const pad = (value: number) => String(value).padStart(2, "0");

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
