import { apiFetch, type SessionLike } from "./client";

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
};

export type OperationalReservationGroup = {
  count: number;
  reservations: OperationalReservationSummary[];
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
  room_id?: number | null;
  room_block_id?: number | null;
  cash_session_id?: number | null;
};

export type DailyOperationalReport = {
  hotel_id: number;
  report_date: string;
  generated_at: string;
  arrivals: OperationalReservationGroup;
  departures: OperationalReservationGroup;
  pending_payments: OperationalReservationGroup;
  late_arrivals: OperationalReservationSummary[];
  available_with_review: AvailableWithReviewItem[];
  active_room_blocks: ActiveRoomBlockItem[];
  cash_session: CashSessionStatusRead;
  alerts: OperationalAlert[];
};

export type NightlyOperationalSummary = {
  hotel_id: number;
  report_date: string;
  generated_at: string;
  alert_count: number;
  pending_payment_count: number;
  late_arrival_count: number;
  available_with_review_count: number;
  active_room_block_count: number;
  cash_session_status: string;
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

export type RevenueReport = {
  start_date: string;
  end_date: string;
  collected: {
    total: number;
    by_method: Record<string, number>;
    by_day: Record<string, number>;
    transactions_count: number;
  };
  expected: {
    total: number;
    pending: number;
    reservations_count: number;
  };
};

export const getDailyOperationalReport = (reportDate: string, session?: SessionLike) =>
  apiFetch<DailyOperationalReport>(
    `/api/reports/operational/daily?report_date=${encodeURIComponent(reportDate)}`,
    { session }
  );

export const getOperationalAlerts = (reportDate: string, session?: SessionLike) =>
  apiFetch<NightlyOperationalSummary>(
    `/api/reports/operational/alerts?report_date=${encodeURIComponent(reportDate)}`,
    { session }
  );

export const getOccupancyReport = (startDate: string, endDate: string, session?: SessionLike) =>
  apiFetch<OccupancyReport>(
    `/api/reports/occupancy?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`,
    { session }
  );

export const getRevenueReport = (startDate: string, endDate: string, session?: SessionLike) =>
  apiFetch<RevenueReport>(
    `/api/reports/revenue?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`,
    { session }
  );
