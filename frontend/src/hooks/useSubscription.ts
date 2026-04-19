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

export const FALLBACK_PLANS: SubscriptionPlan[] = [
  {
    code: "starter",
    name: "Starter",
    price_month: 0,
    room_limit: 15,
    description: "Ideal para hostels y B&B que empiezan a digitalizarse.",
    features: ["Dashboard básico", "Hasta 15 habitaciones", "Exportes manuales CSV"],
    badge: "Gratis",
    mock: true
  },
  {
    code: "pro",
    name: "Pro",
    price_month: 49,
    room_limit: 40,
    description: "Para hoteles boutique que quieren operar sin fricción.",
    features: ["Check-in rápido", "Hasta 8 usuarios", "Reportes diarios", "Soporte priorizado"],
    badge: "Recomendado",
    highlight: true,
    mock: true
  },
  {
    code: "ultra",
    name: "Ultra",
    price_month: 99,
    room_limit: 80,
    description: "Hoteles con más volumen y necesidad de control fino.",
    features: ["Integración OTA", "Hasta 20 usuarios", "Roles avanzados", "SLA 99.5%"],
    badge: "Escala",
    mock: true
  }
];

const buildMockStatus = (session: SessionState): SubscriptionStatus => ({
  hotel_id: session.hotelId ?? null,
  status: "active",
  plan: "pro",
  room_limit: 40,
  staff_limit: 8,
  rooms_in_use: 4,
  can_write: true,
  limits: [
    { code: "rooms", label: "Habitaciones operables", used: 4, limit: 40 },
    { code: "users", label: "Usuarios activos", used: 6, limit: 8 }
  ],
  available_plans: FALLBACK_PLANS,
  source: "mock"
});

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
  const fallbackMap = FALLBACK_PLANS.reduce<Record<string, SubscriptionPlan>>((acc, plan) => {
    acc[plan.code] = plan;
    return acc;
  }, {});

  if (!plans || plans.length === 0) {
    return FALLBACK_PLANS.map((plan) => ({ ...plan, mock: true }));
  }

  return plans.map((plan) => {
    const fallback = fallbackMap[plan.code];
    return {
      ...(fallback ? { ...fallback, mock: false } : { mock: false }),
      ...plan,
      price_month: plan.price_month ?? fallback?.price_month ?? null,
      room_limit: typeof plan.room_limit === "number" ? plan.room_limit : fallback?.room_limit ?? 0,
      description: plan.description ?? fallback?.description,
      features: plan.features ?? fallback?.features,
      badge: plan.badge ?? fallback?.badge,
      highlight: plan.highlight ?? fallback?.highlight
    };
  });
};

const normalizeStatus = (data: SubscriptionStatus | null | undefined, session: SessionState): SubscriptionStatus => {
  const fallback = buildMockStatus(session);
  if (!data) return fallback;

  const planFromData =
    (data as Record<string, unknown>)?.plan ??
    (data as Record<string, unknown>)?.plan_code ??
    (data as Record<string, unknown>)?.current_plan ??
    fallback.plan;

  const statusFromData =
    (data as Record<string, unknown>)?.status ??
    (data as Record<string, unknown>)?.subscription_status ??
    fallback.status;

  const canWriteRaw = (data as Record<string, unknown>)?.can_write;
  const canWrite =
    typeof canWriteRaw === "boolean"
      ? canWriteRaw
      : ["active", "trialing", "demo", "comped"].includes(String(statusFromData));

  const roomLimit = typeof data.room_limit === "number" ? data.room_limit : fallback.room_limit;
  const roomsInUse = typeof data.rooms_in_use === "number" ? data.rooms_in_use : fallback.rooms_in_use;
  const availablePlans = enrichPlans(data.available_plans);
  const limits = normalizeLimits(data.limits, roomsInUse, roomLimit);
  const fallbackLimits = normalizeLimits(undefined, fallback.rooms_in_use, fallback.room_limit);

  return {
    ...fallback,
    ...data,
    plan: planFromData as string | null,
    status: statusFromData as string,
    room_limit: roomLimit,
    staff_limit: typeof data.staff_limit === "number" ? data.staff_limit : fallback.staff_limit,
    rooms_in_use: roomsInUse,
    can_write: canWrite,
    available_plans: availablePlans.length ? availablePlans : fallback.available_plans,
    limits: limits.length ? limits : fallbackLimits,
    source: "api"
  };
};

export function useSubscriptionStatus() {
  const { session } = useSession();
  return useQuery({
    queryKey: ["subscription", session.hotelId ?? "none"],
    queryFn: async () => {
      try {
        const remote = await getSubscriptionStatus(session);
        return normalizeStatus(remote, session);
      } catch (error) {
        console.warn("Falling back to mock subscription status", error);
        return buildMockStatus(session);
      }
    },
    enabled: hasValidSession(session),
    staleTime: 60_000,
    placeholderData: () => buildMockStatus(session)
  });
}

export function useSubscriptionPlans() {
  const { session } = useSession();
  return useQuery({
    queryKey: ["subscription-plans"],
    queryFn: async () => {
      try {
        const remote = await listSubscriptionPlans(session);
        return enrichPlans(remote);
      } catch (error) {
        console.warn("Falling back to mock subscription plans", error);
        return enrichPlans();
      }
    },
    staleTime: 5 * 60_000,
    placeholderData: () => enrichPlans()
  });
}
