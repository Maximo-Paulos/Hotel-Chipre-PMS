import { apiFetch, type SessionLike } from "./client";

// Mirrors app/models/notification.py NotificationSeverityEnum.
export type NotificationSeverity = "info" | "warning" | "critical";

// Mirrors app/schemas/notification.py NotificationRead. Deliberately no
// `payload` field -- the backend never puts guest/reservation detail there
// (see app/services/notification_service.py's SAFE_PAYLOAD_KEYS discipline),
// and NotificationRead itself doesn't expose it, so the frontend must not
// assume any field beyond these exists. `entity_type`/`entity_id` are the
// only deep-link material available; whatever the target page needs beyond
// that id is re-fetched (and re-authorized) by that page itself.
export type NotificationItem = {
  id: number;
  hotel_id: number;
  recipient_user_id: number;
  event_type: string;
  severity: NotificationSeverity;
  title: string;
  body?: string | null;
  entity_type?: string | null;
  entity_id?: number | null;
  is_read: boolean;
  read_at?: string | null;
  created_at: string;
  expires_at?: string | null;
};

export type NotificationListResponse = {
  items: NotificationItem[];
  unread_count: number;
};

export const listNotifications = (
  params: { unreadOnly?: boolean; limit?: number; offset?: number } = {},
  session?: SessionLike
) => {
  const query = new URLSearchParams();
  if (params.unreadOnly) query.set("unread_only", "true");
  query.set("limit", String(params.limit ?? 50));
  query.set("offset", String(params.offset ?? 0));
  return apiFetch<NotificationListResponse>(`/api/notifications?${query.toString()}`, { session });
};

export const markNotificationRead = (notificationId: number, read = true, session?: SessionLike) =>
  apiFetch<NotificationItem>(`/api/notifications/${notificationId}/read`, {
    method: "POST",
    data: { read },
    session
  });

export const markAllNotificationsRead = (session?: SessionLike) =>
  apiFetch<{ marked_read: number }>("/api/notifications/read-all", { method: "POST", session });

export type PushSubscriptionPayload = { endpoint: string; p256dh: string; auth: string };

export const registerPushSubscription = (payload: PushSubscriptionPayload, session?: SessionLike) =>
  apiFetch<{ registered: boolean }>("/api/notifications/push-subscriptions", {
    method: "POST",
    data: payload,
    session
  });

export const unregisterPushSubscription = (endpoint: string, session?: SessionLike) =>
  apiFetch<{ removed: boolean }>("/api/notifications/push-subscriptions/unregister", {
    method: "POST",
    data: { endpoint },
    session
  });

// Mirrors app/schemas/notification.py NotificationPreferenceRead.
// `event_type === ""` is the hotel-wide default row (see the backend model's
// own docstring) -- every other event_type row overrides it individually.
export type NotificationPreference = {
  event_type: string;
  in_app_enabled: boolean;
  push_enabled: boolean;
  email_enabled: boolean;
  quiet_hours_start?: number | null;
  quiet_hours_end?: number | null;
};

export type NotificationPreferenceUpdate = {
  event_type?: string;
  in_app_enabled?: boolean;
  push_enabled?: boolean;
  email_enabled?: boolean;
  quiet_hours_start?: number | null;
  quiet_hours_end?: number | null;
  clear_quiet_hours?: boolean;
};

export const listNotificationPreferences = (session?: SessionLike) =>
  apiFetch<NotificationPreference[]>("/api/notifications/preferences", { session });

export const updateNotificationPreference = (payload: NotificationPreferenceUpdate, session?: SessionLike) =>
  apiFetch<NotificationPreference>("/api/notifications/preferences", { method: "PUT", data: payload, session });

// Mirrors app/schemas/notification.py DailyReportScheduleRead/Update. Owner
// / co-owner only on the backend (require_roles(ROLE_OWNER, ROLE_CO_OWNER)).
export type DailyReportSchedule = {
  hotel_id: number;
  hour: number;
  recipient_user_ids: number[];
  recipient_roles: string[];
  channels: string[];
  sections: string[];
  enabled: boolean;
};

export type DailyReportScheduleUpdate = {
  hour: number;
  recipient_user_ids: number[];
  recipient_roles: string[];
  channels: string[];
  sections?: string[] | null;
  enabled: boolean;
};

export const getDailyReportSchedule = (session?: SessionLike) =>
  apiFetch<DailyReportSchedule>("/api/notifications/daily-report-schedule", { session });

export const updateDailyReportSchedule = (payload: DailyReportScheduleUpdate, session?: SessionLike) =>
  apiFetch<DailyReportSchedule>("/api/notifications/daily-report-schedule", {
    method: "PUT",
    data: payload,
    session
  });
