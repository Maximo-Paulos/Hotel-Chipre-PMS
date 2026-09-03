import { useEffect, useSyncExternalStore } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";

import { buildAuthHeaders, buildUrl, type SessionLike } from "../api/client";
import { refreshDomains } from "../api/queryInvalidation";
import {
  HOTEL_ID_INDEX_BY_QUERY_PREFIX,
  QUERY_PREFIXES_BY_DOMAIN,
  hotelIdForQueryKey,
  type QueryDomain
} from "../api/queryKeys";
import { useSession } from "../state/session";

export type SyncDomain = QueryDomain;

type SyncMessage = {
  version: 1;
  senderId: string;
  hotelId: number;
  domain: SyncDomain;
  path: string;
  occurredAt: number;
};

type ServerEvent = {
  version?: number;
  schema_version?: number;
  event_id?: string;
  hotel_id?: number;
  domain?: SyncDomain;
  event_type?: string;
  revision?: number;
  cursor?: number | string | null;
  payload?: Record<string, string | number | boolean | null>;
};

const CHANNEL_NAME = "hotel-pms-domain-events";
const STORAGE_KEY = "hotel-pms-domain-event";

const DOMAIN_QUERY_PREFIXES = QUERY_PREFIXES_BY_DOMAIN;
const ALL_DOMAINS = Object.keys(QUERY_PREFIXES_BY_DOMAIN) as SyncDomain[];
const EVENT_ID_LIMIT = 2048;

export type RealtimeConnectionStatus = "disabled" | "connecting" | "connected" | "reconnecting" | "degraded";

const statusByHotel = new Map<number, RealtimeConnectionStatus>();
const statusListeners = new Set<() => void>();

const updateRealtimeStatus = (hotelId: number, status: RealtimeConnectionStatus) => {
  if (statusByHotel.get(hotelId) === status) return;
  statusByHotel.set(hotelId, status);
  statusListeners.forEach((listener) => listener());
};

const subscribeRealtimeStatus = (listener: () => void) => {
  statusListeners.add(listener);
  return () => statusListeners.delete(listener);
};

const snapshotForHotel = (hotelId: number | null | undefined): RealtimeConnectionStatus =>
  hotelId ? statusByHotel.get(hotelId) ?? "connecting" : "disabled";

export function useRealtimeStatus(): RealtimeConnectionStatus {
  const { session } = useSession();
  return useSyncExternalStore(
    subscribeRealtimeStatus,
    () => snapshotForHotel(session.hotelId),
    () => "disabled"
  );
}

let senderId: string | null = null;
let channel: BroadcastChannel | null = null;

const getSenderId = () => {
  if (!senderId) {
    senderId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }
  return senderId;
};

const normalizeHotelId = (hotelId?: number | string | null) => {
  const parsed = typeof hotelId === "string" ? parseInt(hotelId, 10) : hotelId;
  return Number.isInteger(parsed) && (parsed as number) > 0 ? (parsed as number) : null;
};

export const domainsForPath = (path: string): SyncDomain[] => {
  const normalized = path.toLowerCase();
  if (normalized.includes("analytics")) return ["analytics"];
  if (normalized.includes("room-state-events")) return ["rooms", "reservations", "analytics"];
  if (normalized.includes("cash-register") || normalized.includes("cash")) return ["cash", "payments", "analytics"];
  if (normalized.includes("stock") || normalized.includes("laundry") || normalized.includes("linen")) {
    return ["stock", "analytics"];
  }
  if (normalized.includes("surcharge")) return ["settings", "payments", "analytics"];
  if (normalized.includes("payment") || normalized.includes("checkin") || normalized.includes("checkout")) {
    return ["payments", "reservations", "cash", "analytics"];
  }
  if (normalized.includes("reservation") || normalized.includes("waitlist") || normalized.includes("booking")) {
    return ["reservations", "rooms", "analytics"];
  }
  if (normalized.includes("room") || normalized.includes("rate") || normalized.includes("block")) {
    return ["rooms", "reservations", "analytics"];
  }
  if (normalized.includes("category")) return ["rooms", "reservations", "analytics"];
  if (normalized.includes("guest")) return ["guests", "reservations", "analytics"];
  if (normalized.includes("onboarding")) return ["onboarding", "settings"];
  if (normalized.includes("permission") || normalized.includes("security")) return ["security", "users", "settings"];
  if (normalized.includes("user") || normalized.includes("invitation")) return ["users", "security", "settings"];
  if (normalized.includes("notification")) return ["notifications", "settings"];
  if (
    normalized.includes("company") ||
    normalized.includes("integration") ||
    normalized.includes("api-key") ||
    normalized.includes("promotion")
  ) {
    return ["settings"];
  }
  if (normalized.includes("settings") || normalized.includes("config") || normalized.includes("subscription")) return ["settings"];
  return [];
};

