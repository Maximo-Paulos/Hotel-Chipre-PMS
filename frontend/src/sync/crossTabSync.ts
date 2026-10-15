import { useEffect, useMemo, useRef, useSyncExternalStore } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";

import { buildAuthHeaders, buildUrl, type SessionLike } from "../api/client";
import { recoveryDomainsForCursor, refreshDomains } from "../api/queryInvalidation";
import {
  QUERY_PREFIXES_BY_DOMAIN,
  type QueryDomain
} from "../api/queryKeys";
import { useSession } from "../state/session";

import { nextRealtimeRetryPlan } from "./retryPolicy";

export type SyncDomain = QueryDomain;

type SyncMessage = {
  version: 1;
  senderId: string;
  hotelId: number;
  domain: SyncDomain;
  path: string;
  occurredAt: number;
  originKey?: string;
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
  origin_key?: string;
  payload?: Record<string, string | number | boolean | null>;
};

const CHANNEL_NAME = "hotel-pms-domain-events";
const STORAGE_KEY = "hotel-pms-domain-event";

const DOMAIN_QUERY_PREFIXES = QUERY_PREFIXES_BY_DOMAIN;
const EVENT_ID_LIMIT = 2048;
const ORIGIN_DOMAIN_LIMIT = 2048;
// Coalesce a burst of committed table events into one tenant-scoped refetch.
const REALTIME_EVENT_DEBOUNCE_MS = 1_000;
const CROSS_TAB_INVALIDATION_DEBOUNCE_MS = 100;
// Recovery is a slow safety net only after the stream has been marked
// degraded. The stream itself recovers before every reconnect attempt, so a
// second fast poll would duplicate database reads while it is reconnecting.
// Hidden tabs pause recovery and catch up when they become visible again.
const REALTIME_RECOVERY_POLL_MS = 60_000;
const REALTIME_RECOVERY_MAX_POLL_MS = 5 * 60_000;

export const realtimeRecoveryPollDelay = (consecutiveFailures: number): number => {
  const failures = Number.isSafeInteger(consecutiveFailures) ? Math.max(0, consecutiveFailures) : 0;
  return Math.min(REALTIME_RECOVERY_MAX_POLL_MS, REALTIME_RECOVERY_POLL_MS * 2 ** failures);
};

export const isTerminalRealtimeAuthorizationError = (error: unknown): boolean => {
  if (!error || typeof error !== "object" || !("status" in error)) return false;
  const status = Number((error as { status?: unknown }).status);
  return status === 401 || status === 403;
};

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
const handledOriginDomains = new Set<string>();
const LOCAL_ORIGIN_REFRESH_EVENT = "hotel-pms:domain-event-local-recovery";
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const pendingLocalMutationOrigins = new Map<
  string,
  { hotelId: number; domains: Set<SyncDomain>; observedDomains: Set<SyncDomain> }
>();

const getSenderId = () => {
  if (!senderId) {
    senderId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }
  return senderId;
};

const normalizeHotelId = (hotelId?: unknown) => {
  const parsed = typeof hotelId === "string" ? parseInt(hotelId, 10) : hotelId;
  return typeof parsed === "number" && Number.isInteger(parsed) && parsed > 0 ? parsed : null;
};

const normalizeOriginKey = (originKey: unknown): string | null =>
  typeof originKey === "string" && UUID_PATTERN.test(originKey) ? originKey.toLowerCase() : null;

const mutationOriginKey = (hotelId: number, originKey: string) => `${hotelId}:${originKey}`;
const originDomainKey = (hotelId: number, originKey: string, domain: SyncDomain) =>
  `${hotelId}:${originKey}:${domain}`;

const rememberOriginDomain = (hotelId: number, originKey: string, domain: SyncDomain) => {
  const key = originDomainKey(hotelId, originKey, domain);
  if (handledOriginDomains.has(key)) handledOriginDomains.delete(key);
  handledOriginDomains.add(key);
  while (handledOriginDomains.size > ORIGIN_DOMAIN_LIMIT) {
    const oldest = handledOriginDomains.values().next().value;
    if (typeof oldest !== "string") break;
    handledOriginDomains.delete(oldest);
  }
};

