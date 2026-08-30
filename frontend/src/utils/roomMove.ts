/**
 * Room-move rules, mirrored from the backend so the UI can block a move
 * before the request instead of after the 403.
 *
 * The tier a move needs is decided by the SHAPE of the move, not by the
 * route: same category, another category with the same capacity, or another
 * category with a different capacity. Tiers are nested -- holding a higher
 * one implies the lower ones.
 *
 * Source of truth: required_room_move_permission() in
 * app/services/reservation_operations_service.py. Keep both in step.
 */

export const PERMISSION_MOVE = "reservation:move";
export const PERMISSION_MOVE_CATEGORY = "reservation:move_category";
export const PERMISSION_MOVE_CAPACITY = "reservation:move_capacity";

/** Lowest tier first. A holder of tier N can perform every move up to N. */
export const MOVE_TIERS = [PERMISSION_MOVE, PERMISSION_MOVE_CATEGORY, PERMISSION_MOVE_CAPACITY] as const;

export type MoveCategory = { id: number; max_occupancy: number };

export const ROOM_MOVE_REASONS = [
  { value: "guest_request", label: "A pedido del huésped" },
  { value: "guest_complaint", label: "Por queja del huésped" },
  { value: "maintenance", label: "Mantenimiento" },
  { value: "operational", label: "Operativo" },
  { value: "upgrade", label: "Upgrade" }
] as const;

export function requiredMovePermission(from: MoveCategory, to: MoveCategory): string {
  if (from.id === to.id) return PERMISSION_MOVE;
  if (from.max_occupancy === to.max_occupancy) return PERMISSION_MOVE_CATEGORY;
  return PERMISSION_MOVE_CAPACITY;
}

const TIER_LABEL: Record<string, string> = {
  [PERMISSION_MOVE]: "Mover reservas",
  [PERMISSION_MOVE_CATEGORY]: "Cambiar de categoría",
  [PERMISSION_MOVE_CAPACITY]: "Cambiar de categoría y capacidad"
};

/**
 * Why this move is not available, or null when it is.
 *
 * Callers show the reason next to the destination instead of hiding it: an
 * operator who cannot move a guest to the suite should still see the suite
 * and read why, rather than wonder where it went.
 */
export function moveBlockedReason(
  from: MoveCategory | undefined,
  to: MoveCategory | undefined,
  hasPermission: (permission: string) => boolean
): string | null {
  if (!from || !to) return null;
  const required = requiredMovePermission(from, to);
  // Nested tiers: any tier at or above the required one authorizes the move.
  const held = MOVE_TIERS.slice(MOVE_TIERS.indexOf(required as (typeof MOVE_TIERS)[number]));
  if (held.some((permission) => hasPermission(permission))) return null;
  return `Requiere el permiso "${TIER_LABEL[required]}"`;
}
