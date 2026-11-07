import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("./src/utils/reservationStats.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
}).outputText;
const module = { exports: {} };
vm.runInNewContext(compiled, { module, exports: module.exports });

const { countScheduledDepartures } = module.exports;

test("scheduled departures include pre-check-in stays and exclude cancellations and other dates", () => {
  const reservations = [
    { check_out_date: "2026-11-07", status: "pre_check_in" },
    { check_out_date: "2026-11-07", status: "checked_in" },
    { check_out_date: "2026-11-07", status: "checked_out" },
    { check_out_date: "2026-11-07", status: "cancelled" },
    { check_out_date: "2026-11-07", status: "no_show" },
    { check_out_date: "2026-11-06", status: "checked_out" }
  ];

  assert.equal(countScheduledDepartures(reservations, "2026-11-07"), 3);
});

test("scheduled departures return zero when no active reservation departs today", () => {
  assert.equal(
    countScheduledDepartures(
      [{ check_out_date: "2026-11-06", status: "checked_out" }],
      "2026-11-07"
    ),
    0
  );
});