/** Return false when this exact request/domain was already handled or is in flight locally. */
export const shouldRefreshForDomainOrigin = (
  hotelId: number,
  domain: SyncDomain,
  rawOriginKey: unknown
): boolean => {
  const normalizedHotelId = normalizeHotelId(hotelId);
  const originKey = normalizeOriginKey(rawOriginKey);
  if (!normalizedHotelId || !originKey) return true;
  const pending = pendingLocalMutationOrigins.get(mutationOriginKey(normalizedHotelId, originKey));
  if (pending && pending.domains.has(domain)) {
    pending.observedDomains.add(domain);
    return false;
  }
  const key = originDomainKey(normalizedHotelId, originKey, domain);
  if (handledOriginDomains.has(key)) return false;
  rememberOriginDomain(normalizedHotelId, originKey, domain);
  return true;
};

export const beginLocalDomainMutation = (
  hotelId: number | string | null | undefined,
  path: string,
  rawOriginKey: unknown
) => {
  const normalizedHotelId = normalizeHotelId(hotelId);
  const originKey = normalizeOriginKey(rawOriginKey);
  const domains = domainsForPath(path);
  if (!normalizedHotelId || !originKey || domains.length === 0) return;
  pendingLocalMutationOrigins.set(mutationOriginKey(normalizedHotelId, originKey), {
    hotelId: normalizedHotelId,
    domains: new Set(domains),
    observedDomains: new Set()
  });
};

export const finishLocalDomainMutation = (
  hotelId: number | string | null | undefined,
  rawOriginKey: unknown,
  succeeded: boolean
) => {
  const normalizedHotelId = normalizeHotelId(hotelId);
  const originKey = normalizeOriginKey(rawOriginKey);
  if (!normalizedHotelId || !originKey) return;
  const key = mutationOriginKey(normalizedHotelId, originKey);
  const pending = pendingLocalMutationOrigins.get(key);
  if (!pending) return;
  pendingLocalMutationOrigins.delete(key);

  if (succeeded) {
    pending.domains.forEach((domain) => rememberOriginDomain(pending.hotelId, originKey, domain));
    return;
  }

  const observedDomains = Array.from(pending.observedDomains);
  observedDomains.forEach((domain) => rememberOriginDomain(pending.hotelId, originKey, domain));
  if (observedDomains.length && typeof window !== "undefined") {
    try {
      window.dispatchEvent(
        new CustomEvent(LOCAL_ORIGIN_REFRESH_EVENT, {
          detail: { hotelId: pending.hotelId, domains: observedDomains }
        })
      );
    } catch {
      /* The original stream event remains safe to retry after this tab reloads. */
    }
  }
};

export const domainsForPath = (path: string): SyncDomain[] => {
  const normalized = path.toLowerCase();
  if (normalized.includes("rate-change-drafts")) return ["rooms"];
  if (normalized.includes("gemma")) return ["assistant"];
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
  if (normalized.includes("/whatsapp/channel")) return ["settings"];
  if (normalized.includes("whatsapp")) return ["whatsapp"];
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
  if (candidate.originKey !== undefined && !normalizeOriginKey(candidate.originKey)) return null;
  return { ...candidate, hotelId, domain: candidate.domain as SyncDomain } as SyncMessage;
};

export const broadcastDomainChange = (
  hotelId: number | string | null | undefined,
  path: string,
  rawOriginKey?: string
) => {
  if (typeof window === "undefined") return;
  const normalizedHotelId = normalizeHotelId(hotelId);
  const originKey = normalizeOriginKey(rawOriginKey);
  const safePath = path.split("?", 1)[0].slice(0, 200);
  const domains = domainsForPath(safePath);
  if (!normalizedHotelId || domains.length === 0) return;
  if (originKey) finishLocalDomainMutation(normalizedHotelId, originKey, true);
  domains.forEach((domain) => {
    const message: SyncMessage = {
      version: 1,
      senderId: getSenderId(),
      hotelId: normalizedHotelId,
      domain,
      path: safePath,
      occurredAt: Date.now(),
      ...(originKey ? { originKey } : {})
    };
    let postedToBroadcastChannel = false;
    try {
      if (typeof BroadcastChannel !== "undefined") {
        channel ??= new BroadcastChannel(CHANNEL_NAME);
        channel.postMessage(message);
        postedToBroadcastChannel = true;
      }
    } catch {
      // Storage below is the Safari/private-mode fallback.
    }
    if (!postedToBroadcastChannel) {
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(message));
      } catch {
        /* ignore unavailable storage */
      }
    }
  });
};

