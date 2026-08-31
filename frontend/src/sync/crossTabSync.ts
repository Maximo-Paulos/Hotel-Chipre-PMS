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
  hotel_id?: number;
  domain?: SyncDomain;
  event_type?: string;
  revision?: number;
  payload?: Record<string, string | number | boolean | null>;
};

const CHANNEL_NAME = "hotel-pms-domain-events";
const STORAGE_KEY = "hotel-pms-domain-event";

const DOMAIN_QUERY_PREFIXES = QUERY_PREFIXES_BY_DOMAIN;
const ALL_DOMAINS = Object.keys(QUERY_PREFIXES_BY_DOMAIN) as SyncDomain[];

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
  let hasConnected = false;
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
      const wasReconnect = hasConnected;
      hasConnected = true;
      retryCount = 0;
      updateRealtimeStatus(hotelId, "connected");
      if (wasReconnect) {
        // Redis pub/sub is intentionally ephemeral. A complete authoritative
        // refetch heals every event that arrived while this client was away.
        await refreshDomains(queryClient, hotelId, ALL_DOMAINS);
      }
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
}
