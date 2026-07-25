import { expect, test, type Page } from "@playwright/test";

// Fase 3 (reservas y tarifas): el precio y la seña que se muestran antes de
// confirmar una reserva tienen que coincidir EXACTAMENTE con lo que termina
// grabado en la reserva. Este spec cubre el caso donde el operador deja la
// "Seña manual" vacía para usar la seña porcentual configurada por el hotel.

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

test("QA- default hotel deposit shown before confirming matches the deposit stored on the reservation", async ({
  page
}) => {
  const suffix = Date.now().toString();
  const guestLastName = `QA-Deposit ${suffix}`;
  const checkIn = localIsoDate(90);
  const checkOut = localIsoDate(92);

  await login(page);
  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();

  const form = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(form).toBeVisible();
  await form.getByPlaceholder("Nombre").fill("Huésped");
  await form.getByPlaceholder("Apellido").fill(guestLastName);
  await form.getByPlaceholder("Email").fill(`${guestLastName.toLowerCase().replaceAll(" ", ".")}@example.test`);
  await form.getByPlaceholder("Teléfono").fill("1112345678");
  await form.getByLabel("Tipo de documento").selectOption("DNI");
  await form.getByPlaceholder("Documento").fill(`QADEP-${suffix}`);
  await form.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = form.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  await categorySelect.selectOption((await categoryOption.getAttribute("value"))!);

  const roomSelect = form.locator("label").filter({ hasText: "Habitación (opcional)" }).locator("select");
  const roomOption = roomSelect.locator("option").filter({ hasText: "101" });
  await expect(roomOption).toHaveCount(1);
  await roomSelect.selectOption((await roomOption.getAttribute("value"))!);

  await form.locator("label").filter({ hasText: "Check-in" }).locator('input[type="date"]').fill(checkIn);
  await form.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]').fill(checkOut);

  // Dejar "Seña manual" vacía a propósito: el operador espera usar la seña
  // porcentual configurada por el hotel, no una seña de $0 ni "sin definir".
  const depositField = form.locator("label").filter({ hasText: "Seña manual" }).locator("input");
  await expect(depositField).toHaveValue("");

  const totalCell = form.locator("p").filter({ hasText: "Total final" }).locator("xpath=following-sibling::p");
  await expect(totalCell).not.toHaveText("Actualizando...", { timeout: 10_000 });
  await expect(totalCell).not.toHaveText("Total no disponible");

  const depositCell = form.locator("p").filter({ hasText: "Seña" }).locator("xpath=following-sibling::p");
  // Bug real: hoy este texto queda en "Por configurar" aunque el backend va a
  // aplicar la seña porcentual del hotel (30% por defecto) al crear la reserva.
  await expect(depositCell).not.toHaveText("Por configurar");
  const previewedDepositText = (await depositCell.textContent())?.trim() ?? "";
  expect(previewedDepositText.length).toBeGreaterThan(0);

  await form.getByRole("button", { name: "Crear", exact: true }).click();
  await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();

  const reservationRow = page.locator("table").filter({ hasText: "Código" }).locator("tbody tr").filter({ hasText: guestLastName });
  await expect(reservationRow).toHaveCount(1);
  await reservationRow.getByRole("button", { name: "Editar", exact: true }).click();

  const editForm = page.locator("form").filter({ hasText: "Pagos y balance" });
  await expect(editForm).toBeVisible();
  const depositRequiredCell = editForm
    .locator("p")
    .filter({ hasText: "Seña requerida" })
    .locator("xpath=following-sibling::p");
  await expect(depositRequiredCell).not.toHaveText("$0", { timeout: 10_000 });

  // El monto de seña mostrado ANTES de confirmar tiene que ser exactamente el
  // mismo que terminó grabado en la reserva (mismo formato, mismo valor).
  await expect(depositRequiredCell).toHaveText(previewedDepositText);
});
