import { apiFetch, type SessionLike } from "./client";

export type HotelConfig = {
  id: number;
  hotel_name: string;
  hotel_timezone: string;
  check_in_time?: string | null;
  check_out_time?: string | null;
  default_currency: string;
  deposit_percentage: number;
  checkin_payment_policy: "deposit" | "total" | "free";
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
  enable_despegar_sync: boolean;
  allow_cancellation_after_checkin: boolean;
  languages: string[];
  jurisdiction_code: string;
  interface_language: string;
  allow_overbooking?: boolean;
  no_show_cutoff_hours?: number;
  manual_rate_min_adjustment_pct?: string | number | null;
  manual_rate_max_adjustment_pct?: string | number | null;
  require_document_for_checkin: boolean;
  require_terms_acceptance: boolean;
  extra_policies?: string | null;
  updated_at?: string | null;
};

export type HotelConfigUpdate = Partial<HotelConfig>;

export type HotelInterfaceLanguage = {
  interface_language: "es" | "en";
};

export const getHotelConfig = (session?: SessionLike) =>
  apiFetch<HotelConfig>("/api/config/", { session, method: "GET" });

export const getHotelInterfaceLanguage = (session?: SessionLike) =>
  apiFetch<HotelInterfaceLanguage>("/api/config/interface-language", { session, method: "GET" });

export const updateHotelConfig = (payload: HotelConfigUpdate, session?: SessionLike) =>
  apiFetch<HotelConfig>("/api/config/", { session, method: "PATCH", data: payload });
