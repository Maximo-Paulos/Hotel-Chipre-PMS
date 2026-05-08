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
