import { apiFetch, type SessionLike } from "./client";

export type HotelConfig = {
  id: number;
  hotel_name: string;
  hotel_timezone: string;
  default_currency: string;
  deposit_percentage: number;
  free_cancellation_hours: number;
  cancellation_penalty_percentage: number;
  enable_full_payment: boolean;
  enable_deposit_payment: boolean;
  enable_cash: boolean;
  enable_mercado_pago: boolean;
  enable_paypal: boolean;
  enable_credit_card: boolean;
  enable_debit_card: boolean;
  enable_bank_transfer: boolean;
  enable_booking_sync: boolean;
  enable_expedia_sync: boolean;
  allow_cancellation_after_checkin: boolean;
  receptionist_view_past_days?: number;
  receptionist_view_future_days?: number;
  allow_revenue_manager?: boolean;
  allow_revenue_receptionist?: boolean;
  sync_interval_minutes?: number;
  safety_buffer_rooms?: number;
  allow_overbooking?: boolean;
  max_overallocation_pct?: number;
  no_show_cutoff_hours?: number;
  ota_autopush_enabled?: boolean;
  card_validation_enabled?: boolean;
  payment_retry_attempts?: number;
  auth_amount_pct?: number;
  stop_sell_channels?: string | null;
  event_notifications?: string | null;
  require_document_for_checkin: boolean;
  require_terms_acceptance: boolean;
  extra_policies?: string | null;
  updated_at?: string | null;
};

export type HotelConfigUpdate = Partial<HotelConfig>;

export const getHotelConfig = (session?: SessionLike) =>
  apiFetch<HotelConfig>("/api/config/", { session, method: "GET" });

export const updateHotelConfig = (payload: HotelConfigUpdate, session?: SessionLike) =>
  apiFetch<HotelConfig>("/api/config/", { session, method: "PATCH", data: payload });
