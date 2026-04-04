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
