import assert from "node:assert/strict";
import test from "node:test";

import { isRoomBlockCurrentOrUpcoming } from "./src/utils/roomBlockVisibility.mjs";

test("room-block list excludes ended blocks while keeping current and future blocks", () => {
  const today = "2026-10-16";

  assert.equal(isRoomBlockCurrentOrUpcoming({ ends_at: "2026-10-15" }, today), false);
  assert.equal(isRoomBlockCurrentOrUpcoming({ ends_at: today }, today), false, "end date is exclusive");
  assert.equal(isRoomBlockCurrentOrUpcoming({ ends_at: "2026-10-17" }, today), true);
  assert.equal(isRoomBlockCurrentOrUpcoming({ starts_at: "2026-10-20", ends_at: "2026-10-21" }, today), true);
  assert.equal(isRoomBlockCurrentOrUpcoming({ ends_at: null }, today), true);
});
