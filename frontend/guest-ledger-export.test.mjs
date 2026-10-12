import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");
const [page, guestApi, spanishText, englishText] = await Promise.all([
  read("src/views/protected/GuestsPage.tsx"),
  read("src/api/guests.ts"),
  read("src/locales/es/guests.json"),
  read("src/locales/en/guests.json")
]);
const spanish = JSON.parse(spanishText);
const english = JSON.parse(englishText);

test("guest ledger export UI is rendered only for guest:export", () => {
  assert.match(page, /const canExportGuestLedger = hasPermission\("guest:export"\)/);
  assert.match(page, /\{canExportGuestLedger \? \(/);
  assert.match(page, /if \(!canExportGuestLedger \|\| ledgerExportInFlightRef\.current\) return/);
});

test("guest ledger date defaults use hotel timezone and send an inclusive end date", () => {
  assert.match(page, /hotelTodayIso\(hotelConfigQuery\.data\?\.hotel_timezone\)/);
  assert.match(page, /addDaysIso\(ledgerToday, -29\)/);
  assert.match(page, /const toDateExclusive = addDaysIso\(effectiveLedgerThroughDate, 1\)/);
  assert.match(guestApi, /from_date: fromDate, to_date: toDateExclusive/);
  assert.match(guestApi, /"Cache-Control": "no-store"/);
});

test("CSV export handles HTTP errors safely and cleans up the temporary download", () => {
  assert.match(guestApi, /apiFetch<Blob>\(`\/api\/guests\/ledger\/export\?/);
  assert.match(guestApi, /responseType: "blob"/);
  assert.match(guestApi, /throw new GuestLedgerExportError\(Number\(error\.status\)\)/);
  assert.match(page, /downloadAnchor\?\.remove\(\)/);
  assert.match(page, /setTimeout\(\(\) => URL\.revokeObjectURL\(urlToRevoke\), 60_000\)/);
  assert.match(page, /role="alert"/);
  assert.match(page, /role="status"/);
});

test("guest export messages are localized with the same English and Spanish keys", () => {
  assert.deepEqual(Object.keys(english.export.errors).sort(), Object.keys(spanish.export.errors).sort());
  for (const key of ["eyebrow", "title", "description", "from", "through", "download", "downloading", "downloaded"]) {
    assert.ok(english.export[key], `English export.${key} is required`);
    assert.ok(spanish.export[key], `Spanish export.${key} is required`);
  }
});
