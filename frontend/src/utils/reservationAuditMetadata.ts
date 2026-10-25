export type ReservationAuditMetadataLabels = {
  arrival: string;
  comment: string;
  empty: string;
};

/** Builds translated audit timeline lines for reservation arrival/comment changes. */
export const reservationAuditMetadataLines = (
  details: Record<string, unknown>,
  labels: ReservationAuditMetadataLabels
): string[] => {
  const before = details.before && typeof details.before === "object" ? details.before as Record<string, unknown> : {};
  const after = details.after && typeof details.after === "object" ? details.after as Record<string, unknown> : {};
  const beforeMetadata = details.metadata && typeof details.metadata === "object" ? details.metadata as Record<string, unknown> : before;
  const afterMetadata = details.metadata && typeof details.metadata === "object" ? details.metadata as Record<string, unknown> : after;
  const lines: string[] = [];

  for (const [field, label] of [["arrival_time_hint", labels.arrival], ["reservation_comment", labels.comment]] as const) {
    const hasChange = Object.prototype.hasOwnProperty.call(beforeMetadata, field) || Object.prototype.hasOwnProperty.call(afterMetadata, field);
    if (!hasChange) continue;
    const previous = beforeMetadata[field] ?? labels.empty;
    const next = afterMetadata[field] ?? labels.empty;
    if (previous === next) continue;
    lines.push(`${label}: ${String(previous)} → ${String(next)}`);
  }

  return lines;
};