export const domainForPath = (path: string): SyncDomain | null => domainsForPath(path)[0] ?? null;

const parseMessage = (raw: unknown): SyncMessage | null => {
  if (!raw || typeof raw !== "object") return null;
  const candidate = raw as Partial<SyncMessage>;
  const hotelId = normalizeHotelId(candidate.hotelId);
  if (
    candidate.version !== 1 ||
    typeof candidate.senderId !== "string" ||
    !hotelId ||
    typeof candidate.domain !== "string" ||
    !Object.prototype.hasOwnProperty.call(DOMAIN_QUERY_PREFIXES, candidate.domain)
  ) {
    return null;
  }
  return { ...candidate, hotelId, domain: candidate.domain as SyncDomain } as SyncMessage;
};

export const broadcastDomainChange = (hotelId: number | string | null | undefined, path: string) => {
  if (typeof window === "undefined") return;
  const normalizedHotelId = normalizeHotelId(hotelId);
  const safePath = path.split("?", 1)[0].slice(0, 200);
  const domains = domainsForPath(safePath);
  if (!normalizedHotelId || domains.length === 0) return;
  domains.forEach((domain) => {
    const message: SyncMessage = {
      version: 1,
      senderId: getSenderId(),
      hotelId: normalizedHotelId,
      domain,
      path: safePath,
      occurredAt: Date.now()
    };
    try {
      if (typeof BroadcastChannel !== "undefined") {
        channel ??= new BroadcastChannel(CHANNEL_NAME);
        channel.postMessage(message);
      }
    } catch {
      // Storage below is the Safari/private-mode fallback.
    }
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(message));
    } catch {
      /* ignore unavailable storage */
    }
  });
};

const invalidateDomainQueries = (queryClient: QueryClient, hotelId: number, domain: SyncDomain) => {
  const prefixes = new Set(DOMAIN_QUERY_PREFIXES[domain]);
  return queryClient.invalidateQueries({
    predicate: (query) => {
      const [prefix] = query.queryKey;
      if (typeof prefix !== "string" || !prefixes.has(prefix)) return false;
      // A cross-tenant message must never invalidate a query that carries a
      // different hotel scope. Unknown/unscoped operational keys stay untouched.
      return hotelIdForQueryKey(query.queryKey) === hotelId && HOTEL_ID_INDEX_BY_QUERY_PREFIX[prefix] !== undefined;
    },
    refetchType: "active"
  });
};

const notifyIfRelevant = (queryClient: QueryClient, hotelId: number, raw: unknown) => {
  const message = parseMessage(raw);
  if (!message || message.senderId === getSenderId() || message.hotelId !== hotelId) return;
  void invalidateDomainQueries(queryClient, hotelId, message.domain);
};

const startCrossTabSubscription = (hotelId: number, queryClient: QueryClient) => {
  if (typeof window === "undefined") return () => undefined;
  const onStorage = (event: StorageEvent) => {
    if (event.key !== STORAGE_KEY || !event.newValue) return;
    try {
      notifyIfRelevant(queryClient, hotelId, JSON.parse(event.newValue));
    } catch {
      /* ignore malformed cross-tab messages */
    }
  };
  window.addEventListener("storage", onStorage);
  const onChannelMessage = (event: MessageEvent) => notifyIfRelevant(queryClient, hotelId, event.data);
  try {
    if (typeof BroadcastChannel !== "undefined") {
      channel ??= new BroadcastChannel(CHANNEL_NAME);
      channel.addEventListener("message", onChannelMessage);
    }
  } catch {
    /* storage listener remains available */
  }
  return () => {
    window.removeEventListener("storage", onStorage);
    try {
      channel?.removeEventListener("message", onChannelMessage);
    } catch {
      /* ignore channel cleanup errors */
    }
  };
};

