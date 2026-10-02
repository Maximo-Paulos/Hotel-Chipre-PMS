import { apiFetch, type SessionLike } from "./client";

export type RateCalendarChannelPrice = {
  rate_plan_id: number;
  rate_plan_code: string;
  rate_plan_name: string;
  base_amount: number;
  sales_channel_code?: string | null;
  currency_code: string;
};

export type RateCalendarChannelRestrictions = {
  min_stay: number | null;
  max_stay: number | null;
  closed_to_arrival: boolean;
  closed_to_departure: boolean;
  allotment: number | null;
  stop_sell: boolean;
};

export type RateCalendarChannelDay = {
  provider_code: "direct" | "booking" | "expedia" | string;
  provider_label: string;
  currency_code: string;
  missing_mapping: boolean;
  prices: RateCalendarChannelPrice[];
  restrictions: RateCalendarChannelRestrictions;
};

export type RateCalendarDay = {
  date: string;
  is_today: boolean;
  total_rooms: number;
  reserved: number;
  blocked: number;
  for_sale: number;
  status: "open" | "closed";
  occupancy_pct: number;
  channels: RateCalendarChannelDay[];
};

export type RateCalendarMeta = {
  category_id: number;
  category_name: string;
  category_code: string;
  total_rooms: number;
  hotel_currency_code: string;
  date_from: string;
  date_to: string;
};

export type RateCalendarResponse = {
  meta: RateCalendarMeta;
  days: RateCalendarDay[];
};

export type GetRateCalendarDailyParams = {
  categoryId: number;
  dateFrom: string;
  dateTo: string;
};

export const getRateCalendarDaily = (
  { categoryId, dateFrom, dateTo }: GetRateCalendarDailyParams,
  session?: SessionLike
) => {
  const search = new URLSearchParams({
    category_id: String(categoryId),
    date_from: dateFrom,
    date_to: dateTo
  });

  return apiFetch<RateCalendarResponse>(`/api/rate-calendar/daily?${search.toString()}`, {
    method: "GET",
    session
  });
};

// ── Daily rate editing (maps to backend /api/rates/...) ──

export type DailyRatePrices = {
  price: number;
  price_cash?: number | null;
  price_transfer?: number | null;
  price_mercadopago?: number | null;
  price_paypal?: number | null;
  price_credit_card?: number | null;
};

export type RatePaymentMethodOptions = {
  enable_cash: boolean;
  enable_bank_transfer: boolean;
  enable_debit_card: boolean;
  enable_credit_card: boolean;
  enable_mercado_pago: boolean;
  enable_paypal: boolean;
};

export const getRatePaymentMethodOptions = (session?: SessionLike) =>
  apiFetch<RatePaymentMethodOptions>("/api/rates/payment-method-options", { method: "GET", session });

// One row per date for the editable grid. `source` says where the effective
// price came from (an explicit daily_rate, a price_period, the category base,
// or none), and `daily_rate_id` is set only when an explicit row exists.
export type DailyRateRangeRow = DailyRatePrices & {
  date: string;
  source: "daily_rate" | "price_period" | "category_base" | "none";
  daily_rate_id: number | null;
};

export const getCategoryDailyRates = (
  categoryId: number,
  fromDate: string,
  toDate: string,
  session?: SessionLike
) => {
  const search = new URLSearchParams({ from_date: fromDate, to_date: toDate });
  return apiFetch<DailyRateRangeRow[]>(`/api/rates/category/${categoryId}?${search.toString()}`, {
    method: "GET",
    session
  });
};

export type PricePeriod = {
  id: number;
  hotel_id: number;
  category_id: number;
  name: string;
  start_date: string;
  end_date: string;
  price_per_night: number;
  price_cash?: number | null;
  price_transfer?: number | null;
  price_mercadopago?: number | null;
  price_paypal?: number | null;
  price_credit_card?: number | null;
  price_debit_card?: number | null;
  price_booking?: number | null;
  price_expedia?: number | null;
  priority: number;
  is_active: boolean;
  created_at: string;
};

export type PricePeriodInput = Omit<Pick<PricePeriod, "category_id" | "name" | "start_date" | "end_date" | "price_per_night" | "price_cash" | "price_transfer" | "price_mercadopago" | "price_paypal" | "price_credit_card" | "price_debit_card" | "price_booking" | "price_expedia" | "priority" | "is_active">, "category_id"> & {
  category_id: number;
};

export const listPricePeriods = (categoryId: number, session?: SessionLike) => {
  const search = new URLSearchParams({ category_id: String(categoryId), active_only: "false" });
  return apiFetch<PricePeriod[]>(`/api/rates/periods?${search.toString()}`, { session });
};