const notifyIfRelevant = (
  hotelId: number,
  scheduleRefresh: (domain: SyncDomain) => void,
  raw: unknown
) => {
  const message = parseMessage(raw);
  if (!message || message.senderId === getSenderId() || message.hotelId !== hotelId) return;
  if (!shouldRefreshForDomainOrigin(message.hotelId, message.domain, message.originKey)) return;
  scheduleRefresh(message.domain);
};

const createVisibleDomainRefreshQueue = (
  queryClient: QueryClient,
  hotelId: number,
  debounceMs: number
) => {
  const pendingDomains = new Set<SyncDomain>();
  let timer: number | null = null;
  const isHidden = () => typeof document !== "undefined" && document.visibilityState === "hidden";
  const clearTimer = () => {
    if (timer !== null && typeof window !== "undefined") window.clearTimeout(timer);
    timer = null;
  };
  const flush = () => {
    timer = null;
    if (isHidden() || pendingDomains.size === 0) return;
    const domains = Array.from(pendingDomains);
    pendingDomains.clear();
    void refreshDomains(queryClient, hotelId, domains);
  };
  const schedule = (domain: SyncDomain) => {
    pendingDomains.add(domain);
    if (timer !== null || isHidden() || typeof window === "undefined") return;
    timer = window.setTimeout(flush, debounceMs);
  };
  const onVisibilityChange = () => {
    if (isHidden()) {
      clearTimer();
      return;
    }
    if (pendingDomains.size > 0) {
      clearTimer();
      timer = window.setTimeout(flush, 0);
    }
  };
  if (typeof document !== "undefined") document.addEventListener("visibilitychange", onVisibilityChange);
  return {
    schedule,
    close: () => {
      clearTimer();
      pendingDomains.clear();
      if (typeof document !== "undefined") document.removeEventListener("visibilitychange", onVisibilityChange);
    }
  };
};

const startCrossTabSubscription = (queryClient: QueryClient, hotelId: number) => {
  if (typeof window === "undefined") return () => undefined;
  const refreshQueue = createVisibleDomainRefreshQueue(queryClient, hotelId, CROSS_TAB_INVALIDATION_DEBOUNCE_MS);
  const scheduleRefresh = refreshQueue.schedule;
  const onStorage = (event: StorageEvent) => {
    if (event.key !== STORAGE_KEY || !event.newValue) return;
    try {
      notifyIfRelevant(hotelId, scheduleRefresh, JSON.parse(event.newValue));
    } catch {
      /* ignore malformed cross-tab messages */
    }
  };
  window.addEventListener("storage", onStorage);
  const onLocalOriginRecovery = (event: Event) => {
    const detail = (event as CustomEvent<{ hotelId?: unknown; domains?: unknown }>).detail;
    if (normalizeHotelId(detail?.hotelId) !== hotelId || !Array.isArray(detail?.domains)) return;
    detail.domains.forEach((domain) => {
      if (typeof domain === "string" && Object.prototype.hasOwnProperty.call(DOMAIN_QUERY_PREFIXES, domain)) {
        scheduleRefresh(domain as SyncDomain);
      }
    });
  };
  window.addEventListener(LOCAL_ORIGIN_REFRESH_EVENT, onLocalOriginRecovery);
  const onChannelMessage = (event: MessageEvent) => notifyIfRelevant(hotelId, scheduleRefresh, event.data);
  try {
    if (typeof BroadcastChannel !== "undefined") {
      channel ??= new BroadcastChannel(CHANNEL_NAME);
      channel.addEventListener("message", onChannelMessage);
    }
  } catch {
    /* storage listener remains available */
  }
  return () => {
    refreshQueue.close();
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(LOCAL_ORIGIN_REFRESH_EVENT, onLocalOriginRecovery);
    try {
      channel?.removeEventListener("message", onChannelMessage);
    } catch {
      /* ignore channel cleanup errors */
    }
  };
};

