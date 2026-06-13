import { apiFetch, type SessionLike } from "./client";

export type LaundryStatus = "collected" | "sent" | "received" | "closed";

export type LaundryItem = {
  id: number;
  hotel_id: number;
  batch_id: number;
  item_type: string;
  quantity: number;
  room_id?: number | null;
};

export type LaundryBatch = {
  id: number;
  hotel_id: number;
  batch_code: string;
  status: LaundryStatus;
  sent_at?: string | null;
  received_at?: string | null;
  notes?: string | null;
  created_by_user_id?: number | null;
  created_at: string;
  items: LaundryItem[];
};

export type LaundryBatchCreate = {
  notes?: string | null;
};

export type LaundryItemCreate = {
  item_type: string;
  quantity: number;
  room_id?: number | null;
};

export const listLaundryBatches = (
  filters: { statusFilter?: string; batchCode?: string } = {},
  session?: SessionLike
) => {
  const params = new URLSearchParams();
  if (filters.statusFilter) params.set("status_filter", filters.statusFilter);
  if (filters.batchCode) params.set("batch_code", filters.batchCode);
  const query = params.toString();
  return apiFetch<LaundryBatch[]>(`/api/laundry/batches${query ? `?${query}` : ""}`, { session });
};

export const createLaundryBatch = (payload: LaundryBatchCreate, session?: SessionLike) =>
  apiFetch<LaundryBatch>("/api/laundry/batches", { method: "POST", data: payload, session });

export const addLaundryItem = (batchId: number, payload: LaundryItemCreate, session?: SessionLike) =>
  apiFetch<LaundryItem>(`/api/laundry/batches/${batchId}/items`, { method: "POST", data: payload, session });

export const updateLaundryStatus = (batchId: number, status: LaundryStatus, session?: SessionLike) =>
  apiFetch<LaundryBatch>(`/api/laundry/batches/${batchId}/status`, {
    method: "PATCH",
    data: { status },
    session
  });
