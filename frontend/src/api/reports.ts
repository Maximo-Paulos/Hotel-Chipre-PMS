import { apiFetch, buildAuthHeaders, buildUrl, type SessionLike } from "./client";

export type OperationalReservationSummary = {
  reservation_id: number;
  confirmation_code: string;
  guest_id: number;
  guest_name?: string | null;
  room_id?: number | null;
  room_number?: string | null;
  status: string;
  check_in_date: string;
  check_out_date: string;
  total_amount?: number | null;
  amount_paid?: number | null;
  balance_due?: number | null;
  currency_code?: string | null;
  company_billing_deferred?: boolean;
  company_night_extra_due?: number | string | null;
};

export type OperationalReservationGroup = {
  count: number;
  reservations: OperationalReservationSummary[];
};

export type ArrivalCount = {
  report_date: string;
  count: number;
};

export type AvailableWithReviewItem = {
  reservation_id: number;
  confirmation_code: string;
  room_id?: number | null;
  room_number?: string | null;
  check_in_date: string;
  check_out_date: string;
  allocation_status: string;
};

export type ActiveRoomBlockItem = {
  room_block_id: number;
  room_id: number;
  room_number?: string | null;
  reason_code: string;
  reason_note?: string | null;
  starts_at: string;
  ends_at?: string | null;
  is_indefinite: boolean;
};

export type CashSessionStatusRead = {
  status: string;
  session_id?: number | null;
  opened_at?: string | null;
  opened_by_user_id?: number | null;
  currency_code?: string | null;
};

export type OperationalAlert = {
  code: string;
  severity: string;
  message: string;
  reservation_id?: number | null;
  amount?: CurrencyAmount | null;
  currency_code?: string | null;
  room_id?: number | null;
  room_block_id?: number | null;
  cash_session_id?: number | null;
};

export type DailyOperationalReport = {
  hotel_id: number;
  report_date: string;
  generated_at: string;
  arrivals: OperationalReservationGroup;
  no_shows: OperationalReservationGroup;
  departures: OperationalReservationGroup;
  pending_payments: OperationalReservationGroup;
  late_arrivals: OperationalReservationSummary[];
  available_with_review: AvailableWithReviewItem[];
  active_room_blocks: ActiveRoomBlockItem[];
  cash_session: CashSessionStatusRead;
  alerts: OperationalAlert[];
};

export type OccupancyReport = {
  start_date: string;
  end_date: string;
  total_rooms: number;
  average_occupancy: number;
  daily: Array<{
    date: string;
    occupied: number;
    available: number;
    rate: number;
  }>;
};

export type CurrencyAmount = number | string;

export type RevenueCurrencyTotal = {
  currency_code: string;
  gross_collected: CurrencyAmount;
  refunds: CurrencyAmount;
  net_collected: CurrencyAmount;
  transaction_count: number;
};

export type RevenueBreakdown = RevenueCurrencyTotal & {
  payment_method?: string | null;
  category_id?: string | null;
  category_name?: string | null;
  channel_code?: string | null;
  channel_label?: string | null;
};

export type RevenueReport = {
  start_date: string;
  end_date: string;
  timezone: string;
  receivables_as_of: string;
  collected: {
    currency_code?: string | null;
    total?: CurrencyAmount | null;
    by_method: Record<string, CurrencyAmount>;
    by_day: Record<string, CurrencyAmount>;
    by_currency: RevenueCurrencyTotal[];
    by_method_by_currency: RevenueBreakdown[];
    by_category: RevenueBreakdown[];
    by_channel: RevenueBreakdown[];
    by_day_by_currency: Array<{ date: string; currency_code: string; net_collected: CurrencyAmount }>;
    by_combination: RevenueBreakdown[];
    transactions_count: number;
  };
  expected: {
    total?: CurrencyAmount | null;
    pending?: CurrencyAmount | null;
    reservations_count: number;
    currency_code?: string | null;
    by_currency: Array<{
      currency_code: string;
      total: CurrencyAmount;
      pending: CurrencyAmount;
      reservations_count: number;
    }>;
  };
  booked_value: {
    total?: CurrencyAmount | null;
    currency_code?: string | null;
    by_currency: Array<{
      currency_code: string;
      amount: CurrencyAmount;
      reservation_count: number;
      booked_night_count: number;
    }>;
  };
  external_ota_collected: {
    by_currency: Array<{ currency_code: string; amount: CurrencyAmount }>;
    by_channel: Array<{ channel_code: string; currency_code: string; amount: CurrencyAmount }>;
    by_category: Array<{ category_name: string; currency_code: string; amount: CurrencyAmount }>;
    by_combination: Array<{
      channel_code: string;
      category_name: string;
      currency_code: string;
      amount: CurrencyAmount;
    }>;
  };
  receivables: {
    by_currency: Array<{
      currency_code: string;
      overdue: CurrencyAmount;
      due_at_check_in: CurrencyAmount;
      due_today_company_nights: CurrencyAmount;
      future: CurrencyAmount;
      total: CurrencyAmount;
    }>;
  };
};

export type BookedValueReport = {
  total: CurrencyAmount | null;
  currency_code: string | null;
  by_currency: Array<{
    currency_code: string;
    amount: CurrencyAmount;
    reservation_count: number;
    booked_night_count: number;
  }>;
};

export const getDailyOperationalReport = (reportDate: string, session?: SessionLike, signal?: AbortSignal) =>
  apiFetch<DailyOperationalReport>(
    `/api/reports/operational/daily?report_date=${encodeURIComponent(reportDate)}`,
    { session, signal }
  );

export const getTodayArrivalCount = (session?: SessionLike, signal?: AbortSignal) =>
  apiFetch<ArrivalCount>("/api/reports/operational/arrivals/count", { session, signal });

export const getOccupancyReport = (startDate: string, endDate: string, session?: SessionLike, signal?: AbortSignal) =>
  apiFetch<OccupancyReport>(
    `/api/reports/occupancy?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`,
    { session, signal }
  );

export const getRevenueReport = (startDate: string, endDate: string, session?: SessionLike, signal?: AbortSignal) =>
  apiFetch<RevenueReport>(
    `/api/reports/revenue?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`,
    { session, signal }
  );

export const getBookedValueReport = (startDate: string, endDate: string, session?: SessionLike, signal?: AbortSignal) =>
  apiFetch<BookedValueReport>(
    `/api/reports/booked-value?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`,
    { session, signal }
  );

export const downloadRevenueReportCsv = async (
  startDate: string,
  endDate: string,
  session?: SessionLike
): Promise<Blob> => {
  const query = new URLSearchParams({ start_date: startDate, end_date: endDate });
  const response = await fetch(buildUrl(`/api/reports/revenue/export.csv?${query.toString()}`), {
    headers: buildAuthHeaders(session),
    credentials: "include"
  });
  if (!response.ok) {
    let message = response.statusText || "No se pudo exportar el reporte financiero";
    try {
      const payload = await response.json() as { detail?: string };
      message = payload.detail || message;
    } catch {
      // Keep a safe HTTP status message when the provider returns non-JSON.
    }
    throw new Error(message);
  }
  return response.blob();
};
