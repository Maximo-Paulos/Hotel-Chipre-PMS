import { expect, test, type Page } from "@playwright/test";

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

test("owner edits, extends, rejects an overlap and cancels a reservation", async ({ page }) => {
  const suffix = `${Date.now()}`;
  const guestLastName = `Lifecycle ${suffix}`;
  const conflictGuestLastName = `Conflict ${suffix}`;
  const checkIn = localIsoDate(60);
  const originalCheckOut = localIsoDate(62);
  const extendedCheckOut = localIsoDate(64);

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

  const conflictForm = await openReservationForm(page, conflictGuestLastName, localIsoDate(61), localIsoDate(63), {
    expectCreated: false
  });
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
