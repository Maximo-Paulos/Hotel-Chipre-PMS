import { apiFetch, type SessionLike } from "./client";

export type OperationalAuditItem = {
  source: string;
  source_id: number;
  area: string;
  action: string;
  summary: string;
  actor_user_id?: number | null;
  actor_name: string;
  occurred_at: string;
  reservation_id?: number | null;
  room_id?: number | null;
  from_room_id?: number | null;
  to_room_id?: number | null;
  reason_code?: string | null;
  reason_note?: string | null;
  origin_room_disposition?: string | null;
  origin_room_status_before?: string | null;
  origin_room_status_after?: string | null;
  payment_method?: string | null;
  transaction_type?: string | null;
  transaction_status?: string | null;
  movement_type?: string | null;
  amount?: number | null;
  currency_code?: string | null;
  details: Record<string, unknown>;
};

export type OperationalAuditResponse = {
  hotel_id: number;
  items: OperationalAuditItem[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
};

export type OperationalAuditFilters = {
  limit?: number;
  offset?: number;
  from?: string;
  to?: string;
  actor_user_id?: number;
  category?: string;
  reservation_id?: number;
  room_id?: number;
  action?: string;
};

export const getOperationalAudit = (filters: OperationalAuditFilters = {}, session?: SessionLike) => {
  const query = new URLSearchParams();
  if (filters.limit) query.set("limit", String(filters.limit));
  if (filters.offset) query.set("offset", String(filters.offset));
  if (filters.from) query.set("from", filters.from);
  if (filters.to) query.set("to", filters.to);
  if (filters.actor_user_id) query.set("actor_user_id", String(filters.actor_user_id));
  if (filters.category) query.set("category", filters.category);
  if (filters.reservation_id) query.set("reservation_id", String(filters.reservation_id));
  if (filters.room_id) query.set("room_id", String(filters.room_id));
  if (filters.action) query.set("action", filters.action);
  return apiFetch<OperationalAuditResponse>(`/api/operations/audit?${query.toString()}`, { session });
};
