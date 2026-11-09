import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const page = await readFile(new URL("src/views/protected/ReservationsPage.tsx", import.meta.url), "utf8");
const es = JSON.parse(await readFile(new URL("src/locales/es/reservations.json", import.meta.url), "utf8"));
const en = JSON.parse(await readFile(new URL("src/locales/en/reservations.json", import.meta.url), "utf8"));

test("reservation editor labels the collected amount as operational and shows its base-plus-charges breakdown", () => {
  assert.match(page, /t\("page\.form\.summaryOperationalTotal"\)/);
  assert.match(page, /formatMoney\(paymentSummary\.operational_total_amount \?\? paymentSummary\.total_amount \?\? 0, editingCurrencyCode\)/);
  assert.match(page, /data-testid="reservation-operational-total-breakdown"/);
  assert.match(page, /paymentSummary\.billing_adjustment_total != null/);
  assert.match(page, /formatMoney\(paymentSummary\.total_amount \?\? 0, editingCurrencyCode\)/);
  assert.match(page, /formatMoney\(paymentSummary\.billing_adjustment_total, editingCurrencyCode\)/);

  assert.equal(es.page.form.summaryOperationalTotal, "Total operativo");
  assert.equal(es.page.form.summaryBreakdown, "Desglose del total operativo");
  assert.equal(es.page.form.summaryBaseAmount, "Base de la reserva");
  assert.equal(es.page.form.summaryChargesAmount, "Consumos y cargos");
  assert.equal(en.page.form.summaryOperationalTotal, "Operational total");
  assert.equal(en.page.form.summaryBreakdown, "Operational total breakdown");
  assert.equal(en.page.form.summaryBaseAmount, "Reservation base");
  assert.equal(en.page.form.summaryChargesAmount, "Consumption and charges");
});
