import { expect, test, type Page, type TestInfo } from "@playwright/test";

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

// The 3 webkit-*-business Apple device projects share one SQLite database
// and run this exact spec concurrently, pinning the same room 101 for the
// same relative dates. A per-project date salt gives each device project
// its own calendar days so the room booking can never race, instead of
// relying on timing between a create and a later cleanup cancel.
const projectDateSalt = (testInfo: TestInfo) => {
  const name = testInfo.project.name;
  if (name.includes("pro-max")) return 300;
  if (name.includes("iphone-se")) return 200;
  if (name.includes("iphone-15")) return 100;
  return 0;
};

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

async function openReservationForm(
  page: Page,
  lastName: string,
  checkIn: string,
  checkOut: string,
  options: { expectCreated?: boolean } = {}
) {
  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  const form = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(form).toBeVisible();
  await form.getByPlaceholder("Nombre").fill("Huésped");
  await form.getByPlaceholder("Apellido").fill(lastName);
  await form.getByPlaceholder("Email").fill(`${lastName.toLowerCase().replaceAll(" ", ".")}@example.test`);
  await form.getByPlaceholder("Teléfono").fill("1112345678");
  await form.getByLabel("Tipo de documento").selectOption("DNI");
  await form.getByPlaceholder("Documento").fill(`LIFECYCLE-${Date.now()}`);
  await form.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = form.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  const categoryValue = await categoryOption.getAttribute("value");
  expect(categoryValue).toBeTruthy();
  await categorySelect.selectOption(categoryValue!);

  const roomSelect = form.locator("label").filter({ hasText: "Habitación (opcional)" }).locator("select");
  const roomOption = roomSelect.locator("option").filter({ hasText: "101" });
  await expect(roomOption).toHaveCount(1);
  const roomValue = await roomOption.getAttribute("value");
  expect(roomValue).toBeTruthy();
  await roomSelect.selectOption(roomValue!);
  await form.locator("label").filter({ hasText: "Check-in" }).locator('input[type="date"]').fill(checkIn);
  await form.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]').fill(checkOut);
  await expect(form.getByRole("button", { name: "Crear", exact: true })).toBeEnabled();
  await form.getByRole("button", { name: "Crear", exact: true }).click();
  if (options.expectCreated !== false) {
    await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();
  }
  return form;
}

test("owner preserves availability dates after querying a category", async ({ page }) => {
  const checkIn = localIsoDate(30);
  const checkOut = localIsoDate(32);

  await login(page);
  await page.goto("/reservas");

  const categorySelect = page.getByRole("combobox", { name: "Categoría", exact: true });
  await expect(categorySelect).toHaveCount(1);
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  const categoryValue = await categoryOption.getAttribute("value");
  expect(categoryValue).toBeTruthy();
  await categorySelect.selectOption(categoryValue!);

  const checkInField = page.getByRole("textbox", { name: "Check-in", exact: true });
  const checkOutField = page.getByRole("textbox", { name: "Check-out", exact: true });
  await expect(checkInField).toHaveCount(1);
  await expect(checkOutField).toHaveCount(1);
  await checkInField.fill(checkIn);
  await checkInField.press("Tab");
  await checkOutField.fill(checkOut);
  await checkOutField.press("Tab");

  const availabilityButton = page.getByRole("button", { name: "Consultar", exact: true });
  await expect(availabilityButton).toHaveCount(1);
  await availabilityButton.click();
  await expect(page.getByText(/Disponibles: \d+ habitaciones/, { exact: false })).toBeVisible();
  await expect(checkInField).toHaveValue(checkIn);
  await expect(checkOutField).toHaveValue(checkOut);
});

