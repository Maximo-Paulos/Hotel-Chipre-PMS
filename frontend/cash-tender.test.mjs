import assert from "node:assert/strict";
import test from "node:test";

import { calculateCashTender, calculateCashTip, formatCashTenderAmount } from "./src/utils/cashTender.mjs";

test("blank cash tender records the exact amount and no change", () => {
  assert.deepEqual(calculateCashTender("", 18.93), {
    valid: true,
    reason: null,
    receivedAmount: 18.93,
    changeAmount: 0,
    amountEntered: false
  });
});

test("cash tender validates underpayment and calculates change to the cent", () => {
  assert.equal(calculateCashTender("18.92", 18.93).reason, "insufficient");
  assert.deepEqual(calculateCashTender("20", 18.93), {
    valid: true,
    reason: null,
    receivedAmount: 20,
    changeAmount: 1.07,
    amountEntered: true
  });
});

test("cash tender rejects invalid and fractional-cent values", () => {
  assert.equal(calculateCashTender("abc", 18.93).reason, "invalid_received");
  assert.equal(calculateCashTender("18.931", 18.93).reason, "invalid_received");
  assert.equal(calculateCashTender("0", 18.93).reason, "invalid_received");
});

test("cash tips are opt-in and reduce the guest's change without changing the amount due", () => {
  assert.deepEqual(calculateCashTip("", 13.5), {
    valid: true,
    reason: null,
    tipAmount: 0,
    changeAmount: 13.5
  });
  assert.deepEqual(calculateCashTip("13.50", 13.5), {
    valid: true,
    reason: null,
    tipAmount: 13.5,
    changeAmount: 0
  });
  assert.deepEqual(calculateCashTip("5", 13.5), {
    valid: true,
    reason: null,
    tipAmount: 5,
    changeAmount: 8.5
  });
});

test("cash tips cannot exceed change and must use valid cent amounts", () => {
  assert.equal(calculateCashTip("13.51", 13.5).reason, "exceeds_change");
  assert.equal(calculateCashTip("bad", 13.5).reason, "invalid_tip");
  assert.equal(calculateCashTip("1.001", 13.5).reason, "invalid_tip");
  assert.equal(calculateCashTip("1", -1).reason, "invalid_change");
});

test("cash tender formatting preserves cents and the selected locale for every currency", () => {
  assert.ok(formatCashTenderAmount(12.5, "ARS", "es-AR").includes("12,50"));
  assert.ok(formatCashTenderAmount(12.5, "ARS", "en-US").includes("12.50"));
  assert.ok(formatCashTenderAmount(12.5, "JPY", "es-AR").includes("12,50"));
});
