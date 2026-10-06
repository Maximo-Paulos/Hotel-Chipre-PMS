// Block end dates are exclusive in the availability overlap checks.
export const isRoomBlockCurrentOrUpcoming = (block, today) =>
  !block.ends_at || block.ends_at > today;
