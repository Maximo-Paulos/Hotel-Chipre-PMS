import { apiFetch, type SessionLike } from "./client";

export type FxRateItem = {
  type:
    | "oficial"
    | "blue"
    | "eur"
    | "brl"
    | "clp"
    | "uyu"
    | "eur_blue"
    | "brl_blue"
    | "clp_blue"
    | "uyu_blue";
  nombre?: string | null;
  moneda?: string | null;
  casa?: string | null;
  compra?: number | null;
  venta?: number | null;
  fechaActualizacion?: string | null;
  quote_status?: "fresh" | "outage_fallback_24h" | "stale";
};

export type FxCurrencyCode = "ARS" | "USD" | "EUR" | "BRL" | "CLP" | "UYU";

export type FxConversionQuote = {
  from_currency: FxCurrencyCode;
  to_currency: FxCurrencyCode;
  rate: number;
  provider: "dolarapi.com";
  configured_market: "oficial" | "blue";
  quote_status: "fresh" | "outage_fallback_24h" | "not_required";
  warning_code: "fx.lastSuccessFallback24h" | null;
  quote_details: {
    uses_outage_fallback?: boolean;
    quote_status?: "fresh" | "outage_fallback_24h";
    warning_code?: "fx.lastSuccessFallback24h" | null;
    configured_usd_market?: "oficial" | "blue";
    configured_ars_to_usd_rate_side?: "compra" | "venta" | null;
    spread_pct?: number | null;
    fallback_used?: boolean;
    quote_observed_at?: string | null;
    source_updated_at?: string | null;
    target_updated_at?: string | null;
    source_quote?: {
      currency?: FxCurrencyCode;
      side?: "compra" | "venta";
      is_derived_blue?: boolean;
      provider_updated_at?: string | null;
      observed_at?: string | null;
      source?: string;
      fallback_used?: boolean;
    } | null;
    target_quote?: {
      currency?: FxCurrencyCode;
      side?: "compra" | "venta";
      is_derived_blue?: boolean;
      provider_updated_at?: string | null;
      observed_at?: string | null;
      source?: string;
      fallback_used?: boolean;
    } | null;
  } | null;
};

export type FxSnapshotResult = {
  stored: number;
  message: string;
  selected_market: "oficial" | "blue";
  selected_side: "compra" | "venta";
  applied_rate: number;
};

export const getFxRates = (session?: SessionLike) =>
  apiFetch<FxRateItem[]>("/fx/rates", { session, method: "GET" });

export const getFxConversionQuote = (
  from_currency: FxCurrencyCode,
  to_currency: FxCurrencyCode,
  session?: SessionLike
) => apiFetch<FxConversionQuote>("/fx/conversion-quote", {
  method: "POST",
  data: { from_currency, to_currency },
  session
});

export const createFxSnapshot = (session?: SessionLike) =>
  apiFetch<FxSnapshotResult>("/fx/snapshot", { method: "POST", session });
