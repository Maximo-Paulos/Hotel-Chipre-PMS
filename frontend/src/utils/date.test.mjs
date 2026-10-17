import assert from "node:assert/strict";
import test from "node:test";

import { formatHotelDate, formatHotelTime, startOfCurrentMonthIso, startOfCurrentWeekIso } from "./date.ts";

test("formats UTC timestamps in the hotel's local 24-hour clock", () => {
  assert.equal(
    formatHotelTime("2026-09-28T21:55:19Z", "America/Argentina/Buenos_Aires"),
    "18:55:19"
  );
});

test("formats the trial end date in the hotel local timezone", () => {
  assert.equal(
    formatHotelDate("2026-10-12T23:59:59-03:00", "America/Argentina/Buenos_Aires"),
    "12/10/2026"
  );
});

test("treats legacy naive backend timestamps as UTC", () => {
  assert.equal(
    formatHotelTime("2026-09-28T21:55:19", "America/Argentina/Buenos_Aires"),
    "18:55:19"
  );
});

test("builds report ranges from a supplied business date", () => {
  assert.equal(startOfCurrentWeekIso("2026-10-18"), "2026-10-12");
  assert.equal(startOfCurrentMonthIso("2026-10-18"), "2026-10-01");
});
