import { apiFetch, type SessionLike } from "./client";
import type { DecimalValue, StockMovementType } from "./stock";

// D (stock/lavanderia separation, real split): ropa blanca vive en su propia
// tabla (linen_items/linen_locations/linen_movements, ver
// app/models/linen.py) -- NO en stock_items/stock_locations/stock_movements
// (que ahora son insumos generales unicamente). El dueño rechazo
// explicitamente compartir una tabla con un flag `kind`; esto es el cliente
// para /api/laundry/items, /api/laundry/locations y /api/laundry/movements.

export type LinenItem = {
  id: number;
  hotel_id: number;
  name: string;
  unit: string;
  min_quantity?: DecimalValue | null;
  active: boolean;
};

export type LinenLocation = {
  id: number;
  hotel_id: number;
  name: string;
};

export type LinenItemCreate = {
  name: string;
  unit: string;
  min_quantity?: DecimalValue | null;
  active?: boolean;
};

export type LinenLocationCreate = {
  name: string;
};

export type LinenMovementCreate = {
  linen_item_id: number;
  location_id?: number | null;
  movement_type: StockMovementType;
  quantity: DecimalValue;
  reason?: string | null;
};

export type LinenMovement = {
  id: number;
  hotel_id: number;
  item_id: number;
  location_id?: number | null;
  movement_type: StockMovementType;
  quantity: DecimalValue;
  reason?: string | null;
  created_by_user_id?: number | null;
  created_at: string;
  transfer_reference?: string | null;
};

export type CurrentLinenStock = {
  item_id: number;
  quantity: DecimalValue;
};

// GET /api/laundry/items/summary: every linen item's current balance in one
// request -- avoids the per-item N+1 (see LaundryPage.tsx's houseStockQueries
// and app/api/laundry_vendor.py get_laundry_linen_summary docstring).
export type LinenSummaryEntry = {
  item: LinenItem;
  current_quantity: DecimalValue;
  min_quantity?: DecimalValue | null;
  location_balances: Array<{
    location_id: number;
    current_quantity: DecimalValue;
    has_movements: boolean;
  }>;
};

export type LinenOpeningCountLine = {
  linen_item_id: number;
  location_id: number;
  quantity: DecimalValue;
};

export type LinenOpeningCountBatch = {
  counts: LinenOpeningCountLine[];
  reason: string;
};

export type LinenTransferCreate = {
  linen_item_id: number;
  source_location_id: number;
  destination_location_id: number;
  quantity: DecimalValue;
  reason: string;
};

export type LinenTransferResult = {
  transfer_reference: string;
  outbound: LinenMovement;
  inbound: LinenMovement;
};

export type LinenParLevel = {
  id: number;
  hotel_id: number;
  item_id: number;
  location_id: number;
  min_quantity: DecimalValue;
};

export const listLinenItems = (session?: SessionLike) =>
  apiFetch<LinenItem[]>("/api/laundry/items", { session });

export const createLinenItem = (payload: LinenItemCreate, session?: SessionLike) =>
  apiFetch<LinenItem>("/api/laundry/items", { method: "POST", data: payload, session });

export const deleteLinenItem = (itemId: number, session?: SessionLike) =>
  apiFetch<void>(`/api/laundry/items/${itemId}`, { method: "DELETE", session });

export const listLinenLocations = (session?: SessionLike) =>
  apiFetch<LinenLocation[]>("/api/laundry/locations", { session });

export const createLinenLocation = (payload: LinenLocationCreate, session?: SessionLike) =>
  apiFetch<LinenLocation>("/api/laundry/locations", { method: "POST", data: payload, session });

export const createLinenMovement = (payload: LinenMovementCreate, session?: SessionLike) =>
  apiFetch<LinenMovement>("/api/laundry/movements", { method: "POST", data: payload, session });

export const createLinenOpeningCounts = (payload: LinenOpeningCountBatch, session?: SessionLike) =>
  apiFetch<LinenMovement[]>("/api/laundry/opening-counts", { method: "POST", data: payload, session });

export const createLinenTransfer = (
  payload: LinenTransferCreate,
  { idempotencyKey }: { idempotencyKey: string },
  session?: SessionLike
) =>
  apiFetch<LinenTransferResult>("/api/laundry/transfers", {
    method: "POST",
    data: payload,
    headers: { "Idempotency-Key": idempotencyKey },
    session
  });

export const getCurrentLinenStock = (
  itemId: number,
  { locationId }: { locationId?: number } = {},
  session?: SessionLike
) => {
  const query = locationId ? `?location_id=${locationId}` : "";
  return apiFetch<CurrentLinenStock>(`/api/laundry/items/${itemId}/current${query}`, { session });
};

export const getLinenSummary = ({ locationId }: { locationId?: number } = {}, session?: SessionLike) => {
  const query = locationId ? `?location_id=${locationId}` : "";
  return apiFetch<LinenSummaryEntry[]>(`/api/laundry/items/summary${query}`, { session });
};

export const setLinenLocationMinimum = (
  itemId: number,
  locationId: number,
  min_quantity: DecimalValue,
  session?: SessionLike
) => apiFetch<LinenParLevel>(
  `/api/laundry/items/${itemId}/locations/${locationId}/minimum`,
  { method: "PUT", data: { min_quantity }, session }
);
