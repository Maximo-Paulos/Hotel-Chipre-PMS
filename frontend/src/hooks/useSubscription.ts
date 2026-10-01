import { useQuery } from "@tanstack/react-query";

import {
  getSubscriptionStatus,
  listSubscriptionPlans,
  type SubscriptionLimit,
  type SubscriptionPlan,
  type SubscriptionStatus
} from "../api/subscription";
import { hasValidSession } from "../api/client";
import { type SessionState, useSession } from "../state/session";

import { useEffectivePermissions } from "./usePermissions";

const normalizeLimits = (
  limits: SubscriptionStatus["limits"],
  roomsInUse: number,
  roomLimit: number
): SubscriptionLimit[] => {
  const asArray: SubscriptionLimit[] = [];

  if (Array.isArray(limits)) {
    limits.forEach((limit) => {
      if (!limit) return;
      const code = limit.code || "custom";
      asArray.push({
        code,
        label: limit.label ?? code,
        limit: typeof limit.limit === "number" || limit.limit === null ? limit.limit : null,
        used: typeof limit.used === "number" ? limit.used : undefined
      });
    });
  } else if (limits && typeof limits === "object") {
    Object.entries(limits).forEach(([code, value]) => {
      if (!value) return;
      const val = value as SubscriptionLimit;
      asArray.push({
        code,
        label: val.label ?? code,
        limit: typeof val.limit === "number" || val.limit === null ? val.limit : null,
        used: typeof val.used === "number" ? val.used : undefined
      });
    });
  }

  const hasRooms = asArray.some((item) => item.code === "rooms");
  if (!hasRooms) {
    asArray.unshift({
      code: "rooms",
      label: "Habitaciones operables",
      used: roomsInUse,
      limit: roomLimit
    });
  }

  return asArray;
};

const enrichPlans = (plans?: SubscriptionPlan[] | null): SubscriptionPlan[] => {
  return (plans ?? []).map((plan) => ({ ...plan, mock: false }));
};

const normalizeStatus = (data: SubscriptionStatus | null | undefined, session: SessionState): SubscriptionStatus => {
  if (!data || typeof data.status !== "string" || typeof data.room_limit !== "number" || typeof data.rooms_in_use !== "number") {
    throw new Error("El backend devolvió un estado de suscripción incompleto.");
  }

  const planFromData =
    (data as Record<string, unknown>)?.plan ??
    (data as Record<string, unknown>)?.plan_code ??
    (data as Record<string, unknown>)?.current_plan ??
    null;

  const statusFromData =
    (data as Record<string, unknown>)?.status ??
    (data as Record<string, unknown>)?.subscription_status;

  const canWriteRaw = (data as Record<string, unknown>)?.can_write;
  const canWrite =
    typeof canWriteRaw === "boolean"
      ? canWriteRaw
      : ["active", "trialing", "demo", "comped"].includes(String(statusFromData));

  const roomLimit = data.room_limit;
  const roomsInUse = data.rooms_in_use;
  const availablePlans = enrichPlans(data.available_plans);
  const limits = normalizeLimits(data.limits, roomsInUse, roomLimit);

  return {
    ...data,
    hotel_id: data.hotel_id ?? session.hotelId,
    plan: planFromData as string | null,
    status: statusFromData as string,
    room_limit: roomLimit,
    staff_limit: typeof data.staff_limit === "number" ? data.staff_limit : null,
    rooms_in_use: roomsInUse,
    can_write: canWrite,
    available_plans: availablePlans,
    limits,
    source: "api"
  };
};

export function useSubscriptionStatus(options?: { enabled?: boolean }) {
  const { session } = useSession();
  const { hasPermission } = useEffectivePermissions();
  const enabled = hasValidSession(session) && (options?.enabled ?? true) && hasPermission("settings:subscription:view");
  return useQuery({
    queryKey: ["subscription", session.hotelId ?? "none", session.userId ?? "none"],
    queryFn: async () => normalizeStatus(await getSubscriptionStatus(session), session),
    enabled,
    staleTime: 60_000
  });
}

export function useSubscriptionPlans() {
  const { session } = useSession();
  return useQuery({
    queryKey: ["subscription-plans"],
    queryFn: async () => enrichPlans(await listSubscriptionPlans(session)),
    staleTime: 5 * 60_000
  });
}
