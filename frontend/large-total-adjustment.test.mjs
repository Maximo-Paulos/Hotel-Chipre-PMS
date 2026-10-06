import test from "node:test";
import assert from "node:assert/strict";

import { isLargeTotalAdjustment } from "./src/utils/largeTotalAdjustment.mjs";

test("large total adjustments are flagged at fifty percent of the current amount", () => {
  assert.equal(isLargeTotalAdjustment(85000, 10000), true);
  assert.equal(isLargeTotalAdjustment(85000, 127500), true);
  assert.equal(isLargeTotalAdjustment(85000, 50000), false);
});

test("large total adjustment guard ignores missing, negative, and zero baselines", () => {
  assert.equal(isLargeTotalAdjustment(0, 1000000), true);
  assert.equal(isLargeTotalAdjustment(0, 0), false);
  assert.equal(isLargeTotalAdjustment(85000, Number.NaN), false);
  assert.equal(isLargeTotalAdjustment(85000, -1), false);
});
