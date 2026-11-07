import assert from "node:assert/strict";
import test from "node:test";

import {
  allocationHistoryNoteTranslation,
  allocationHistoryTriggerTranslation
} from "./src/utils/allocationHistoryLabels.ts";
import enReservations from "./src/locales/en/reservations.json" with { type: "json" };
import esReservations from "./src/locales/es/reservations.json" with { type: "json" };

test("allocation movement reasons map internal triggers to localized keys", () => {
  assert.deepEqual(allocationHistoryTriggerTranslation("new_reservation"), {
    key: "page.allocation.triggerReasons.newReservation"
  });
  assert.deepEqual(allocationHistoryTriggerTranslation("manual_api_recalculate"), {
    key: "page.allocation.triggerReasons.manualRecalculate"
  });
  assert.deepEqual(allocationHistoryTriggerTranslation("room_status_maintenance"), {
    key: "page.allocation.triggerReasons.roomStatusMaintenance"
  });
  assert.deepEqual(allocationHistoryTriggerTranslation("overbooking_resolution_2026-11-07"), {
    key: "page.allocation.triggerReasons.overbookingResolution",
    values: { date: "2026-11-07" }
  });
});

test("unknown movement reasons use a safe label", () => {
  assert.deepEqual(allocationHistoryTriggerTranslation("internal_trigger_42"), {
    key: "page.allocation.triggerReasons.unknown"
  });
});

test("generated allocation notes are translated while operator notes remain unchanged", () => {
  assert.deepEqual(allocationHistoryNoteTranslation("Allocation run moved 3 reservation(s)"), {
    key: "page.allocation.generatedMoveNote",
    values: { count: 3 }
  });
  assert.equal(allocationHistoryNoteTranslation("Moved after operator review"), null);
});

test("allocation history keys exist in both supported reservation locales", () => {
  const expectedReasons = [
    "reservationCreatedAutoProposal", "newReservation", "reservationDateChange", "reservationUpdate",
    "reservationRoomMove", "reservationGroupCreated", "manualRecalculate", "manualPreview",
    "manualRoomReallocation", "roomBlockProposal", "roomBlockExtensionProposal", "extensionConflict",
    "roomStatusAvailable", "roomStatusOccupied", "roomStatusMaintenance", "roomStatusBlocked",
    "roomStatusCleaning", "overbookingResolution", "unknown"
  ];

  for (const locale of [enReservations, esReservations]) {
    const allocation = locale.page.allocation;
    for (const reason of expectedReasons) {
      assert.equal(typeof allocation.triggerReasons[reason], "string", `missing trigger label: ${reason}`);
    }
    assert.equal(typeof allocation.generatedMoveNote, "string");
  }
});
