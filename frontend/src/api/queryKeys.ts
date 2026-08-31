/** Shared keys for queries whose data is consumed by multiple settings/ops views. */
export const queryKeys = {
  rooms: (hotelId: number | null) => ["rooms", hotelId] as const,
  roomCategories: (hotelId: number | null) => ["room-categories", hotelId] as const,
  categories: (hotelId: number | null) => ["categories", hotelId] as const,
  apiKeys: (hotelId: number | null) => ["api-keys", hotelId] as const,
  integrations: (hotelId: number | null) => ["integrations", hotelId] as const,
  reservations: (hotelId: number | null) => ["reservations", hotelId] as const,
  reservation: (hotelId: number | null, reservationId: number) => ["reservation", hotelId, reservationId] as const,
  reservationOperations: (hotelId: number | null, reservationId: number) => [
    "reservation-operations",
    hotelId,
    reservationId
  ] as const,
  paymentSummary: (hotelId: number | null, reservationId?: number) => [
    "payment-summary",
    hotelId,
    reservationId
  ] as const,
  paymentProofs: (hotelId: number | null, reservationId?: number) => [
    "payment-proofs",
    hotelId,
    reservationId
  ] as const,
  cashSessions: (hotelId: number | null) => ["cash-sessions", hotelId] as const,
  cashMovements: (hotelId: number | null, sessionId?: number) => ["cash-movements", hotelId, sessionId] as const,
  cashSummary: (hotelId: number | null, sessionId?: number) => ["cash-summary", hotelId, sessionId] as const,
  reports: (hotelId: number | null, reportType = "all") => ["reports", reportType, hotelId] as const,
  analytics: (hotelId: number | null) => ["analytics", hotelId] as const,
  guests: (hotelId: number | null) => ["guests", hotelId] as const,
  guest: (hotelId: number | null, guestId: number) => ["guest", hotelId, guestId] as const,
  stockItems: (hotelId: number | null) => ["stock-items", hotelId] as const,
  stockLocations: (hotelId: number | null) => ["stock-locations", hotelId] as const,
  hotelConfig: (hotelId: number | null) => ["hotel-config", hotelId] as const,
  users: (hotelId: number | null) => ["users", hotelId] as const
};

export type QueryDomain =
  | "analytics"
  | "cash"
  | "guests"
  | "notifications"
  | "onboarding"
  | "payments"
  | "reservations"
  | "rooms"
  | "security"
  | "settings"
  | "stock"
  | "users";

/**
 * Every operational query must carry its tenant at a known position. Keeping
 * the index here lets invalidation be broad enough to cover every filter while
 * still refusing to touch another hotel's cache.
 */
export const HOTEL_ID_INDEX_BY_QUERY_PREFIX: Readonly<Record<string, number>> = {
  analytics: 1,
  "api-keys": 1,
  categories: 1,
  companies: 1,
  "cash-latest-close-report": 1,
  "cash-movements": 1,
  "cash-sessions": 1,
  "cash-summary": 1,
  "category-daily-rates": 1,
  "company-documents": 1,
  "daily-rates": 1,
  "guest-checkin-validation": 1,
  "guest-quick-profile": 1,
  "guest-restrictions": 1,
  "guest-search": 1,
  "guest-tags": 1,
  guest: 1,
  guests: 1,
  "gemma-chat": 1,
  "gemma-chat-history": 1,
  "gemma-insights": 1,
  "gemma-runtime-status": 1,
  "hotel-config": 1,
  integrations: 1,
  "notification-preferences": 2,
  notifications: 2,
  "laundry-vendor-balance": 1,
  "laundry-vendor-prices": 1,
  "laundry-vendor-settlements": 1,
  "laundry-vendor-spend": 1,
  "laundry-vendors": 1,
  "laundry-remitos": 1,
  "linen-items": 1,
  "linen-locations": 1,
  "linen-summary": 1,
  "payment-link-tests": 1,
  "payment-links": 1,
  "payment-proofs": 1,
  "payment-surcharges": 1,
  "payment-summary": 1,
  "reservation-quote": 1,
  permissions: 2,
  "permissions-catalog": 1,
  "permissions-matrix": 1,
  "permissions-role-profiles": 1,
  "permissions-user-overrides": 1,
  "permissions-users": 1,
  "permissions-visibility-windows": 1,
  "price-periods": 1,
  promotions: 1,
  reservation: 1,
  "reservation-operations": 1,
  "reservation-pending-actions": 1,
  reservations: 1,
  "reports": 2,
  "room-blocks": 1,
  "room-categories": 1,
  "room-movement-groups": 1,
  "room-state-events": 1,
  rooms: 1,
  "rate-calendar": 1,
  "settings-security": 2,
  "settings-sessions": 1,
  stock: 1,
  "stock-consumption-report": 1,
  "stock-current": 1,
  "stock-items": 1,
  "stock-locations": 1,
  "stock-low": 1,
  "stock-movements": 1,
  "stock-reservations": 1,
  "stock-summary": 1,
  subscription: 1,
  users: 1,
  waitlist: 1,
  "occupancy-grid": 1,
  "onboarding-status": 1
};

