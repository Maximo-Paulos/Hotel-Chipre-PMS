import { useGuestActiveRestrictions } from "../hooks/useGuestRestrictions";
import { useEffectivePermissions } from "../hooks/usePermissions";

type Props = {
  guestId: number;
  hasActiveRestriction?: boolean;
  className?: string;
};

// Small "restricted" indicator for guest rows and the detail header. Guest
// list rows receive a batched ID-only summary; the selected detail header may
// fetch its own restriction data, gated on guest:prohibition_read/manage.
// Reasons are shown only in the detail header to guest:prohibition_manage.
export function GuestRestrictionBadge({ guestId, hasActiveRestriction, className = "" }: Props) {
  const { hasPermission } = useEffectivePermissions();
  const canSeeReason = hasPermission("guest:prohibition_manage");
  const { data, isSuccess } = useGuestActiveRestrictions(guestId, true, {
    enabled: hasActiveRestriction === undefined
  });

  const isRestricted = hasActiveRestriction ?? (isSuccess && Boolean(data?.length));
  if (!isRestricted) return null;

  const reasons = canSeeReason && hasActiveRestriction === undefined
    ? data?.map((restriction) => restriction.reason).join(" · ")
    : null;

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
