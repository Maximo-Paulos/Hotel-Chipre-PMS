import { apiFetch, ApiError, type SessionLike } from "./client";

// Mirrors app/models/guest_restriction.py GuestRestrictionStatusEnum.
export type GuestRestrictionStatus = "active" | "resolved";

// Mirrors app/schemas/guest_restriction.py GuestRestrictionRead. `reason`
// and `detail` are only ever fetched for actors with
// guest:prohibition_read/manage (enforced server-side); the caller must
// still gate rendering of reason/detail behind guest:prohibition_manage --
// see GuestRestrictionBadge.
export type GuestRestriction = {
  id: number;
  hotel_id: number;
  guest_id: number;
  status: GuestRestrictionStatus;
  reason: string;
  detail?: string | null;
  valid_until?: string | null;
  created_by_user_id?: number | null;
  created_at: string;
  resolved_by_user_id?: number | null;
  resolved_at?: string | null;
  resolution_note?: string | null;
  legacy_guest_tag_id?: number | null;
};

export type GuestRestrictionCreatePayload = {
  reason: string;
  detail?: string;
  valid_until?: string;
};

export type GuestRestrictionResolvePayload = {
  resolution_note?: string;
};

// Carried on reservation create/update and check-in requests to authorize
// bypassing an active restriction -- see
// app/schemas/guest_restriction.py:GuestRestrictionOverrideRequest.
export type RestrictionOverride = {
  restriction_id: number;
  reason: string;
};

export const listGuestRestrictions = (guestId: number, activeOnly = true, session?: SessionLike) =>
  apiFetch<GuestRestriction[]>(
    `/api/guests/${guestId}/restrictions?active_only=${activeOnly ? "true" : "false"}`,
    { session }
  );

export const createGuestRestriction = (
  guestId: number,
  payload: GuestRestrictionCreatePayload,
  session?: SessionLike
) => apiFetch<GuestRestriction>(`/api/guests/${guestId}/restrictions`, { method: "POST", data: payload, session });

export const resolveGuestRestriction = (
  guestId: number,
  restrictionId: number,
  payload: GuestRestrictionResolvePayload,
  session?: SessionLike
) =>
  apiFetch<GuestRestriction>(`/api/guests/${guestId}/restrictions/${restrictionId}/resolve`, {
    method: "POST",
    data: payload,
    session
  });

// The GUEST_PROHIBITED 409 shape returned by reservation create/update,
// check-in, and price-quote when an active restriction blocks the action and
// no valid override was supplied (see app/services/guest_restriction_service.py).
export type GuestProhibitedErrorBody = {
  code: "GUEST_PROHIBITED";
  message: string;
  restriction_id: number;
};

// `error.payload` is the raw JSON body of the failed response (see
// api/client.ts ApiError) -- FastAPI's HTTPException(detail=...) puts our
// body under `detail`.
export const getGuestProhibitedDetail = (error: unknown): GuestProhibitedErrorBody | null => {
  if (!(error instanceof ApiError) || error.status !== 409) return null;
  const payload = error.payload;
  if (!payload || typeof payload !== "object") return null;
  const detail = (payload as Record<string, unknown>).detail;
  if (!detail || typeof detail !== "object") return null;
  const record = detail as Record<string, unknown>;
  if (record.code !== "GUEST_PROHIBITED" || typeof record.restriction_id !== "number") return null;
  return record as unknown as GuestProhibitedErrorBody;
};
