import { expect, test, type Page } from "@playwright/test";

import { cleanupEmailOutbox, resetEmailOutbox, waitForCode } from "./support/email-outbox";

// Fase 2 (registro, onboarding y configuración) walked end to end through a
// real browser against the isolated local E2E backend/SQLite database. This
// journey focuses on the parts auth-onboarding-journey.spec.ts does not
// cover: resuming an INCOMPLETE onboarding after logout (no data loss), and
// configuring cash/transfer + real (non-mocked) general/date/category/
// payment-method rates through the actual API, not a mocked one.

test.beforeAll(() => {
  resetEmailOutbox();
});

test.afterAll(() => {
  cleanupEmailOutbox();
});

async function saveAndExpectPath(page: Page, path: string) {
  await page.getByRole("button", { name: "Guardar y seguir", exact: true }).click();
  await page.waitForURL(`**${path}`, { timeout: 15_000 });
}

test("owner can log out mid-onboarding, resume without losing progress, and configure cash/transfer/rates on real backend", async ({
  page
}) => {
  const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const email = `qa-resume-${suffix}@example.test`;
  const password = "QaResume1234!";
  const hotelName = `Hotel QA Resume ${suffix}`;
  const categoryCode = `QR${suffix.replace(/[^a-z0-9]/gi, "").slice(-8).toUpperCase()}`;
  const roomNumber = `8${suffix.replace(/[^0-9]/g, "").slice(-3)}`;

  await page.goto("/register-owner");
  await page.getByLabel("Nombre", { exact: true }).fill("Rita");
  await page.getByLabel("Apellido", { exact: true }).fill("QA");
  await page.getByLabel("Email corporativo", { exact: true }).fill(email);
  await page.getByLabel("Teléfono", { exact: true }).fill("+54 9 11 5555 0202");
  await page.getByLabel("Contraseña", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Crear cuenta y verificar email", exact: true }).click();
  await page.waitForURL("**/verify-email", { timeout: 15_000 });

  const verificationCode = await waitForCode(email, /Verifica tu cuenta/i);
  await page.getByLabel("Codigo", { exact: true }).fill(verificationCode);
  await page.getByRole("button", { name: "Verificar codigo", exact: true }).click();
  await page.waitForURL("**/onboarding", { timeout: 15_000 });

  // Owner step: name/email were auto-persisted from registration, so the
  // wizard should already show them without asking the operator again.
  await expect(page.getByLabel("Nombre completo", { exact: true })).toHaveValue("Rita QA");
  await saveAndExpectPath(page, "/onboarding/identity");

  await page.getByLabel("Nombre del hotel", { exact: true }).fill(hotelName);
  await page.getByLabel("Moneda", { exact: true }).fill("ARS");
  await saveAndExpectPath(page, "/onboarding/categories");

  // --- Log out before completing onboarding (mid-progress) ---
  await page.getByTestId("logout-btn").click();
  await page.waitForURL("**/login", { timeout: 15_000 });

  // --- Log back in: must land on /onboarding, not /dashboard, since it is
  // still incomplete ---
  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/onboarding", { timeout: 15_000 });

  // The identity step must still show the hotel name/currency saved before
  // logging out: onboarding must resume, never ask the operator to redo work.
  await page.goto("/onboarding/identity");
  await expect(page.getByLabel("Nombre del hotel", { exact: true })).toHaveValue(hotelName);
  await expect(page.getByLabel("Moneda", { exact: true })).toHaveValue("ARS");
  await saveAndExpectPath(page, "/onboarding/categories");

  await page.getByRole("button", { name: "+ Agregar categoría", exact: true }).click();
  await page.getByLabel("Nombre de categoría", { exact: true }).fill("Doble QA Resume");
  await page.getByLabel("Código interno", { exact: true }).fill(categoryCode);
  await page.getByLabel("Amenities", { exact: true }).fill("wifi, frigobar, calefacción");
  await page.getByLabel("Precio base por noche", { exact: true }).fill("70000");
  await page.getByLabel("Ocupación máxima", { exact: true }).fill("2");
  await saveAndExpectPath(page, "/onboarding/rooms");

  await page.getByRole("button", { name: "+ Agregar habitación", exact: true }).click();
  await page.getByLabel("Número de habitación", { exact: true }).fill(roomNumber);
  await page.getByLabel("Piso", { exact: true }).fill("2");
  await page.getByRole("combobox", { name: "Categoría", exact: true }).selectOption({
    label: `Doble QA Resume (${categoryCode})`
  });
  await saveAndExpectPath(page, "/onboarding/policy");

  await page.getByLabel("Seña (%)", { exact: true }).fill("25");
  await page.getByLabel("Cancelación gratis hasta (horas)", { exact: true }).fill("24");
  await saveAndExpectPath(page, "/onboarding/payments");

  const mercadoPagoCheckbox = page.getByRole("checkbox", { name: "Mercado Pago", exact: true });
  if (!(await mercadoPagoCheckbox.isChecked())) {
    await mercadoPagoCheckbox.check();
  }
  await saveAndExpectPath(page, "/onboarding/ota");
  await saveAndExpectPath(page, "/onboarding/subscription");
  await saveAndExpectPath(page, "/onboarding/staff");

  await page.getByRole("button", { name: "+ Agregar staff", exact: true }).click();
  await page.getByLabel("Nombre", { exact: true }).fill("Recepción QA Resume");
  await page.getByLabel("Rol", { exact: true }).fill("Reception");
  await page.getByLabel("Email", { exact: true }).fill(`reception-resume-${suffix}@example.test`);
  await saveAndExpectPath(page, "/onboarding/finish");

  await expect(page.getByRole("button", { name: "Marcar onboarding como completo", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Marcar onboarding como completo", exact: true }).click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });

  // --- Cash + bank transfer are hotel-level settings, not part of the
  // wizard: configure them for real, no mocked network. ---
  await page.goto("/settings/hotel");
  const cashCheckbox = page.locator("label").filter({ hasText: "Efectivo" }).locator('input[type="checkbox"]');
  const transferCheckbox = page.locator("label").filter({ hasText: "Transferencia" }).locator('input[type="checkbox"]');
  if (!(await cashCheckbox.isChecked())) await cashCheckbox.check();
  if (!(await transferCheckbox.isChecked())) await transferCheckbox.check();
  await page.getByRole("button", { name: "Guardar cambios", exact: true }).click();
  await expect(page.getByText("Cambios guardados.", { exact: true })).toBeVisible();

  await page.reload();
  await expect(cashCheckbox).toBeChecked();
  await expect(transferCheckbox).toBeChecked();

  // --- Rates: general price + per-date + per-category + per-payment-method,
  // through the real /api/daily-rates backend (rate-calendar.spec.ts only
  // exercises this page against a mocked API). ---
  await page.goto("/operacion/tarifas");
  await expect(page.getByTestId("rate-calendar-category")).toContainText(`Doble QA Resume`);
  await expect(page.getByTestId("rate-calendar-category")).toContainText(categoryCode);

  const today = new Date();
  const from = new Date(today.getFullYear(), today.getMonth() + 1, 1);
  const to = new Date(today.getFullYear(), today.getMonth() + 1, 7);
  const isoDate = (d: Date) => d.toISOString().slice(0, 10);

  const rateForm = page.getByTestId("rate-editor");
  await rateForm.locator('input[type="date"]').first().fill(isoDate(from));
  await rateForm.locator('input[type="date"]').nth(1).fill(isoDate(to));
  await page.getByLabel("Precio base *", { exact: true }).fill("80000");
  await page.getByLabel("Efectivo", { exact: true }).fill("76000");
  await page.getByLabel("Transferencia", { exact: true }).fill("78000");
  await page.getByLabel("Mercado Pago", { exact: true }).fill("82000");
  await page.getByTestId("rate-editor-save").click();
  const savedSummary = page.getByText(/Tarifas guardadas: \d+ creadas, \d+ actualizadas\./);
  await expect(savedSummary).toBeVisible();
  const summaryText = (await savedSummary.textContent()) ?? "";
  const createdOrUpdated = summaryText.match(/(\d+) creadas, (\d+) actualizadas/);
  expect(createdOrUpdated).not.toBeNull();
  const [, createdCount, updatedCount] = createdOrUpdated!;
  expect(Number(createdCount) + Number(updatedCount)).toBeGreaterThan(0);

  // Reload and confirm the per-date, per-category, per-payment-method prices
  // were actually persisted server-side (not just an optimistic UI toast).
  await page.reload();
  await expect(page.getByLabel(`Precio base ${isoDate(from)}`)).toHaveValue("80000", { timeout: 15_000 });
  await expect(page.getByLabel(`Efectivo ${isoDate(from)}`)).toHaveValue("76000");
  await expect(page.getByLabel(`Transferencia ${isoDate(from)}`)).toHaveValue("78000");
  await expect(page.getByLabel(`Mercado Pago ${isoDate(from)}`)).toHaveValue("82000");
});
