type RoomBlockDateRange = { ends_at?: string | null };

export function isRoomBlockCurrentOrUpcoming(block: RoomBlockDateRange, today: string): boolean;