/** Coalesce cross-tab broadcasts and SSE events into one tenant-scoped refresh. */
export const createDomainRefreshScheduler = (
  queryClient: QueryClient,
  hotelId: number,
  debounceMs = REALTIME_EVENT_DEBOUNCE_MS
) => {
  return createVisibleDomainRefreshQueue(queryClient, hotelId, debounceMs);
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

const waitUntilVisible = (signal: AbortSignal) => {
  if (typeof document === "undefined" || document.visibilityState !== "hidden" || signal.aborted) {
    return Promise.resolve();
  }
  return new Promise<void>((resolve) => {
    const finish = () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      signal.removeEventListener("abort", finish);
      resolve();
    };
    const onVisibilityChange = () => {
      if (document.visibilityState !== "hidden") finish();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    signal.addEventListener("abort", finish, { once: true });
    if (signal.aborted) finish();
  });
};

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
    // Recovery may finish after the live stream has already advanced this
    // tab. Cursors are monotonic; a stale recovery response must not rewind it.
    if (cursor < readCursor(session, hotelId)) return;
    window.sessionStorage.setItem(cursorStorageKey(session, hotelId), String(cursor));
  } catch {
    /* sessionStorage can be unavailable in private browsing */
  }
};

const recoveryFlights = new Map<string, Promise<void>>();

export const recoverRealtime = (
  session: SessionLike,
  queryClient: QueryClient,
  hotelId: number,
  signal?: AbortSignal
): Promise<void> => {
  // The stream reconnect path and the bounded recovery poll can overlap while
  // the API is slow. Share one request per user/hotel so this tab does not
  // multiply recovery reads during that delay. The key contains no credential.
  const flightKey = `${hotelId}:${String(session.userId ?? "")}`;
  const existingFlight = recoveryFlights.get(flightKey);
  if (existingFlight) return existingFlight;

  const currentCursor = readCursor(session, hotelId);
  const query = currentCursor > 0 ? `?after_cursor=${currentCursor}` : "";
  const request = (async () => {
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
      has_more?: boolean;
    };
    // A missing cursor is the expected first connection for a new browser
    // session. Reconcile only domains returned by recovery; refetchType="active"
    // limits network work to mounted views and avoids replaying a full reset.
    const domains = recoveryDomainsForCursor(currentCursor, payload);
    if (domains.length) {
      await refreshDomains(queryClient, hotelId, domains);
    }
    if (Number.isSafeInteger(payload.latest_cursor) && (payload.latest_cursor as number) >= currentCursor) {
      writeCursor(session, hotelId, payload.latest_cursor as number);
    }
  })();
  recoveryFlights.set(flightKey, request);
  const clearFlight = () => {
    if (recoveryFlights.get(flightKey) === request) recoveryFlights.delete(flightKey);
  };
  void request.then(clearFlight, clearFlight);
  return request;
};

