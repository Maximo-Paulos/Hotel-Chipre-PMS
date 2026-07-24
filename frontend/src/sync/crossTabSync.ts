import { useEffect } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";

import { buildAuthHeaders, buildUrl, type SessionLike } from "../api/client";
import { useSession } from "../state/session";

export type SyncDomain =
  | "analytics"
  | "cash"
  | "guests"
  | "onboarding"
  | "payments"
  | "reservations"
  | "rooms"
  | "settings"
  | "stock"
  | "users";

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
};

const CHANNEL_NAME = "hotel-pms-domain-events";
const STORAGE_KEY = "hotel-pms-domain-event";

const DOMAIN_QUERY_PREFIXES: Record<SyncDomain, string[]> = {
  analytics: ["analytics", "room-state-events"],
  cash: ["cash", "cash-register", "cash-sessions"],
  guests: ["guests", "guest", "guest-tags", "guest-quick-profile"],
  onboarding: ["onboarding"],
  payments: ["payments", "payment-summary", "payment-links", "payment-proofs", "reservations", "reservation"],
  reservations: [
    "reservations",
    "reservation",
    "reservation-operations",
    "reservation-pending-actions",
    "payment-summary",
    "room-movement-groups",
    "waitlist"
  ],
  rooms: [
    "rooms",
    "room-categories",
    "room-blocks",
    "room-movement-groups",
    "daily-rates",
    "rate-calendar"
  ],
  settings: ["hotel-config", "permissions-matrix", "api-keys", "whatsapp-settings", "subscription"],
  stock: ["stock-items", "stock-locations", "stock-low", "stock-current"],
  users: ["users"]
};

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

export const domainForPath = (path: string): SyncDomain | null => {
  const normalized = path.toLowerCase();
  if (normalized.includes("analytics") || normalized.includes("room-state-events")) return "analytics";
  if (normalized.includes("cash-register") || normalized.includes("cash")) return "cash";
  if (normalized.includes("stock") || normalized.includes("laundry")) return "stock";
  if (normalized.includes("payment") || normalized.includes("checkin")) return "payments";
  if (normalized.includes("reservation") || normalized.includes("waitlist") || normalized.includes("booking")) return "reservations";
  if (normalized.includes("room") || normalized.includes("rate") || normalized.includes("block")) return "rooms";
  if (normalized.includes("guest")) return "guests";
  if (normalized.includes("onboarding")) return "onboarding";
  if (normalized.includes("user") || normalized.includes("invitation")) return "users";
  if (normalized.includes("settings") || normalized.includes("config") || normalized.includes("subscription")) return "settings";
  return null;
};

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
  const domain = domainForPath(safePath);
  if (!normalizedHotelId || !domain) return;
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
};

const invalidateDomainQueries = (queryClient: QueryClient, hotelId: number, domain: SyncDomain) => {
  const prefixes = new Set(DOMAIN_QUERY_PREFIXES[domain]);
  return queryClient.invalidateQueries({
    predicate: (query) => {
      const [prefix, ...rest] = query.queryKey;
      if (typeof prefix !== "string" || !prefixes.has(prefix)) return false;
      // A cross-tenant message must never invalidate a query that carries a
      // different hotel scope. Unscoped operational keys stay untouched.
      return rest.some((part) => part === hotelId);
    }
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
  let retryCount = 0;
  while (!signal.aborted && retryCount < 6) {
    try {
      const response = await fetch(buildUrl("/api/events/stream"), {
        headers: buildAuthHeaders(session),
        signal
      });
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) return;
        throw new Error(`realtime stream returned ${response.status}`);
      }
      if (!response.body) throw new Error("realtime stream has no body");
      retryCount = 0;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (!signal.aborted) {
        const chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });
        buffer = parseSseFrames(buffer, (event) => {
          if (event.hotel_id !== hotelId || !event.domain) return;
          void invalidateDomainQueries(queryClient, hotelId, event.domain);
        });
      }
    } catch (error) {
      if (signal.aborted) return;
      retryCount += 1;
      const delay = Math.min(30_000, 1_000 * 2 ** (retryCount - 1));
      await new Promise<void>((resolve) => window.setTimeout(resolve, delay));
    }
  }
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
