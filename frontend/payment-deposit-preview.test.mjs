import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const page = await readFile(new URL("src/views/protected/ReservationsPage.tsx", import.meta.url), "utf8");

test("foreign-currency deposit preview does not relabel the reservation balance when FX is unavailable", () => {
  assert.match(
    page,
    /const requestedDepositPreview = paymentAmountInput\.trim\(\)\s*\? Number\(paymentAmountInput\)\s*:\s*convertReservationToTender\(suggestedDepositAmount\);/
  );
  assert.match(page, /depositAmountPreview === null\s*\?\s*t\("page\.form\.registerDeposit"\)/);
});
