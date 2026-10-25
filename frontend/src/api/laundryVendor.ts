import { apiFetch, type SessionLike } from "./client";
import type { DecimalValue } from "./stock";

// D2 (Via D lavanderia): client for the D1 backend -- see
// app/api/laundry_vendor.py for the exact request/response contracts this
// mirrors. A remito is a transfer between the hotel's own LinenLocation and
// the vendor's dedicated one (created automatically with the vendor), not a
// new kind of business event. Linen items/locations are their own tables
// (see api/linen.ts), physically separate from general stock.
export type RemitoDirection = "outbound" | "inbound";

export type LaundryVendor = {
  id: number;
  hotel_id: number;
  name: string;
  linen_location_id: number;
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
  linen_item_id: number;
  unit_price: DecimalValue;
  effective_from: string;
  currency_code: string;
  updated_at: string;
};

export type LaundryVendorPriceUpsert = {
  linen_item_id: number;
  unit_price: DecimalValue;
  effective_from?: string;
  currency_code?: string | null;
};

export type LaundryRemitoLine = {
  id: number;
  linen_item_id: number;
  quantity: DecimalValue;
  missing_quantity?: DecimalValue;
  unit_price_snapshot?: DecimalValue | null;
};

export type LaundryRemito = {
  id: number;
  hotel_id: number;
  vendor_id: number;
  direction: RemitoDirection;
  house_location_id?: number | null;
  remito_number: string;
  remito_date: string;
  notes?: string | null;
  created_by_user_id?: number | null;
  created_by_name?: string | null;
  created_at: string;
  lines: LaundryRemitoLine[];
};

export type LaundryRemitoLineCreate = {
  linen_item_id: number;
  quantity: DecimalValue;
  missing_quantity?: DecimalValue;
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

export type LaundryMissingFollowUpStatus = "open" | "contacted" | "response_recorded" | "closed";

export type LaundryMissingFollowUp = {
  id: number;
  remito_id: number;
  remito_number: string;
  remito_date: string;
  vendor_id: number;
  vendor_name: string;
  linen_item_id: number;
  linen_item_name: string;
  quantity: DecimalValue;
  missing_quantity: DecimalValue;
  follow_up_status: LaundryMissingFollowUpStatus;
  follow_up_note?: string | null;
  supplier_reference?: string | null;
  supplier_contacted_on?: string | null;
  supplier_contact_note?: string | null;
  supplier_response_on?: string | null;
  supplier_response_note?: string | null;
  follow_up_updated_at?: string | null;
};

export type LaundryMissingFollowUpUpdate = Partial<
  Pick<
    LaundryMissingFollowUp,
    | "follow_up_status"
    | "follow_up_note"
    | "supplier_reference"
    | "supplier_contacted_on"
    | "supplier_contact_note"
    | "supplier_response_on"
    | "supplier_response_note"
  >
>;

export type LaundryDiscrepancyType = "excess_return" | "short_return";
export type LaundryDiscrepancyStatus =
  | "pending_approval"
  | "pending_identification"
  | "pending_review"
  | "pending_resolution"
  | "pending_claim"
  | "awaiting_replacement"
  | "resolved"
  | "return_to_laundry"
  | "returned_to_laundry";

export type LaundryDiscrepancy = {
  id: number;
  hotel_id: number;
  remito_id: number;
  remito_line_id: number;
  vendor_id: number;
  linen_item_id: number;
  discrepancy_type: LaundryDiscrepancyType;
  quantity: DecimalValue;
  remaining_quantity: DecimalValue;
  source_location_id: number;
  custody_location_id?: number | null;
  status: LaundryDiscrepancyStatus;
  created_by_user_id?: number | null;
  created_at: string;
  reviewed_by_user_id?: number | null;
  reviewed_at?: string | null;
  review_reason?: string | null;
  resolution_code?: string | null;
  resolution_reason?: string | null;
  resolution_amount?: DecimalValue | null;
  resolution_currency_code?: string | null;
  resolution_recorded_by_user_id?: number | null;
  resolution_recorded_at?: string | null;
  resolved_by_user_id?: number | null;
  resolved_at?: string | null;
  returned_by_user_id?: number | null;
  returned_at?: string | null;
  return_reason?: string | null;
};

export type LaundryDiscrepancyAction = { reason: string };
export type LaundryDiscrepancyResolution = LaundryDiscrepancyAction & {
  resolution_code: string;
  resolution_amount?: DecimalValue | null;
  resolution_currency_code?: string | null;
};

export type LaundryVendorBalanceLine = {
  linen_item_id: number;
  linen_item_name: string;
  quantity: DecimalValue;
};

export type LaundryVendorSpendLine = {
  linen_item_id: number;
  linen_item_name: string;
  quantity: DecimalValue;
  subtotal: DecimalValue;
  unpriced_quantity?: DecimalValue;
};

export type LaundryVendorSpend = {
  total: DecimalValue;
  unpriced_quantity?: DecimalValue;
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

export const listLaundryMissingFollowUps = (session?: SessionLike) =>
  apiFetch<LaundryMissingFollowUp[]>("/api/laundry/missing-follow-ups", { session });

export const updateLaundryMissingFollowUp = (
  remitoLineId: number,
  payload: LaundryMissingFollowUpUpdate,
  session?: SessionLike
) =>
  apiFetch<LaundryMissingFollowUp>(`/api/laundry/missing-follow-ups/${remitoLineId}`, {
    method: "PATCH",
    data: payload,
    session
  });

export const listLaundryDiscrepancies = (session?: SessionLike) =>
  apiFetch<LaundryDiscrepancy[]>("/api/laundry/discrepancies", { session });

export const approveLaundryDiscrepancy = (
  discrepancyId: number,
  payload: LaundryDiscrepancyAction,
  idempotencyKey: string,
  session?: SessionLike
) => apiFetch<LaundryDiscrepancy>(`/api/laundry/discrepancies/${discrepancyId}/approve`, {
  method: "POST",
  data: payload,
  headers: { "Idempotency-Key": idempotencyKey },
  session
});

export const resolveLaundryDiscrepancy = (
  discrepancyId: number,
  payload: LaundryDiscrepancyResolution,
  idempotencyKey: string,
  session?: SessionLike
) => apiFetch<LaundryDiscrepancy>(`/api/laundry/discrepancies/${discrepancyId}/resolve`, {
  method: "POST",
  data: payload,
  headers: { "Idempotency-Key": idempotencyKey },
  session
});

export const confirmLaundryDiscrepancyReturn = (
  discrepancyId: number,
  payload: LaundryDiscrepancyAction,
  idempotencyKey: string,
  session?: SessionLike
) => apiFetch<LaundryDiscrepancy>(
  `/api/laundry/discrepancies/${discrepancyId}/return-to-laundry`,
  {
    method: "POST",
    data: payload,
    headers: { "Idempotency-Key": idempotencyKey },
    session
  }
);

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
  unpriced_quantity?: DecimalValue;
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
