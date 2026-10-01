import { apiFetch, type SessionLike } from "./client";

export type FxRateItem = {
  type: "oficial" | "blue" | "eur" | "brl" | "clp" | "uyu";
  nombre?: string | null;
  moneda?: string | null;
  casa?: string | null;
  compra?: number | null;
  venta?: number | null;
  fechaActualizacion?: string | null;
};

export const getFxRates = (session?: SessionLike) =>
  apiFetch<FxRateItem[]>("/fx/rates", { session, method: "GET" });