const parseSseFrames = (buffer: string, onEvent: (event: ServerEvent) => void) => {
  const frames = buffer.split("\n\n");
  const remainder = frames.pop() ?? "";
  frames.forEach((frame) => {
    const data = frame
      .split(/\r?\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trim())
      .join("\n");
    if (!data) return;
    try {
      onEvent(JSON.parse(data) as ServerEvent);
    } catch {
      /* ignore malformed server frames */
    }
  });
  return remainder;
};

const cursorStorageKey = (session: SessionLike, hotelId: number) =>
  `hotel-pms:realtime-cursor:${hotelId}:${session.userId}`;

const readCursor = (session: SessionLike, hotelId: number): number => {
  if (typeof window === "undefined") return 0;
  try {
    const value = Number(window.sessionStorage.getItem(cursorStorageKey(session, hotelId)) ?? 0);
    return Number.isSafeInteger(value) && value >= 0 ? value : 0;
  } catch {
    return 0;
  }
};

const writeCursor = (session: SessionLike, hotelId: number, cursor: number) => {
  if (typeof window === "undefined" || !Number.isSafeInteger(cursor) || cursor < 0) return;
  try {
    window.sessionStorage.setItem(cursorStorageKey(session, hotelId), String(cursor));
  } catch {
    /* sessionStorage can be unavailable in private browsing */
  }
};

const recoverRealtime = async (
  session: SessionLike,
  queryClient: QueryClient,
  hotelId: number,
  signal?: AbortSignal
) => {
  const currentCursor = readCursor(session, hotelId);
  const query = currentCursor > 0 ? `?after_cursor=${currentCursor}` : "";
  const response = await fetch(buildUrl(`/api/events/recovery${query}`), {
    headers: buildAuthHeaders(session),
    credentials: "include",
    signal
  });
  if (response.status === 401 || response.status === 403) {
    throw Object.assign(new Error("realtime recovery unauthorized"), { status: response.status });
  }
  if (!response.ok) throw new Error(`realtime recovery returned ${response.status}`);
  const payload = (await response.json()) as {
    latest_cursor?: number;
    domains?: string[];
    reset_required?: boolean;
  };
  const domains = (payload.domains ?? []).filter((domain): domain is SyncDomain =>
    ALL_DOMAINS.includes(domain as SyncDomain)
  );
  if (payload.reset_required || currentCursor === 0) {
    await refreshDomains(queryClient, hotelId, ALL_DOMAINS);
  } else if (domains.length) {
    await refreshDomains(queryClient, hotelId, domains);
  }
  if (Number.isSafeInteger(payload.latest_cursor) && (payload.latest_cursor as number) >= currentCursor) {
    writeCursor(session, hotelId, payload.latest_cursor as number);
  }
};

