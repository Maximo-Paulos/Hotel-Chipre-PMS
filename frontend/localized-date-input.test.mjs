import assert from "node:assert/strict";
import test from "node:test";

import {
  dateInputCursorPosition,
  formatDateInputValue,
  formatDateTimeInputValue,
  maskDateInputValue,
  maskDateTimeInputValue,
  parseDateInputValue,
  parseDateTimeInputValue
} from "./src/utils/localizedDateInput.mjs";

test("date input uses day-first display and preserves ISO values", () => {
  assert.equal(formatDateInputValue("2026-09-30"), "30/09/2026");
  assert.equal(maskDateInputValue("2026-09-30"), "30/09/2026");
  assert.equal(maskDateInputValue("1/9/2026"), "01/09/2026");
  assert.equal(parseDateInputValue("30/09/2026"), "2026-09-30");
  assert.equal(parseDateInputValue("29/02/2024"), "2024-02-29");
  assert.equal(parseDateInputValue("29/02/2026"), null);
  assert.equal(parseDateInputValue("31/04/2026"), null);
});

test("date-time input uses day-first 24-hour display and local ISO values", () => {
  assert.equal(formatDateTimeInputValue("2026-09-30T16:25"), "30/09/2026 16:25");
  assert.equal(maskDateTimeInputValue("300920261625"), "30/09/2026 16:25");
  assert.equal(maskDateTimeInputValue("2026-09-30T16:25"), "30/09/2026 16:25");
  assert.equal(maskDateTimeInputValue("1/9/2026 6:05"), "01/09/2026 06:05");
  assert.equal(parseDateTimeInputValue("30/09/2026 16:25"), "2026-09-30T16:25");
  assert.equal(parseDateTimeInputValue("30/09/2026 24:00"), null);
  assert.equal(parseDateTimeInputValue("30/09/2026 16:60"), null);
});

test("cursor position follows the digit count after inserting separators", () => {
  assert.equal(dateInputCursorPosition("30/09/2026", 2), 2);
  assert.equal(dateInputCursorPosition("30/09/2026", 3), 4);
  assert.equal(dateInputCursorPosition("30/09/2026", 8), 10);
});
