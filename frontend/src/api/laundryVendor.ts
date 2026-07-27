import { apiFetch, type SessionLike } from "./client";
import type { DecimalValue } from "./stock";

// D2 (Via D lavanderia): client for the D1 backend -- see
// app/api/laundry_vendor.py for the exact request/response contracts this
// mirrors. A remito is a transfer between the hotel's own StockLocation and
// the vendor's dedicated one (created automatically with the vendor), not a
// new kind of business event.
export type RemitoDirection = "outbound" | "inbound";

export type LaundryVendor = {
  id: number;
  hotel_id: number;
  name: string;
  stock_location_id: number;
  contact_phone?: string | null;
  contact_email?: string | null;
  active: boolean;
  created_at: string;
};

export type LaundryVendorCreate = {
  name: string;
  contact_phone?: string | null;
  contact_email?: string | null;
  active?: boolean;
};

export type LaundryVendorUpdate = Partial<LaundryVendorCreate>;

export type LaundryVendorPrice = {
  id: number;
  vendor_id: number;
  stock_item_id: number;
  unit_price: DecimalValue;
  currency_code: string;
  updated_at: string;
};

export type LaundryVendorPriceUpsert = {
  stock_item_id: number;
  unit_price: DecimalValue;
  currency_code?: string | null;
};

export type LaundryRemitoLine = {
  id: number;
  stock_item_id: number;
  quantity: DecimalValue;
  unit_price_snapshot?: DecimalValue | null;
};

export type LaundryRemito = {
  id: number;
  hotel_id: number;
  vendor_id: number;
  direction: RemitoDirection;
  remito_number: string;
  remito_date: string;
  notes?: string | null;
  created_by_user_id?: number | null;
  created_at: string;
  lines: LaundryRemitoLine[];
};

export type LaundryRemitoLineCreate = {
  stock_item_id: number;
  quantity: DecimalValue;
};

export type LaundryRemitoCreate = {
  vendor_id: number;
  direction: RemitoDirection;
  remito_number: string;
  remito_date: string;
  house_location_id: number;
  lines: LaundryRemitoLineCreate[];
  notes?: string | null;
};

export type LaundryRemitoCreateResponse = {
  remito: LaundryRemito;
  warnings: string[];
};

export type LaundryVendorBalanceLine = {
  stock_item_id: number;
  stock_item_name: string;
  quantity: DecimalValue;
};

export type LaundryVendorSpendLine = {
  stock_item_id: number;
  stock_item_name: string;
  quantity: DecimalValue;
  subtotal: DecimalValue;
};

export type LaundryVendorSpend = {
  total: DecimalValue;
  by_item: LaundryVendorSpendLine[];
};

export const listLaundryVendors = (session?: SessionLike) =>
  apiFetch<LaundryVendor[]>("/api/laundry/vendors", { session });

export const createLaundryVendor = (payload: LaundryVendorCreate, session?: SessionLike) =>
  apiFetch<LaundryVendor>("/api/laundry/vendors", { method: "POST", data: payload, session });

export const updateLaundryVendor = (vendorId: number, payload: LaundryVendorUpdate, session?: SessionLike) =>
  apiFetch<LaundryVendor>(`/api/laundry/vendors/${vendorId}`, { method: "PATCH", data: payload, session });

export const listLaundryVendorPrices = (vendorId: number, session?: SessionLike) =>
  apiFetch<LaundryVendorPrice[]>(`/api/laundry/vendors/${vendorId}/prices`, { session });

export const setLaundryVendorPrice = (
  vendorId: number,
  payload: LaundryVendorPriceUpsert,
  session?: SessionLike
) =>
  apiFetch<LaundryVendorPrice>(`/api/laundry/vendors/${vendorId}/prices`, {
    method: "POST",
    data: payload,
    session
  });

export const createLaundryRemito = (payload: LaundryRemitoCreate, session?: SessionLike) =>
  apiFetch<LaundryRemitoCreateResponse>("/api/laundry/remitos", { method: "POST", data: payload, session });

export const listLaundryRemitos = (
  filters: { vendorId?: number; dateFrom?: string; dateTo?: string } = {},
  session?: SessionLike
) => {
  const params = new URLSearchParams();
  if (filters.vendorId) params.set("vendor_id", String(filters.vendorId));
  if (filters.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters.dateTo) params.set("date_to", filters.dateTo);
  const query = params.toString();
  return apiFetch<LaundryRemito[]>(`/api/laundry/remitos${query ? `?${query}` : ""}`, { session });
};

export const getLaundryVendorBalance = (vendorId: number, session?: SessionLike) =>
  apiFetch<LaundryVendorBalanceLine[]>(`/api/laundry/vendors/${vendorId}/balance`, { session });

// Wired by D3 (reporte de gasto), not consumed by the D2 remito/balance UI.
export const getLaundryVendorSpend = (
  vendorId: number,
  filters: { dateFrom?: string; dateTo?: string } = {},
  session?: SessionLike
) => {
  const params = new URLSearchParams();
  if (filters.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters.dateTo) params.set("date_to", filters.dateTo);
  const query = params.toString();
  return apiFetch<LaundryVendorSpend>(`/api/laundry/vendors/${vendorId}/spend${query ? `?${query}` : ""}`, {
    session
  });
};

// Liquidacion trimestral (owner's "cuanto anotamos vs cuanto factura el
// lavadero" cross-check). total_amount is computed server-side from each
// remito line's frozen unit_price_snapshot, never today's live vendor price
// -- see vendor_settlements in app/services/laundry_vendor_service.py.
export type LaundryVendorSettlementQuarter = {
  period_start: string;
  period_end: string;
  total_amount: DecimalValue;
  by_item: LaundryVendorSpendLine[];
  paid: boolean;
  paid_at?: string | null;
  notes?: string | null;
};

export const getLaundryVendorSettlements = (vendorId: number, year: number, session?: SessionLike) =>
  apiFetch<LaundryVendorSettlementQuarter[]>(`/api/laundry/vendors/${vendorId}/settlements?year=${year}`, {
    session
  });

export const markLaundryVendorSettlementPaid = (
  vendorId: number,
  periodStart: string,
  payload: { paid: boolean; notes?: string | null },
  session?: SessionLike
) =>
  apiFetch<LaundryVendorSettlementQuarter>(
    `/api/laundry/vendors/${vendorId}/settlements/${periodStart}/mark-paid`,
    { method: "POST", data: payload, session }
  );
