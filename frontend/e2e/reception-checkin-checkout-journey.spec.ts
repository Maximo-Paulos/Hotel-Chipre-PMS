import { expect, test, type Page } from "@playwright/test";

// Functional journey for the receptionist role: create -> pay -> check-in -> add
// a consumption charge -> check-out blocked by the new pending balance -> pay it
// off -> check-out succeeds. Complements role-journey.spec.ts (which only checks
// UI gating) with the real front-desk flow end to end, using the receptionist
// persona instead of owner.
const receptionist = {
  email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
  password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!"
};

const localIsoDate = (offsetDays: number) => {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
};

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(receptionist.email);
  await page.locator('input[type="password"]').fill(receptionist.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
  await expect(page.getByTestId("session-role")).toHaveText("Recepción");
}

test("receptionist runs the full check-in / checkout journey with a pending-balance charge", async ({ page }) => {
  const suffix = Date.now().toString();
  const guestLastName = `QA-Recepcion ${suffix}`;
  const checkIn = localIsoDate(40);
  const checkOut = localIsoDate(42);

  await login(page);

  // Recepción opera su propia caja (cash:operate) para poder cobrar en efectivo.
  await page.goto("/caja");
  const openingForm = page.locator("form").filter({ hasText: "Saldo inicial" }).filter({ hasText: "Abrir caja" });
  const openButton = openingForm.getByRole("button", { name: "Abrir caja", exact: true });
  if (await openButton.isVisible().catch(() => false)) {
    const openResponse = page.waitForResponse(
      (response) => response.url().includes("/api/cash-register/sessions") && response.request().method() === "POST"
    );
    await openButton.click();
    const response = await openResponse;
    expect(response.ok(), `open cash session failed: ${response.status()} ${await response.text()}`).toBeTruthy();
    await expect(page.getByText("Caja abierta.", { exact: true })).toBeVisible();
  }

  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  const reservationForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(reservationForm).toBeVisible();

  await reservationForm.getByPlaceholder("Nombre").fill("Huésped");
  await reservationForm.getByPlaceholder("Apellido").fill(guestLastName);
  await reservationForm.getByPlaceholder("Email").fill(`qa.recepcion.${suffix}@example.test`);
  await reservationForm.getByPlaceholder("Teléfono").fill("1112345678");
  await reservationForm.getByLabel("Tipo de documento").selectOption("DNI");
  await reservationForm.getByPlaceholder("Documento").fill(`QA-RECEP-${suffix}`);
  await reservationForm.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = reservationForm.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  const categoryValue = await categoryOption.getAttribute("value");
  expect(categoryValue).toBeTruthy();
  await categorySelect.selectOption(categoryValue!);

  const roomSelect = reservationForm.locator("label").filter({ hasText: "Habitación (opcional)" }).locator("select");
  const roomOption = roomSelect.locator("option").filter({ hasText: "102" });
  await expect(roomOption).toHaveCount(1);
  const roomValue = await roomOption.getAttribute("value");
  expect(roomValue).toBeTruthy();
  await roomSelect.selectOption(roomValue!);

  await reservationForm.locator("label").filter({ hasText: "Check-in" }).locator('input[type="date"]').fill(checkIn);
  await reservationForm.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]').fill(checkOut);

  const createReservationButton = reservationForm.getByRole("button", { name: "Crear", exact: true });
  await expect(createReservationButton).toBeEnabled();
  await createReservationButton.click();
  await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();

  const reservationTable = page.locator("table").filter({ hasText: "Código" });
  const reservationRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await expect(reservationRow).toHaveCount(1);

  // Pagar el total antes de poder hacer check-in (regla de negocio: fully_paid).
  await reservationRow.getByRole("button", { name: "Editar", exact: true }).click();
  const editModal = page.locator("div.fixed").filter({ hasText: "Pagos y balance" });
  const editForm = editModal.locator("form").filter({ hasText: "Pagos y balance" });
  await expect(editForm.getByText("Resumen financiero y acciones rápidas.", { exact: true })).toBeVisible();
  await expect(editForm.getByText("Cargando resumen...", { exact: true })).toHaveCount(0);
  await editForm.getByRole("button", { name: "Pago total", exact: true }).click();
  await expect(page.getByText("Pago completo registrado", { exact: true })).toBeVisible();
  await editModal.getByRole("button", { name: "Cerrar", exact: true }).click();

  const paidRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await paidRow.getByRole("button", { name: "Check-in", exact: true }).click();
  await expect(page.getByText("Check-in registrado", { exact: true })).toBeVisible();

  // Cargar un consumo (minibar) desde la Ficha: reception tiene reservation:charge.
  const checkedInRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await checkedInRow.getByRole("button", { name: "Ficha", exact: true }).click();
  const detailsModal = page.locator("div.fixed").filter({ hasText: "Ficha" });
  await expect(detailsModal.getByRole("heading", { name: /Reserva/ })).toBeVisible();
  const chargeForm = detailsModal.locator("form").filter({ hasText: "Detalle del consumo" });
  await chargeForm.getByPlaceholder("Minibar, desayuno, late checkout...").fill(`QA minibar ${suffix}`);
  await chargeForm.locator('input[type="number"]').fill("500");
  await chargeForm.getByRole("button", { name: "Cargar consumo", exact: true }).click();
  await expect(page.getByText("Consumo cargado a la reserva.", { exact: true })).toBeVisible();
  await expect(detailsModal.getByText(`QA minibar ${suffix}`, { exact: true })).toBeVisible();
  await detailsModal.getByRole("button", { name: "Cerrar", exact: true }).click();

  // Checkout con saldo pendiente: el consumo recién cargado dejó un saldo que
  // reservation.balance_due no ve (sólo compara total_amount vs amount_paid,
  // no BillingAdjustment), así que este saldo lo detecta recién el backend al
  // intentar el check-out, no el chequeo previo del botón.
  const chargedRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await chargedRow.getByRole("button", { name: "Check-out", exact: true }).click();
  await expect(page.getByText(/saldo pendiente de/i)).toBeVisible();
  await expect(page.getByText("Check-out registrado", { exact: true })).toHaveCount(0);

  // El aviso de saldo pendiente abre la ficha de pagos: cobrar el consumo pendiente.
  const balanceEditModal = page.locator("div.fixed").filter({ hasText: "Pagos y balance" });
  const balanceEditForm = balanceEditModal.locator("form").filter({ hasText: "Pagos y balance" });
  await expect(balanceEditForm).toBeVisible();
  await expect(balanceEditForm.getByText("Cargando resumen...", { exact: true })).toHaveCount(0);
  await balanceEditForm.getByRole("button", { name: "Pago total", exact: true }).click();
  await expect(page.getByText("Pago completo registrado", { exact: true })).toBeVisible();
  await balanceEditModal.getByRole("button", { name: "Cerrar", exact: true }).click();

  // Checkout con saldo completo: ahora sí cierra la estadía.
  const settledRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await settledRow.getByRole("button", { name: "Check-out", exact: true }).click();
  await expect(page.getByText("Check-out registrado", { exact: true })).toBeVisible();
});
