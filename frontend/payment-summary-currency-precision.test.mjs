import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const reservationDrawer = await readFile(
  new URL("src/components/ReservationDetailDrawer.tsx", import.meta.url),
  "utf8"
);
const reservationsPage = await readFile(
  new URL("src/views/protected/ReservationsPage.tsx", import.meta.url),
  "utf8"
);
const currencySource = await readFile(new URL("src/utils/currency.ts", import.meta.url), "utf8");
const currencyModuleCode = ts.transpileModule(currencySource, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022
  }
}).outputText;
const { formatMoneyExact } = await import(
  `data:text/javascript;base64,${Buffer.from(currencyModuleCode).toString("base64")}`
);
const normalizeWhitespace = (value) => value.replace(/\s+/g, " ").trim();
const assertSourceMatch = (source, pattern, message) => {
  assert.ok(pattern.test(source), message);
};

test("payment summary currency formatting preserves ARS and USD minor units", () => {
  assert.equal(normalizeWhitespace(formatMoneyExact(41_997.5, "ARS")), "$ 41.997,50");
  assert.equal(normalizeWhitespace(formatMoneyExact(26.75, "USD")), "US$ 26,75");
  assert.equal(normalizeWhitespace(formatMoneyExact(2.5, "ARS")), "$ 2,50");
});

test("reservation payment summaries and transaction listings use exact currency precision", () => {
  assertSourceMatch(
    reservationDrawer,
    /formatMoneyExact\(summary\.amount_paid, currencyCode\)/,
    "the reservation drawer must preserve cents in the paid summary"
  );
  assertSourceMatch(
    reservationDrawer,
    /formatMoneyExact\(operationalBalanceDue \?\? 0, currencyCode\)/,
    "the reservation drawer must preserve cents in the outstanding balance"
  );

  assertSourceMatch(
    reservationsPage,
    /formatMoneyExact\(paymentSummary\.amount_paid \?\? 0, editingCurrencyCode\)/,
    "the reservation editor must preserve cents in the paid summary"
  );
  assertSourceMatch(
    reservationsPage,
    /formatMoneyExact\(paymentSummary\.operational_balance_due \?\? paymentSummary\.balance_due \?\? 0, editingCurrencyCode\)/,
    "the reservation editor must preserve cents in the outstanding balance"
  );
  assertSourceMatch(
    reservationsPage,
    /formatMoneyExact\(detailsSummary\.hotel_received_amount \?\? 0, detailsCurrencyCode\)/,
    "the reservation detail summary must preserve cents in received payments"
  );
  assertSourceMatch(
    reservationsPage,
    /formatMoneyExact\(tx\.amount, tx\.currency\)/,
    "payment options must preserve cents"
  );
  assertSourceMatch(
    reservationsPage,
    /formatMoneyExact\(tx\.gross_amount \?\? tx\.amount, tx\.currency\)/,
    "payment transaction totals must preserve cents"
  );
  assertSourceMatch(
    reservationsPage,
    /formatMoneyExact\(tx\.applied_amount, tx\.applied_currency\)/,
    "cross-currency applied amounts must preserve cents"
  );
});