const runEventStream = async (
  session: SessionLike,
  queryClient: QueryClient,
  signal: AbortSignal,
  scheduleRefresh: (domain: SyncDomain) => void,
) => {
  const hotelId = normalizeHotelId(session.hotelId);
  if (!hotelId || !session.accessToken || !session.userId) return;
  if (import.meta.env.VITE_REALTIME_EVENTS_ENABLED === "false") {
    updateRealtimeStatus(hotelId, "disabled");
    return;
  }

  let retryCount = 0;
  let connectedAt: number | null = null;
  const seenEventIds = new Set<string>();
  const waitBeforeRetry = async () => {
    const retryPlan = nextRealtimeRetryPlan(
      retryCount,
      connectedAt === null ? null : performance.now() - connectedAt,
      Math.random()
    );
    retryCount = retryPlan.failureCount;
    connectedAt = null;
    updateRealtimeStatus(hotelId, retryCount >= 3 ? "degraded" : "reconnecting");
    const delay = retryPlan.delayMs;
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
      timer = window.setTimeout(finish, delay);
      signal.addEventListener("abort", finish, { once: true });
      if (signal.aborted) finish();
    });
  };
  updateRealtimeStatus(hotelId, "connecting");
  while (!signal.aborted) {
    await waitUntilVisible(signal);
    if (signal.aborted) break;
    const connectionController = new AbortController();
    const abortConnection = () => connectionController.abort();
    const pauseWhenHidden = () => {
      if (document.visibilityState === "hidden") {
        updateRealtimeStatus(hotelId, "reconnecting");
        connectionController.abort();
      }
    };
    signal.addEventListener("abort", abortConnection, { once: true });
    document.addEventListener("visibilitychange", pauseWhenHidden);
    try {
      // Redis pub/sub is ephemeral. Recover committed domains before every
      // first connection and reconnect so a gap cannot be mistaken for a
      // healthy stream.
      await recoverRealtime(session, queryClient, hotelId, connectionController.signal);
      const streamCursor = readCursor(session, hotelId);
      const streamQuery = streamCursor > 0 ? `?after_cursor=${streamCursor}` : "";
      const response = await fetch(buildUrl(`/api/events/stream${streamQuery}`), {
        headers: buildAuthHeaders(session),
        credentials: "include",
        signal: connectionController.signal
      });
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          updateRealtimeStatus(hotelId, "degraded");
          return;
        }
        throw new Error(`realtime stream returned ${response.status}`);
      }
      if (!response.body) throw new Error("realtime stream has no body");
      connectedAt = performance.now();
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
          if (!shouldRefreshForDomainOrigin(hotelId, event.domain, event.origin_key)) return;
          scheduleRefresh(event.domain);
        });
      }
      if (signal.aborted) break;
      if (document.visibilityState === "hidden") continue;
      updateRealtimeStatus(hotelId, "reconnecting");
      await waitBeforeRetry();
    } catch (error) {
      if (signal.aborted) break;
      if (document.visibilityState === "hidden") continue;
      if (isTerminalRealtimeAuthorizationError(error)) {
        updateRealtimeStatus(hotelId, "degraded");
        return;
      }
      await waitBeforeRetry();
    } finally {
      document.removeEventListener("visibilitychange", pauseWhenHidden);
      signal.removeEventListener("abort", abortConnection);
    }
  }
};

export function useCrossTabSync() {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const hotelId = session.hotelId;
  const realtimeStatus = useRealtimeStatus();
  const recoveryFailureState = useRef({ hotelId: hotelId ?? null, count: 0 });
  const refreshScheduler = useMemo(
    () => createDomainRefreshScheduler(queryClient, hotelId ?? 0),
    [hotelId, queryClient]
  );

  useEffect(() => () => refreshScheduler.close(), [refreshScheduler]);

  useEffect(() => {
    if (!hotelId) return undefined;
    return startCrossTabSubscription(queryClient, hotelId);
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
      controller.signal,
      refreshScheduler.schedule
    );
    return () => controller.abort();
  }, [hotelId, queryClient, refreshScheduler, session.accessToken, session.userId]);

  useEffect(() => {
    if (!hotelId || !session.accessToken || !session.userId || realtimeStatus !== "degraded") {
      return undefined;
    }
    if (recoveryFailureState.current.hotelId !== hotelId) {
      recoveryFailureState.current = { hotelId, count: 0 };
    }
    let timer: number | null = null;
    let stopped = false;
    const schedule = (delay = realtimeRecoveryPollDelay(recoveryFailureState.current.count)) => {
      if (stopped) return;
      if (document.visibilityState === "hidden") {
        timer = null;
        return;
      }
      timer = window.setTimeout(async () => {
        if (stopped) return;
        try {
          await recoverRealtime(
            { hotelId, accessToken: session.accessToken, userId: session.userId },
            queryClient,
            hotelId
          );
          recoveryFailureState.current.count = 0;
        } catch (error) {
          if (isTerminalRealtimeAuthorizationError(error)) {
            stopped = true;
            timer = null;
            return;
          }
          recoveryFailureState.current.count += 1;
        }
        schedule(realtimeRecoveryPollDelay(recoveryFailureState.current.count));
      }, delay);
    };
    const onVisibilityChange = () => {
      if (timer !== null) window.clearTimeout(timer);
      timer = null;
      if (document.visibilityState !== "hidden") schedule(0);
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
