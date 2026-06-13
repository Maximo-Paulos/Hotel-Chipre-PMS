import { apiFetch, type SessionLike } from "./client";

export type StockMovementType = "in" | "out" | "adjustment";

export type DecimalValue = string | number;

export type StockItem = {
  id: number;
  hotel_id: number;
  name: string;
  sku?: string | null;
  unit: string;
  min_quantity?: DecimalValue | null;
  active: boolean;
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
};

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

export const listStockItems = (session?: SessionLike) => apiFetch<StockItem[]>("/api/stock/items", { session });

export const listLowStockItems = (session?: SessionLike) =>
  apiFetch<StockItem[]>("/api/stock/items/low-stock", { session });

export const createStockItem = (payload: StockItemCreate, session?: SessionLike) =>
  apiFetch<StockItem>("/api/stock/items", { method: "POST", data: payload, session });

export const listStockLocations = (session?: SessionLike) =>
  apiFetch<StockLocation[]>("/api/stock/locations", { session });

export const createStockLocation = (payload: StockLocationCreate, session?: SessionLike) =>
  apiFetch<StockLocation>("/api/stock/locations", { method: "POST", data: payload, session });

export const createStockMovement = (payload: StockMovementCreate, session?: SessionLike) =>
  apiFetch<StockMovement>("/api/stock/movements", { method: "POST", data: payload, session });

export const getCurrentStock = (itemId: number, session?: SessionLike) =>
  apiFetch<CurrentStock>(`/api/stock/items/${itemId}/current`, { session });
