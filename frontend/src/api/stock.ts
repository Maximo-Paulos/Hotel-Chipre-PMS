import { apiFetch, type SessionLike } from "./client";

export type StockMovementType = "in" | "out" | "adjustment" | "adjustment_out";

export type DecimalValue = string | number;

export type StockItem = {
  id: number;
  hotel_id: number;
  name: string;
  sku?: string | null;
  unit: string;
  min_quantity?: DecimalValue | null;
  active: boolean;
  // ARS, same as the rest of Stock. See app/models/stock.py StockItem.unit_cost.
  unit_cost?: DecimalValue | null;
};

export type StockLocation = {
  id: number;
  hotel_id: number;
  name: string;
};

export type StockMovement = {
  id: number;
  hotel_id: number;
  item_id: number;
  location_id?: number | null;
  movement_type: StockMovementType;
  quantity: DecimalValue;
  reason?: string | null;
  reservation_id?: number | null;
  created_by_user_id?: number | null;
  created_at: string;
};

export type StockItemCreate = {
  name: string;
  sku?: string | null;
  unit: string;
  min_quantity?: DecimalValue | null;
  active?: boolean;
  unit_cost?: DecimalValue | null;
};

export type StockItemUpdate = Partial<StockItemCreate>;

export type StockLocationCreate = {
  name: string;
};

export type StockMovementCreate = {
  item_id: number;
  location_id?: number | null;
  movement_type: StockMovementType;
  quantity: DecimalValue;
  reason?: string | null;
  reservation_id?: number | null;
};

export type CurrentStock = {
  item_id: number;
  quantity: DecimalValue;
};

// GET /api/stock/summary: every item's current balance in one request --
// avoids the per-item N+1 that used to back StockPage's item grid (see
// app/api/stock.py get_stock_summary docstring).
export type StockSummaryEntry = {
  item: StockItem;
  current_quantity: DecimalValue;
};

export type StockConsumptionGroupBy = "week" | "month";

export type StockConsumptionItem = {
  stock_item_id: number;
  stock_item_name: string;
  unit: string;
  current_quantity: DecimalValue;
  previous_quantity: DecimalValue;
  variation_pct?: DecimalValue | null;
};

export type StockConsumptionReport = {
  hotel_id: number;
  group_by: StockConsumptionGroupBy;
  date_from: string;
  date_to: string;
  previous_date_from: string;
  previous_date_to: string;
  items: StockConsumptionItem[];
};

export const listStockItems = (session?: SessionLike) =>
  apiFetch<StockItem[]>("/api/stock/items", { session });

export const listLowStockItems = (session?: SessionLike) =>
  apiFetch<StockItem[]>("/api/stock/items/low-stock", { session });

export const createStockItem = (payload: StockItemCreate, session?: SessionLike) =>
  apiFetch<StockItem>("/api/stock/items", { method: "POST", data: payload, session });

export const updateStockItem = (itemId: number, payload: StockItemUpdate, session?: SessionLike) =>
  apiFetch<StockItem>(`/api/stock/items/${itemId}`, { method: "PATCH", data: payload, session });

export const deleteStockItem = (itemId: number, session?: SessionLike) =>
  apiFetch<void>(`/api/stock/items/${itemId}`, { method: "DELETE", session });

export const listStockLocations = (session?: SessionLike) =>
  apiFetch<StockLocation[]>("/api/stock/locations", { session });

export const createStockLocation = (payload: StockLocationCreate, session?: SessionLike) =>
  apiFetch<StockLocation>("/api/stock/locations", { method: "POST", data: payload, session });

export const createStockMovement = (
  payload: StockMovementCreate,
  { idempotencyKey }: { idempotencyKey?: string } = {},
  session?: SessionLike
) =>
  apiFetch<StockMovement>("/api/stock/movements", {
    method: "POST",
    data: payload,
    headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
    session
  });

export const getStockSummary = ({ locationId }: { locationId?: number } = {}, session?: SessionLike) => {
  const query = locationId ? `?location_id=${locationId}` : "";
  return apiFetch<StockSummaryEntry[]>(`/api/stock/summary${query}`, { session });
};

export const listStockMovements = (
  { itemId, limit = 20 }: { itemId?: number; limit?: number } = {},
  session?: SessionLike
) => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (itemId) params.set("item_id", String(itemId));
  return apiFetch<StockMovement[]>(`/api/stock/movements?${params.toString()}`, { session });
};

export const getCurrentStock = (
  itemId: number,
  { locationId }: { locationId?: number } = {},
  session?: SessionLike
) => {
  const query = locationId ? `?location_id=${locationId}` : "";
  return apiFetch<CurrentStock>(`/api/stock/items/${itemId}/current${query}`, { session });
};

// D5 (Via D): "cuanto se consumio de cada item" por periodo, con el periodo
// anterior de igual largo para calcular variacion % (ver plan D5).
export const getStockConsumptionReport = (
  { dateFrom, dateTo, groupBy = "week" }: { dateFrom: string; dateTo: string; groupBy?: StockConsumptionGroupBy },
  session?: SessionLike
) => {
  const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo, group_by: groupBy });
  return apiFetch<StockConsumptionReport>(`/api/stock/consumption-report?${params.toString()}`, { session });
};
