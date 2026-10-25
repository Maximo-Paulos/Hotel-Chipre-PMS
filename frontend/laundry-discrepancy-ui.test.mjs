import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const readSource = (relativePath) => readFile(path.join(frontendRoot, relativePath), "utf8");

test("laundry discrepancy client uses the tenant API routes and an idempotency key for each mutation", async () => {
  const source = await readSource("src/api/laundryVendor.ts");

  for (const contract of [
    'apiFetch<LaundryDiscrepancy[]>("/api/laundry/discrepancies"',
    '/discrepancies/${discrepancyId}/approve',
    '/discrepancies/${discrepancyId}/resolve',
    '/discrepancies/${discrepancyId}/return-to-laundry'
  ]) {
    assert.ok(source.includes(contract), `missing laundry discrepancy API contract: ${contract}`);
  }
  assert.equal((source.match(/"Idempotency-Key": idempotencyKey/gu) ?? []).length, 3);
});

test("discrepancy UI keeps excess identification separate from physical return and gates actions by permission", async () => {
  const source = await readSource("src/views/protected/LaundryPage.tsx");

  assert.match(source, /hasPermission\("laundry:discrepancy_approve"\)/u);
  assert.match(source, /status === "pending_identification"/u);
  assert.match(source, /status === "return_to_laundry"/u);
  assert.match(source, /returnAfterHandover/u);
  assert.match(source, /status === "pending_approval" \|\| discrepancy\.status === "pending_review"/u);
  assert.match(source, /Idempotency-Key|idempotencyKey/u);
  for (const resolution of ["hotel_stock", "return_to_laundry", "vendor_claim", "vendor_custody", "loss", "replacement", "vendor_credit"]) {
    assert.ok(source.includes(`"${resolution}"`), `missing UI resolution ${resolution}`);
  }
});

test("a role with only discrepancy review permission can reach the laundry review route", async () => {
  const [router, appShell] = await Promise.all([
    readSource("src/router.tsx"),
    readSource("src/ui/AppShell.tsx")
  ]);

  assert.match(router, /anyPermission=\{\["laundry:read", "laundry:discrepancy_approve"\]\}/u);
  assert.match(appShell, /requiresAnyPermission: \["laundry:read", "laundry:discrepancy_approve"\]/u);
});

test("credit copy and the discrepancy query key are present in both locales and stay hotel-scoped", async () => {
  const [keys, spanish, english] = await Promise.all([
    readSource("src/api/queryKeys.ts"),
    readSource("src/locales/es/common.json"),
    readSource("src/locales/en/common.json")
  ]);

  assert.match(keys, /"laundry-discrepancies": 1/u);
  assert.match(keys, /"laundry-discrepancies"/u);
  for (const [locale, source] of [["es", spanish], ["en", english]]) {
    const translations = JSON.parse(source);
    assert.ok(translations.laundryDiscrepancies.creditNotSettled, `${locale} credit settlement disclaimer missing`);
    assert.ok(translations.laundryDiscrepancies.permissionRequired, `${locale} permission message missing`);
    for (const status of ["pending_approval", "pending_identification", "pending_review", "pending_resolution", "pending_claim", "awaiting_replacement", "resolved", "return_to_laundry", "returned_to_laundry"]) {
      assert.ok(translations.laundryDiscrepancies.status[status], `${locale} status ${status} missing`);
    }
  }
});