/** Query prefixes grouped by the server's tenant-scoped invalidation domains. */
export const QUERY_PREFIXES_BY_DOMAIN: Readonly<Record<QueryDomain, readonly string[]>> = {
  analytics: [
    "analytics",
    "companies",
    "reports",
    "room-state-events",
    "gemma-chat",
    "gemma-chat-history",
    "gemma-insights",
    "gemma-runtime-status"
  ],
  cash: ["cash", "cash-register", "cash-sessions", "cash-movements", "cash-summary", "cash-latest-close-report"],
  guests: [
    "guests",
    "guest",
    "guest-tags",
    "guest-quick-profile",
    "guest-search",
    "guest-restrictions",
    "guest-checkin-validation"
  ],
  onboarding: ["onboarding", "onboarding-status"],
  payments: ["payments", "payment-summary", "payment-links", "payment-proofs", "payment-link-tests"],
  reservations: [
    "reservations",
    "reservation",
    "reservation-quote",
    "reservation-operations",
    "reservation-pending-actions",
    "payment-summary",
    "payment-links",
    "payment-proofs",
    "room-movement-groups",
    "occupancy-grid",
    "waitlist"
  ],
  rooms: [
    "rooms",
    "room-categories",
    "categories",
    "room-blocks",
    "room-movement-groups",
    "daily-rates",
    "rate-calendar",
    "category-daily-rates",
    "price-periods",
    "room-state-events",
    "occupancy-grid",
    "reservation-quote"
  ],
  security: ["permissions", "permissions-catalog", "permissions-matrix", "permissions-role-profiles", "permissions-user-overrides", "permissions-users", "permissions-visibility-windows", "settings-security"],
  settings: [
    "hotel-config",
    "permissions-matrix",
    "api-keys",
    "subscription",
    "integrations",
    "companies",
    "company-documents",
    "promotions",
    "payment-surcharges",
    "settings-sessions",
    "notifications",
    "notification-preferences",
    "daily-report-schedules"
  ],
  notifications: ["notifications", "notification-preferences", "daily-report-schedules"],
  stock: [
    "stock",
    "stock-items",
    "stock-locations",
    "stock-low",
    "stock-current",
    "stock-movements",
    "stock-reservations",
    "stock-summary",
    "stock-consumption-report",
    "laundry-vendors",
    "laundry-vendor-prices",
    "laundry-vendor-settlements",
    "laundry-vendor-balance",
    "laundry-vendor-spend",
    "linen-items",
    "linen-locations",
    "linen-summary",
    "laundry-remitos"
  ],
  users: ["users"]
};

export const hotelIdForQueryKey = (queryKey: readonly unknown[]): number | null => {
  const prefix = queryKey[0];
  if (typeof prefix !== "string") return null;
  const index = HOTEL_ID_INDEX_BY_QUERY_PREFIX[prefix];
  const hotelId = index === undefined ? null : queryKey[index];
  return typeof hotelId === "number" && Number.isInteger(hotelId) && hotelId > 0 ? hotelId : null;
};
