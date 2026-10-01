import { expect, test, type Page } from "@playwright/test";
import {
  completeStepUpPrompt,
  issueStepUpTicket,
  loginAsStepUpOwner,
  stepUpAuthHeaders
} from "./support/step-up-owner";

const backendURL = (process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040").replace(/\/$/, "");

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
const otaRecordingRoles = [
  {
    label: "receptionist",
    email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
    password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!"
  },
  {
    label: "manager",
    email: process.env.E2E_MANAGER_EMAIL || "manager@e2e.com",
    password: process.env.E2E_MANAGER_PASSWORD || "E2eManager1234!"
  }
];

const localIsoDate = (offsetDays: number) => {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
};

async function login(page: Page, user = credentials) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(user.email);
  await page.locator('input[type="password"]').fill(user.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

for (const persona of otaRecordingRoles) {
  test(`${persona.label} can record an OTA price without direct manual-rate permission`, async ({ page }) => {
    const suffix = `${Date.now()}`;
    const guestLastName = `QA-OTA-${persona.label} ${suffix}`;
    const externalId = `BKG-${persona.label.toUpperCase()}-${suffix}`;
    const checkIn = localIsoDate(140);
    const checkOut = localIsoDate(142);

    await login(page, persona);
    await page.goto("/reservas");
    await expect(page.getByTestId("open-manual-ota")).toBeVisible();
    await page.getByTestId("open-manual-ota").click();

    const modal = page.getByTestId("manual-ota-modal");
    const form = modal.locator("form");
    await form.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
    await form.getByPlaceholder("Nombre").fill("Huésped");
    await form.getByPlaceholder("Apellido").fill(guestLastName);
    await form.getByLabel("Tipo de documento").selectOption("DNI");
    await form.getByPlaceholder("Documento").fill(`QAOTA-${suffix}`);

    const categorySelect = form.locator("label").filter({ hasText: "Categoría" }).locator("select");
    const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
    await expect(categoryOption).toHaveCount(1);
    await categorySelect.selectOption((await categoryOption.getAttribute("value"))!);
    await form.getByLabel("Check-in", { exact: true }).fill(checkIn);
    await form.getByLabel("Check-out", { exact: true }).fill(checkOut);
    await form.locator("label").filter({ hasText: "Canal" }).locator("select").selectOption("booking");
    await form.locator("label").filter({ hasText: "ID externo" }).locator("input").fill(externalId);
    await form.locator("label").filter({ hasText: "Monto en pesos" }).locator("input").fill("391000");
    await form.getByRole("button", { name: "Guardar reserva de OTA", exact: true }).click();

    const successPanel = modal.getByRole("status");
    await expect(successPanel).toContainText("guardada en ARS", { timeout: 10_000 });
    await expect(successPanel).toContainText("391.000");
    await expect(successPanel).toContainText("No hay una conversión automática configurada");
  });
}

test("owner can revoke OTA recording for receptionist and the UI hides the entry", async ({ page, request }, testInfo) => {
  test.setTimeout(90_000);
  const receptionist = otaRecordingRoles.find((persona) => persona.label === "receptionist")!;
  const ownerSession = await loginAsStepUpOwner(page, "rbac", testInfo.project.name);
  let lastTotpStep = ownerSession.lastTotpStep;
  let overrideVersion: number | null = null;
  const headers = stepUpAuthHeaders(ownerSession.auth);

  try {
    await page.goto("/settings/permissions");
    const prompt = page.getByRole("dialog", { name: "Confirmá que sos vos" });
    await expect(prompt).toBeVisible();
    lastTotpStep = await completeStepUpPrompt(page, lastTotpStep, ownerSession.auth.user.email);

    const otaToggle = page.getByTestId("permission-toggle-receptionist-reservation:ota_record");
    await expect(page.getByTestId("permissions-matrix")).toBeVisible();
    await expect(otaToggle).toBeChecked();
    const overrideResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      // The first 428 is the expected step-up challenge. The client retries
      // the same mutation after MFA; capture that final response so cleanup
      // can restore the override even when this assertion fails later.
      return url.pathname === "/api/permissions/override"
        && response.request().method() === "PUT"
        && response.ok();
    });
    await otaToggle.click();
    lastTotpStep = await completeStepUpPrompt(page, lastTotpStep, ownerSession.auth.user.email);
    const overrideResponse = await overrideResponsePromise;
    expect(overrideResponse.ok(), `Permission override returned ${overrideResponse.status()}: ${await overrideResponse.text()}`).toBeTruthy();
    overrideVersion = (await overrideResponse.json() as { version: number }).version;
    await expect(page.getByText("Override de rol", { exact: true })).toBeVisible();

    await page.context().clearCookies();
    await login(page, receptionist);
    await page.goto("/reservas");
    await expect(page.getByRole("button", { name: "Crear reserva", exact: true })).toBeVisible();
    await expect(page.getByTestId("open-manual-ota")).toHaveCount(0);
  } finally {
    if (overrideVersion !== null) {
      const restoreTicket = await issueStepUpTicket(request, ownerSession.auth, {
        permissionCode: "permissions:manage",
        method: "DELETE",
        path: "/api/permissions/role-overrides/receptionist/reservation:ota_record"
      }, lastTotpStep);
      const restoreResponse = await request.delete(
        `${backendURL}/api/permissions/role-overrides/receptionist/reservation:ota_record?expected_version=${overrideVersion}`,
        { headers: { ...headers, "X-Action-Step-Up-Ticket": restoreTicket.ticket } }
      );
      expect(restoreResponse.ok()).toBeTruthy();
    }
  }
});

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

  await form.getByLabel("Check-in", { exact: true }).fill(checkIn);
  await form.getByLabel("Check-out", { exact: true }).fill(checkOut);

  await form.locator("label").filter({ hasText: "Canal" }).locator("select").selectOption("booking");
  await form.locator("label").filter({ hasText: "ID externo" }).locator("input").fill(externalId);
  // Two independent prices, not a currency converter -- only USD filled
  // here so the canonical total_amount/currency_code ends up in USD.
  await form.locator("label").filter({ hasText: "Monto en dólares" }).locator("input").fill("250");

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
  await form.getByLabel("Check-in", { exact: true }).fill(checkIn);
  await form.getByLabel("Check-out", { exact: true }).fill(checkOut);
  await form.locator("label").filter({ hasText: "Canal" }).locator("select").selectOption("booking");
  await form.locator("label").filter({ hasText: "ID externo" }).locator("input").fill(externalId);
  // Only ARS filled this time -- the resubmission corrects the canonical
  // currency to ARS (upsert path).
  await form.locator("label").filter({ hasText: "Monto en pesos" }).locator("input").fill("300");

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

  await form.getByLabel("Check-in", { exact: true }).fill(checkIn);
  await form.getByLabel("Check-out", { exact: true }).fill(checkOut);

  await form.locator("label").filter({ hasText: "Monto total manual" }).locator("input").fill("180");
  await form.locator("label").filter({ hasText: /^Moneda/ }).locator("select").selectOption("USD");
  await form.getByLabel(/Motivo obligatorio/).fill("Tarifa acordada para la prueba sintética");
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
