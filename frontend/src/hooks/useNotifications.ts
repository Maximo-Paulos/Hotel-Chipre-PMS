import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getDailyReportSchedule,
  listNotificationPreferences,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  updateDailyReportSchedule,
  updateNotificationPreference,
  type DailyReportScheduleUpdate,
  type NotificationListResponse,
  type NotificationPreferenceUpdate
} from "../api/notifications";
import { hasValidSession } from "../api/client";
import { refreshAfterMutation } from "../api/queryInvalidation";
import { useSession } from "../state/session";

import { useOnlineStatus } from "./useOnlineStatus";
import { useGuardedMutation } from "./useGuardedMutation";

const inboxKey = (hotelId: number | null, unreadOnly: boolean) => ["notifications", "inbox", hotelId, unreadOnly];
const preferencesKey = (hotelId: number | null) => ["notifications", "preferences", hotelId];
const dailyReportScheduleKey = (hotelId: number | null) => ["notifications", "daily-report-schedule", hotelId];

// Notifications still poll while open, but mutations use the same tenant-safe
// invalidation path as the rest of the PMS so a read/unread change is visible
// in the bell and the open inbox before the mutation reports success.
export function useNotificationsInbox(unreadOnly = false, limit = 50, offset = 0) {
  const { session } = useSession();
  const isOnline = useOnlineStatus();
  const enabled = hasValidSession(session) && isOnline;

  return useQuery<NotificationListResponse>({
    queryKey: [...inboxKey(session.hotelId, unreadOnly), limit, offset],
    queryFn: () => listNotifications({ unreadOnly, limit, offset }, session),
    enabled,
    refetchInterval: enabled ? 30_000 : false,
    staleTime: 15_000
  });
}

// Cheap, separate query (limit=1) just for the bell badge -- the header/
// bottom-nav bell needs the unread count everywhere, not the full list the
// open panel fetches with its own limit.
export function useUnreadNotificationCount() {
  const { data } = useNotificationsInbox(false, 1, 0);
  return data?.unread_count ?? 0;
}

export function useNotificationMutations() {
  const queryClient = useQueryClient();
  const { session } = useSession();

  const invalidate = () => refreshAfterMutation(queryClient, session.hotelId, ["notifications"]);

  const markReadMutation = useGuardedMutation({
    mutationFn: (notificationId: number) => markNotificationRead(notificationId, true, session),
    onSuccess: async () => invalidate()
  });

  const markAllReadMutation = useGuardedMutation({
    mutationFn: () => markAllNotificationsRead(session),
    onSuccess: async () => invalidate()
  });

  return { markReadMutation, markAllReadMutation };
}

export function useNotificationPreferences() {
  const { session } = useSession();
  return useQuery({
    queryKey: preferencesKey(session.hotelId),
    queryFn: () => listNotificationPreferences(session),
    enabled: hasValidSession(session),
    staleTime: 30_000
  });
}

export function useNotificationPreferenceMutation() {
  const queryClient = useQueryClient();
  const { session } = useSession();
  return useGuardedMutation({
    mutationFn: (payload: NotificationPreferenceUpdate) => updateNotificationPreference(payload, session),
    onSuccess: async () => refreshAfterMutation(queryClient, session.hotelId, ["notifications", "settings"])
  });
}

// Owner/co-owner only on the backend (require_roles) -- callers must gate
// rendering with PermissionGate roles={["owner","co_owner"]} the same way
// SettingsHotelPage gates its owner-only sections; this hook itself doesn't
// re-check role, it just won't get useful data (403) for anyone else.
export function useDailyReportSchedule(enabled: boolean) {
  const { session } = useSession();
  return useQuery({
    queryKey: dailyReportScheduleKey(session.hotelId),
    queryFn: () => getDailyReportSchedule(session),
    enabled: enabled && hasValidSession(session),
    retry: false,
    staleTime: 30_000
  });
}

export function useDailyReportScheduleMutation() {
  const queryClient = useQueryClient();
  const { session } = useSession();
  return useGuardedMutation({
    mutationFn: (payload: DailyReportScheduleUpdate) => updateDailyReportSchedule(payload, session),
    onSuccess: async () => refreshAfterMutation(queryClient, session.hotelId, ["notifications", "settings"])
  });
}
