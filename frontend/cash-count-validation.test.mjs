import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { transformSync } from "esbuild";

const source = readFileSync(new URL("./src/utils/cashCountValidation.ts", import.meta.url), "utf8");
const { code } = transformSync(source, { loader: "ts", format: "esm" });
const { MAX_CASH_COUNT, parseCashCount } = await import(
  `data:text/javascript;base64,${Buffer.from(code).toString("base64")}`
);

test("cash count requires an explicit numeric value while allowing zero", () => {
  assert.equal(parseCashCount(""), null);
  assert.equal(parseCashCount("  "), null);
  assert.equal(parseCashCount("0"), 0);
  assert.equal(parseCashCount("0.00"), 0);
});

test("cash count accepts valid non-negative amounts and rejects invalid values", () => {
  assert.equal(parseCashCount("1234.56"), 1234.56);
  assert.equal(parseCashCount(".50"), 0.5);
  assert.equal(parseCashCount(String(MAX_CASH_COUNT)), MAX_CASH_COUNT);
  for (const value of ["-0.01", "NaN", "Infinity", "1.001", "1e3", "10000000000.00"]) {
    assert.equal(parseCashCount(value), null, `accepted invalid cash count ${value}`);
  }
});
