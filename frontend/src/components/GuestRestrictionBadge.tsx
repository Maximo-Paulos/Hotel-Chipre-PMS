import { useGuestActiveRestrictions } from "../hooks/useGuestRestrictions";
import { useEffectivePermissions } from "../hooks/usePermissions";

type Props = {
  guestId: number;
  className?: string;
};

// Small "restricted" indicator for guest search/list rows and the guest
// detail header. The underlying query is gated on
// guest:prohibition_read/manage (see useGuestActiveRestrictions) so it never
// fires -- and the badge renders nothing -- for an actor without permission,
// including an actor who 403s the list call. reason/detail are only shown to
// guest:prohibition_manage holders (guest:prohibition_read alone can see
// *that* a restriction exists, not why).
export function GuestRestrictionBadge({ guestId, className = "" }: Props) {
  const { hasPermission } = useEffectivePermissions();
  const canSeeReason = hasPermission("guest:prohibition_manage");
  const { data, isSuccess } = useGuestActiveRestrictions(guestId, true);

  if (!isSuccess || !data || data.length === 0) return null;

  const reasons = canSeeReason ? data.map((restriction) => restriction.reason).join(" · ") : null;

  return (
    <span
      title={reasons ?? "Alojamiento restringido"}
      data-testid={`guest-restriction-badge-${guestId}`}
      className={`inline-flex max-w-full items-center gap-1 truncate rounded-full border border-red-200 bg-red-50 px-2 py-0.5 text-[11px] font-semibold text-red-800 ${className}`}
    >
      Restringido{reasons ? `: ${reasons}` : ""}
    </span>
  );
}
