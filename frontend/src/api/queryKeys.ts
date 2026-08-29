/** Shared keys for queries whose data is consumed by multiple settings/ops views. */
export const queryKeys = {
  rooms: (hotelId: number | null) => ["rooms", hotelId] as const,
  roomCategories: (hotelId: number | null) => ["room-categories", hotelId] as const,
  apiKeys: (hotelId: number | null) => ["api-keys", hotelId] as const,
  integrations: (hotelId: number | null) => ["integrations", hotelId] as const
};
