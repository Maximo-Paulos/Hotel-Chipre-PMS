/**
 * Read models refreshed by hotel-scoped domain events should survive normal
 * route changes without another request. A relevant database commit marks
 * these queries stale immediately; the five-minute window is only a fallback
 * for reopening a view when no invalidation arrived.
 */
export const EVENT_REFRESHED_QUERY_STALE_TIME_MS = 5 * 60 * 1000;
