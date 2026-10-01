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
  const checkIn = localIsoDate(0);
  const checkOut = localIsoDate(1);

  await login(page);

  // Recepción opera su propia caja (cash:operate) para poder cobrar en efectivo.
  // Otro spec puede haber dejado una caja abierta para el hotel compartido: el
  // botón arranca optimistamente en "Abrir caja" y recién cambia a "Ya hay una
  // caja abierta" cuando resuelve GET /api/cash-register/sessions, así que hay
  // que esperar esa respuesta antes de decidir si corresponde abrir una nueva.
  const sessionsResponse = page.waitForResponse(
    (response) => response.url().includes("/api/cash-register/sessions") && response.request().method() === "GET"
  );
  await page.goto("/caja");
  await sessionsResponse;
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
  await expect(page.getByLabel("Check-in para disponibilidad", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Check-out para disponibilidad", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Check-in", { exact: true })).toBeVisible();

  await reservationForm.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
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

  await reservationForm.getByLabel("Check-in", { exact: true }).fill(checkIn);
  await reservationForm.getByLabel("Check-out", { exact: true }).fill(checkOut);

  const createReservationButton = reservationForm.getByRole("button", { name: "Crear", exact: true });
  await expect(createReservationButton).toBeEnabled();
  const [createResponse] = await Promise.all([
    page.waitForResponse((res) => res.url().includes("/api/reservations/") && res.request().method() === "POST"),
    createReservationButton.click()
  ]);
  await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();
  const created = await createResponse.json();
  const reservationId: number = created.id;
  const confirmationCode: string = created.confirmation_code;
  expect(reservationId).toBeGreaterThan(0);

  const reservationTable = page.locator("table").filter({ hasText: "Código" });
  const reservationRow = reservationTable.locator("tbody tr").filter({ hasText: confirmationCode });
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

  // B3: check-in ocurre después de cobrar el saldo. La reserva rápida creada
  // arriba (alta rápida) sólo carga nombre/documento -- le faltan los datos
  // nuevos y obligatorios (lugar/país de nacimiento, estado civil, profesión),
  // así que el drawer debe mostrar el formulario de captura antes de dejar
  // avanzar el check-in, no un 400 después. B3.1 (check-in parcial) y B3.5
  // (acompañante) se ejercitan en el mismo paso, con el mismo request que
  // guarda los datos.
  await page.goto(`/reservas?reserva=${reservationId}`);
  const drawer = page.getByRole("dialog", { name: confirmationCode });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByText("Pago completo", { exact: true })).toBeVisible();

  const captureForm = drawer.getByTestId("checkin-capture-form");
  await expect(captureForm).toBeVisible();
  await expect(captureForm).toContainText("Completá el lugar de nacimiento.");
  await captureForm.getByLabel("Lugar de nacimiento").fill("Rosario");
  await captureForm.getByLabel("País de nacimiento").fill("Argentina");
  await captureForm.getByLabel("Estado civil").fill("Soltero/a");
  await captureForm.getByLabel("Profesión").fill("Recepcionista QA");

  await drawer.getByLabel("Nombre del acompañante").fill("Acompañante");
  await drawer.getByLabel("Apellido del acompañante").fill(guestLastName);
  await drawer.getByRole("button", { name: "Agregar", exact: true }).click();
  await expect(drawer.getByText(`Acompañante ${guestLastName}`, { exact: false })).toBeVisible();

  await drawer.getByRole("button", { name: "Check-in parcial", exact: true }).click();
  await expect(drawer.getByText("Check-in parcial registrado.", { exact: true })).toBeVisible();
  await expect(drawer.getByText("Pre check-in", { exact: true })).toBeVisible();
  // The capture form only shows while data is missing -- it's now saved.
  await expect(captureForm).toHaveCount(0);

  await page.route(/\/api\/checkin\/\d+$/, async (route) => {
    if (route.request().method() === "POST") {
      await new Promise((resolve) => setTimeout(resolve, 800));
    }
    await route.continue();
  });
  await drawer.getByRole("button", { name: "Confirmar check-in", exact: true }).click();
  await expect(drawer.getByTestId("drawer-action-pending")).toContainText("Registrando el check-in");
  await expect(drawer.getByText("Check-in registrado.", { exact: true })).toBeVisible();
  await expect(drawer.getByText("Check-in", { exact: true }).first()).toBeVisible();

  await page.getByRole("button", { name: "Cerrar detalle de reserva" }).click();
  await expect(drawer).not.toBeVisible();

  // Switching to another real reservation must not carry the prior check-in
  // success notice into the new reservation drawer.
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  const secondReservationForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await secondReservationForm.getByTestId("guest-search-input").fill(guestLastName);
  const existingGuest = secondReservationForm
    .getByTestId("guest-search-results")
    .getByRole("button")
    .filter({ hasText: guestLastName })
    .first();
  await expect(existingGuest).toBeVisible();
  await existingGuest.click();
  const secondCategorySelect = secondReservationForm.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const secondCategoryOption = secondCategorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await secondCategorySelect.selectOption((await secondCategoryOption.getAttribute("value"))!);
  await secondReservationForm.getByLabel("Check-in", { exact: true }).fill(localIsoDate(70));
  await secondReservationForm.getByLabel("Check-out", { exact: true }).fill(localIsoDate(72));
  const [secondCreateResponse] = await Promise.all([
    page.waitForResponse((response) => response.url().includes("/api/reservations/") && response.request().method() === "POST"),
    secondReservationForm.getByRole("button", { name: "Crear", exact: true }).click()
  ]);
  const secondReservation = await secondCreateResponse.json();
  await page.getByRole("searchbox", { name: "Buscar reserva" }).fill(secondReservation.confirmation_code);
  const secondSearchResult = page.getByTestId("reservation-search-results").getByRole("button", {
    name: new RegExp(secondReservation.confirmation_code)
  });
  await expect(secondSearchResult).toBeVisible();
  await secondSearchResult.click();
  const secondDrawer = page.getByRole("dialog", { name: secondReservation.confirmation_code });
  await expect(secondDrawer).toBeVisible();
  await expect(secondDrawer.getByText("Check-in registrado.", { exact: true })).toHaveCount(0);
  await secondDrawer.getByRole("button", { name: "Cancelar", exact: true }).click();
  await expect(secondDrawer.getByText("Reserva cancelada.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Cerrar detalle de reserva" }).click();

  // Cargar un consumo (minibar) desde la Ficha: reception tiene reservation:charge.
  const checkedInRow = reservationTable.locator("tbody tr").filter({ hasText: confirmationCode });
  await checkedInRow.getByRole("button", { name: "Ficha", exact: true }).first().click();
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
  const chargedRow = reservationTable.locator("tbody tr").filter({ hasText: confirmationCode });
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
  const settledRow = reservationTable.locator("tbody tr").filter({ hasText: confirmationCode });
  await settledRow.getByRole("button", { name: "Check-out", exact: true }).click();
  await expect(page.getByText("Check-out registrado", { exact: true })).toBeVisible();

  // Dejar la caja compartida del hotel E2E cerrada: otros specs (p.ej.
  // zz-cash-control-journey.spec.ts) asumen que pueden decidir libremente
  // si abren una caja nueva, y una caja abierta con saldo dejada acá rompe
  // esa decisión para el siguiente spec que corra.
  await page.goto("/caja");
  const closeCashForm = page.locator("form").filter({ hasText: "Cerrar caja" });
  const expectedBalanceLabel = closeCashForm.getByText(/Saldo esperado:/);
  await expect(expectedBalanceLabel).not.toContainText("$ 0,00");
  const expectedBalanceText = await expectedBalanceLabel.innerText();
  const expectedBalance = Number(expectedBalanceText.replace(/[^0-9,.-]/g, "").replace(/\./g, "").replace(",", "."));
  expect(expectedBalance).toBeGreaterThan(0);
  await closeCashForm.locator('input[type="number"]').fill(String(expectedBalance));
  await closeCashForm.getByRole("button", { name: "Cerrar caja", exact: true }).click();
  await expect(page.getByText("Caja cerrada.", { exact: true })).toBeVisible();
});