const runEventStream = async (
  session: SessionLike,
  queryClient: QueryClient,
  signal: AbortSignal,
) => {
  const hotelId = normalizeHotelId(session.hotelId);
  if (!hotelId || !session.accessToken || !session.userId) return;
  if (import.meta.env.VITE_REALTIME_EVENTS_ENABLED === "false") {
    updateRealtimeStatus(hotelId, "disabled");
    return;
  }

  let retryCount = 0;
  const seenEventIds = new Set<string>();
  const scheduledDomains = new Set<SyncDomain>();
  let refreshTimer: number | null = null;
  const waitBeforeRetry = async () => {
    retryCount += 1;
    updateRealtimeStatus(hotelId, retryCount >= 3 ? "degraded" : "reconnecting");
    const delay = Math.min(30_000, 1_000 * 2 ** (retryCount - 1));
    const jitter = Math.floor(Math.random() * Math.max(250, delay * 0.2));
    await new Promise<void>((resolve) => {
      let timer: number | null = null;
      const finish = () => {
        if (timer !== null) {
          window.clearTimeout(timer);
          timer = null;
        }
        signal.removeEventListener("abort", finish);
        resolve();
      };
      timer = window.setTimeout(finish, delay + jitter);
      signal.addEventListener("abort", finish, { once: true });
      if (signal.aborted) finish();
    });
  };
  const scheduleRefresh = (domain: SyncDomain) => {
    scheduledDomains.add(domain);
    if (refreshTimer !== null) return;
    refreshTimer = window.setTimeout(() => {
      const domains = Array.from(scheduledDomains);
      scheduledDomains.clear();
      refreshTimer = null;
      void refreshDomains(queryClient, hotelId, domains);
    }, 75);
  };

  updateRealtimeStatus(hotelId, "connecting");
  while (!signal.aborted) {
    try {
      // Redis pub/sub is ephemeral. Recover committed domains before every
      // first connection and reconnect so a gap cannot be mistaken for a
      // healthy stream.
      await recoverRealtime(session, queryClient, hotelId, signal);
      const response = await fetch(buildUrl("/api/events/stream"), {
        headers: buildAuthHeaders(session),
        credentials: "include",
        signal
      });
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          updateRealtimeStatus(hotelId, "degraded");
          return;
        }
        throw new Error(`realtime stream returned ${response.status}`);
      }
      if (!response.body) throw new Error("realtime stream has no body");
      retryCount = 0;
      updateRealtimeStatus(hotelId, "connected");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (!signal.aborted) {
        const chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });
        buffer = parseSseFrames(buffer, (event) => {
          if (
            event.hotel_id !== hotelId ||
            !event.domain ||
            !Object.prototype.hasOwnProperty.call(DOMAIN_QUERY_PREFIXES, event.domain)
          ) {
            return;
          }
          if (event.event_id) {
            if (seenEventIds.has(event.event_id)) return;
            seenEventIds.add(event.event_id);
            if (seenEventIds.size > EVENT_ID_LIMIT) {
              const first = seenEventIds.values().next().value;
              if (typeof first === "string") seenEventIds.delete(first);
            }
          }
          const cursor = Number(event.cursor);
          const currentCursor = readCursor(session, hotelId);
          if (Number.isSafeInteger(cursor) && cursor <= currentCursor) return;
          if (Number.isSafeInteger(cursor)) writeCursor(session, hotelId, cursor);
          scheduleRefresh(event.domain);
        });
      }
      if (signal.aborted) break;
      updateRealtimeStatus(hotelId, "reconnecting");
      await waitBeforeRetry();
    } catch (error) {
      if (signal.aborted) break;
      await waitBeforeRetry();
    }
  }
  if (refreshTimer !== null) window.clearTimeout(refreshTimer);
  scheduledDomains.clear();
};

export function useCrossTabSync() {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const hotelId = session.hotelId;
  const realtimeStatus = useRealtimeStatus();

  useEffect(() => {
    if (!hotelId) return undefined;
    return startCrossTabSubscription(hotelId, queryClient);
  }, [hotelId, queryClient]);

  useEffect(() => {
    if (!hotelId || !session.accessToken || !session.userId) return undefined;
    const controller = new AbortController();
    void runEventStream(
      {
        hotelId,
        accessToken: session.accessToken,
        userId: session.userId
      },
      queryClient,
      controller.signal
    );
    return () => controller.abort();
  }, [hotelId, queryClient, session.accessToken, session.userId]);

  useEffect(() => {
    if (!hotelId || !session.accessToken || !session.userId || realtimeStatus === "connected" || realtimeStatus === "disabled") {
      return undefined;
    }
    let timer: number | null = null;
    let stopped = false;
    const schedule = () => {
      const delay = typeof document !== "undefined" && document.hidden ? 60_000 : 15_000;
      timer = window.setTimeout(async () => {
        if (stopped) return;
        try {
          await recoverRealtime(
            { hotelId, accessToken: session.accessToken, userId: session.userId },
            queryClient,
            hotelId
          );
        } catch {
          /* SSE remains the primary path; the next bounded poll retries. */
        }
        schedule();
      }, delay);
    };
    const onVisibilityChange = () => {
      if (timer !== null) window.clearTimeout(timer);
      schedule();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    schedule();
    return () => {
      stopped = true;
      if (timer !== null) window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [hotelId, queryClient, realtimeStatus, session.accessToken, session.userId]);
}
