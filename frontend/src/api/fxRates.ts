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
};

export type FxCurrencyCode = "ARS" | "USD" | "EUR" | "BRL" | "CLP" | "UYU";

export type FxConversionQuote = {
  from_currency: FxCurrencyCode;
  to_currency: FxCurrencyCode;
  rate: number;
  provider: "dolarapi.com";
  configured_market: "oficial" | "blue";
  quote_details: {
    configured_usd_market?: "oficial" | "blue";
    source_updated_at?: string | null;
    target_updated_at?: string | null;
    source_quote?: { is_derived_blue?: boolean; provider_updated_at?: string | null } | null;
    target_quote?: { is_derived_blue?: boolean; provider_updated_at?: string | null } | null;
  } | null;
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
