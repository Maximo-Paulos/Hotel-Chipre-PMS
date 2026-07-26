import { expect, test, type Page } from "@playwright/test";

// B4: "Cargar reserva de OTA" + tarifa manual en reserva directa.
//
// One real backend behavior this spec deliberately exercises instead of the
// plan's original assumption: POST /api/reservations/manual-ota is an UPSERT
// keyed by (channel, external_id) -- app/services/ota_manual_service.py
// create_or_update_manual_ota_reservation updates the existing reservation on
// a repeat submission, it does not reject it as a duplicate. There is no
// "duplicate ID externo" error to assert here; the second case below proves
// the upsert instead.
//
// Both fixture categories (seeded by scripts/seed_e2e_backend.py) use plain
// DailyRate pricing with no rate_plan/OTACurrencyRate configured, so
// fx_rate_snapshot legitimately stays null for every case here -- the UI must
// show the "no automatic conversion configured" explanation, not a blank or
// a lie about a cotización that was never computed.

const credentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

const localIsoDate = (offsetDays: number) => {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
};

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

test("cargar reserva de Booking en USD, ver conversion y reenviar el mismo ID externo actualiza en vez de duplicar", async ({
  page
}) => {
  const suffix = `${Date.now()}`;
  const guestLastName = `QA-OTA ${suffix}`;
  const externalId = `BKG-E2E-${suffix}`;
  const checkIn = localIsoDate(120);
  const checkOut = localIsoDate(122);

  await login(page);
  await page.goto("/reservas");
  await page.getByRole("button", { name: "Cargar reserva de OTA", exact: true }).click();

  const modal = page.getByTestId("manual-ota-modal");
  const form = modal.locator("form");
  await expect(form).toBeVisible();

  await form.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
  await form.getByPlaceholder("Nombre").fill("Huésped");
  await form.getByPlaceholder("Apellido").fill(guestLastName);
  await form.getByLabel("Tipo de documento").selectOption("DNI");
  await form.getByPlaceholder("Documento").fill(`QAOTA-${suffix}`);

  const categorySelect = form.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  await categorySelect.selectOption((await categoryOption.getAttribute("value"))!);

  await form.locator("label").filter({ hasText: "Check-in" }).locator('input[type="date"]').fill(checkIn);
  await form.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]').fill(checkOut);

  await form.locator("label").filter({ hasText: "Canal" }).locator("select").selectOption("booking");
  await form.locator("label").filter({ hasText: "ID externo" }).locator("input").fill(externalId);
  await form.locator("label").filter({ hasText: "Monto total" }).locator("input").fill("250");
  await form.locator("label").filter({ hasText: /^Moneda/ }).locator("select").selectOption("USD");
  await form.locator("label").filter({ hasText: "Ya cobrado" }).locator("input").fill("100");

  await form.getByRole("button", { name: "Guardar reserva de OTA", exact: true }).click();

  const successPanel = modal.getByRole("status");
  await expect(successPanel).toContainText("guardada en USD", { timeout: 10_000 });
  // No rate_plan/OTACurrencyRate configured for this fixture category -- the
  // panel must say so plainly instead of showing a fabricated cotización.
  await expect(successPanel).toContainText("No hay una conversión automática configurada");

  // Re-submit the SAME channel + external_id with a different amount: the
  // backend upserts (see comment above), so this must show the same success
  // panel again -- not an error -- and correct the currency/amount in place.
  await successPanel.getByRole("button", { name: "Cargar otra", exact: true }).click();
  await expect(form).toBeVisible();

  const guestSearchInput = form.getByPlaceholder("Buscar por nombre, documento o email");
  await expect(guestSearchInput).toBeVisible();
  await expect(guestSearchInput).toHaveValue("");
  await form.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
  await form.getByPlaceholder("Nombre").fill("Huésped");
  await form.getByPlaceholder("Apellido").fill(guestLastName);
  await categorySelect.selectOption((await categoryOption.getAttribute("value"))!);
  await form.locator("label").filter({ hasText: "Check-in" }).locator('input[type="date"]').fill(checkIn);
  await form.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]').fill(checkOut);
  await form.locator("label").filter({ hasText: "Canal" }).locator("select").selectOption("booking");
  await form.locator("label").filter({ hasText: "ID externo" }).locator("input").fill(externalId);
  await form.locator("label").filter({ hasText: "Monto total" }).locator("input").fill("300");
  await form.locator("label").filter({ hasText: /^Moneda/ }).locator("select").selectOption("ARS");

  await form.getByRole("button", { name: "Guardar reserva de OTA", exact: true }).click();
  await expect(successPanel).toContainText("guardada en ARS", { timeout: 10_000 });
  await expect(successPanel).toContainText("se actualizó esa reserva en vez de crear una nueva");

  await successPanel.getByRole("button", { name: "Cerrar", exact: true }).click();
  await expect(modal).toBeHidden();

  // Exactly one reservation row for this external_id/guest -- the second
  // submission updated it, it did not create a sibling.
  const reservationsTable = page.locator("table").filter({ hasText: "Código" });
  await expect(reservationsTable.locator("tbody tr").filter({ hasText: guestLastName })).toHaveCount(1);
});

test("tarifa manual en reserva directa muestra la moneda usada aunque no haya conversion automatica", async ({ page }) => {
  const suffix = `${Date.now()}`;
  const guestLastName = `QA-ManualRate ${suffix}`;
  const checkIn = localIsoDate(130);
  const checkOut = localIsoDate(132);

  await login(page);
  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();

  const form = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(form).toBeVisible();
  await form.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
  await form.getByPlaceholder("Nombre").fill("Huésped");
  await form.getByPlaceholder("Apellido").fill(guestLastName);
  await form.getByLabel("Tipo de documento").selectOption("DNI");
  await form.getByPlaceholder("Documento").fill(`QAMAN-${suffix}`);
  await form.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = form.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  await categorySelect.selectOption((await categoryOption.getAttribute("value"))!);

  await form.locator("label").filter({ hasText: "Check-in" }).locator('input[type="date"]').fill(checkIn);
  await form.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]').fill(checkOut);

  await form.locator("label").filter({ hasText: "Monto total manual" }).locator("input").fill("180");
  await form.locator("label").filter({ hasText: /^Moneda/ }).locator("select").selectOption("USD");
  await expect(form.getByText("No se usa la cotización automática de Tarifas para esta reserva.")).toBeVisible();

  // Manual pricing skips the quote_token gate -- the button must not be
  // stuck waiting on a cotización that this reservation is not using.
  await expect(form.getByRole("button", { name: "Crear", exact: true })).toBeEnabled();
  await form.getByRole("button", { name: "Crear", exact: true }).click();

  const resultPanel = form.getByRole("status");
  await expect(resultPanel).toContainText("creada en USD", { timeout: 10_000 });
  await expect(resultPanel).toContainText("No hay una conversión automática configurada");

  await resultPanel.getByRole("button", { name: "Cerrar", exact: true }).click();
  await expect(form).toBeHidden();

  const reservationRow = page.locator("table").filter({ hasText: "Código" }).locator("tbody tr").filter({ hasText: guestLastName });
  await expect(reservationRow).toHaveCount(1);
  await reservationRow.getByRole("button", { name: "Cancelar", exact: true }).click();
  await expect(page.getByText("Reserva cancelada", { exact: true })).toBeVisible();
});
