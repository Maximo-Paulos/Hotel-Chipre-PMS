export type AllocationHistoryTranslation = {
  key: string;
  values?: Record<string, string | number>;
};

const triggerReasonKeys: Record<string, string> = {
  reservation_created_auto_proposal: "reservationCreatedAutoProposal",
  new_reservation: "newReservation",
  reservation_date_change: "reservationDateChange",
  reservation_update: "reservationUpdate",
  reservation_room_move: "reservationRoomMove",
  reservation_group_created: "reservationGroupCreated",
  manual_api_recalculate: "manualRecalculate",
  manual_api_preview: "manualPreview",
  rooms_manual_reallocate: "manualRoomReallocation",
  room_block_proposal: "roomBlockProposal",
  room_block_extension_proposal: "roomBlockExtensionProposal",
  extension_conflict: "extensionConflict"
};

const roomStatusKeys: Record<string, string> = {
  available: "roomStatusAvailable",
  occupied: "roomStatusOccupied",
  maintenance: "roomStatusMaintenance",
  blocked: "roomStatusBlocked",
  cleaning: "roomStatusCleaning"
};

export function allocationHistoryTriggerTranslation(reason: string): AllocationHistoryTranslation {
  const knownKey = triggerReasonKeys[reason];
  if (knownKey) {
    return { key: `page.allocation.triggerReasons.${knownKey}` };
  }

  const roomStatus = /^room_status_(available|occupied|maintenance|blocked|cleaning)$/.exec(reason);
  if (roomStatus) {
    return { key: `page.allocation.triggerReasons.${roomStatusKeys[roomStatus[1]]}` };
  }

  const overbookingResolution = /^overbooking_resolution_(\d{4}-\d{2}-\d{2})$/.exec(reason);
  if (overbookingResolution) {
    return {
      key: "page.allocation.triggerReasons.overbookingResolution",
      values: { date: overbookingResolution[1] }
    };
  }

  return { key: "page.allocation.triggerReasons.unknown" };
}

export function allocationHistoryNoteTranslation(note: string): AllocationHistoryTranslation | null {
  const generatedMoveNote = /^Allocation run moved (\d+) reservation\(s\)$/i.exec(note.trim());
  if (!generatedMoveNote) return null;

  return {
    key: "page.allocation.generatedMoveNote",
    values: { count: Number(generatedMoveNote[1]) }
  };
}