test("owner edits, extends, rejects an overlap and cancels a reservation", async ({ page }, testInfo) => {
  const salt = projectDateSalt(testInfo);
  // WebKit clamps Date.now() precision, so concurrent device projects can
  // get the exact same millisecond suffix. Append the (already per-project
  // unique) date salt to keep guest names unique too.
  const suffix = `${Date.now()}-${salt}`;
  const guestLastName = `Lifecycle ${suffix}`;
  const conflictGuestLastName = `Conflict ${suffix}`;
  // Offset 150, not 60: payment-journey-full-matrix.spec.ts pins room-agnostic
  // reservations across localIsoDate(60..70) and never cancels them, so that
  // range is permanently occupied for the rest of a full chromium run.
  const checkIn = localIsoDate(150 + salt);
  const originalCheckOut = localIsoDate(152 + salt);
  const extendedCheckOut = localIsoDate(154 + salt);

  await login(page);
  await openReservationForm(page, guestLastName, checkIn, originalCheckOut);

  const reservationTable = page.locator("table").filter({ hasText: "Código" });
  const reservationRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await expect(reservationRow).toHaveCount(1);
  await reservationRow.getByRole("button", { name: "Editar", exact: true }).click();

  const editForm = page.locator("form").filter({ hasText: "Pagos y balance" });
  await expect(editForm).toBeVisible();
  const editCheckOut = editForm.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]');
  await editCheckOut.fill(extendedCheckOut);
  await editForm.getByRole("button", { name: "Guardar cambios", exact: true }).click();
  await expect(page.getByText("Reserva actualizada", { exact: true })).toBeVisible();
  await expect(reservationTable.locator("tbody tr").filter({ hasText: guestLastName })).toContainText(extendedCheckOut);

  const conflictForm = await openReservationForm(
    page,
    conflictGuestLastName,
    localIsoDate(151 + salt),
    localIsoDate(153 + salt),
    { expectCreated: false }
  );
  const conflictModal = page.locator("div.fixed").filter({ hasText: "Datos de la reserva" });
  const conflictError = conflictModal.getByText(/Room 101 is not available for the requested dates/i);
  await expect(conflictError).toBeVisible();
  await expect(reservationTable.locator("tbody tr").filter({ hasText: conflictGuestLastName })).toHaveCount(0);
  await conflictForm.getByRole("button", { name: "Cancelar", exact: true }).click();

  const updatedRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  page.once("dialog", (dialog) => dialog.accept());
  await updatedRow.getByRole("button", { name: "Cancelar", exact: true }).click();
  await expect(page.getByText("Reserva cancelada", { exact: true })).toBeVisible();
  await expect(reservationTable.locator("tbody tr").filter({ hasText: guestLastName })).toContainText("Cancelada");
});

test("editing a reservation cannot silently no-op a category/status change through disabled fields", async (
  { page },
  testInfo
) => {
  // Bug real: PATCH /api/reservations/{id} no tiene campos category_id ni
  // status (ver ReservationUpdate en app/schemas/reservation.py), asi que el
  // backend los ignora en silencio y devuelve 200. El selector "Categoria" y
  // "Estado" del formulario de edicion tenian que estar deshabilitados para
  // no sugerir una accion que no hace nada; el cambio de huespedes (un campo
  // que si persiste) tiene que seguir funcionando en el mismo formulario.
  const salt = projectDateSalt(testInfo);
  // WebKit clamps Date.now() precision, so concurrent device projects can
  // get the exact same millisecond suffix. Append the (already per-project
  // unique) date salt to keep guest names unique too.
  const suffix = `${Date.now()}-${salt}`;
  const guestLastName = `QA-EditLock ${suffix}`;
  // Offset 160, not 70: payment-journey-full-matrix.spec.ts pins room-agnostic
  // reservations across localIsoDate(60..70) and never cancels them, so that
  // range is permanently occupied for the rest of a full chromium run.
  const checkIn = localIsoDate(160 + salt);
  const checkOut = localIsoDate(162 + salt);

  await login(page);
  await openReservationForm(page, guestLastName, checkIn, checkOut);

  const reservationTable = page.locator("table").filter({ hasText: "Código" });
  const reservationRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await expect(reservationRow).toHaveCount(1);
  await expect(reservationRow).toContainText("Pendiente");
  await reservationRow.getByRole("button", { name: "Editar", exact: true }).click();

  const editForm = page.locator("form").filter({ hasText: "Pagos y balance" });
  await expect(editForm).toBeVisible();

  const categorySelect = editForm.locator("label").filter({ hasText: "Categoría" }).locator("select");
  await expect(categorySelect).toBeDisabled();
  const statusSelect = editForm.locator("label").filter({ hasText: "Estado" }).locator("select");
  await expect(statusSelect).toBeDisabled();
  await expect(statusSelect).toHaveValue("pending");

  const adultsInput = editForm.locator("label").filter({ hasText: "Adultos" }).locator("input");
  await adultsInput.fill("2");
  await editForm.getByRole("button", { name: "Guardar cambios", exact: true }).click();
  await expect(page.getByText("Reserva actualizada", { exact: true })).toBeVisible();

  // El cambio de huespedes (campo soportado por el backend) se guardo, y el
  // estado sigue siendo "Pendiente" (no quedo en un estado inconsistente por
  // un control que nunca debio ofrecerse como editable).
  await expect(reservationRow).toContainText("Pendiente");

  // Cleanup: this test pins room 101 for localIsoDate(160..162). The WebKit
  // Apple business matrix reruns this exact spec once per device project
  // against the shared database, so leaving this reservation pending would
  // make the next device run fail room availability with a false "Room 101
  // is not available for the requested dates" negative.
  await reservationRow.getByRole("button", { name: "Cancelar", exact: true }).click();
  await expect(page.getByText("Reserva cancelada", { exact: true })).toBeVisible();
});
