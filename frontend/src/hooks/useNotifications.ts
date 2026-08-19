import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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
import { useSession } from "../state/session";

import { useOnlineStatus } from "./useOnlineStatus";

const inboxKey = (hotelId: number | null, unreadOnly: boolean) => ["notifications", "inbox", hotelId, unreadOnly];
const preferencesKey = (hotelId: number | null) => ["notifications", "preferences", hotelId];
const dailyReportScheduleKey = (hotelId: number | null) => ["notifications", "daily-report-schedule", hotelId];

// Backend has no realtime "notification created" event on the SSE stream
// (see crossTabSync.ts's SyncDomain list -- notifications isn't one), so the
// unread badge/inbox polls instead, same 30s cadence as useGemmaChat's
// polling query. Never fetches while offline (useOnlineStatus) or without a
// valid session, matching every other query hook in this codebase.
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

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["notifications", "inbox", session.hotelId] });

  const markReadMutation = useMutation({
    mutationFn: (notificationId: number) => markNotificationRead(notificationId, true, session),
    onSuccess: invalidate
  });

  const markAllReadMutation = useMutation({
    mutationFn: () => markAllNotificationsRead(session),
    onSuccess: invalidate
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
  return useMutation({
    mutationFn: (payload: NotificationPreferenceUpdate) => updateNotificationPreference(payload, session),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: preferencesKey(session.hotelId) })
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
  return useMutation({
    mutationFn: (payload: DailyReportScheduleUpdate) => updateDailyReportSchedule(payload, session),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: dailyReportScheduleKey(session.hotelId) })
  });
}
