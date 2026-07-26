import { expect, test, type Locator, type Page } from "@playwright/test";

// E1: the hotel owner reported that assigning a guest to a reservation was a
// raw numeric "ID Huésped" text field -- no way to search by name/DNI, and no
// way to tell two guests with the same name apart before confirming. This
// spec covers the replacement: search-by-name/DNI (same pattern as
// GuestsPage.tsx), a confirmation card (name/email/phone/DNI) before the
// guest is actually assigned, "buscar otro" to back out before confirming,
// the "Huésped rápido" fallback when there's no match, and that editing an
// existing reservation still can't change its guest (guestIdDisabled).

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

async function selectCategoryAndRoom(form: Locator) {
  const categorySelect = form.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  await categorySelect.selectOption((await categoryOption.getAttribute("value"))!);

  const roomSelect = form.locator("label").filter({ hasText: "Habitación (opcional)" }).locator("select");
  const roomOption = roomSelect.locator("option").filter({ hasText: "101" });
  await expect(roomOption).toHaveCount(1);
  await roomSelect.selectOption((await roomOption.getAttribute("value"))!);
}

test("buscar huésped por nombre, confirmar con tarjeta de datos, y respetar guestIdDisabled al editar", async ({
  page
}) => {
  const suffix = `${Date.now()}`;
  const guestLastName = `Buscador ${suffix}`;
  const guestEmail = `buscador.${suffix}@example.test`;
  const guestPhone = "1155667788";
  const guestDocument = `SRCH-${suffix}`;
  const checkInA = localIsoDate(500);
  const checkOutA = localIsoDate(502);
  const checkInB = localIsoDate(505);
  const checkOutB = localIsoDate(507);

  await login(page);
  await page.goto("/reservas");

  // 1) Create the guest once via the "Huésped rápido" fallback, so there is
  // a real match to search for afterwards.
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  const firstForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(firstForm).toBeVisible();
  await firstForm.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
  await firstForm.getByPlaceholder("Nombre").fill("Huésped");
  await firstForm.getByPlaceholder("Apellido").fill(guestLastName);
  await firstForm.getByPlaceholder("Email").fill(guestEmail);
  await firstForm.getByPlaceholder("Teléfono").fill(guestPhone);
  await firstForm.getByLabel("Tipo de documento").selectOption("DNI");
  await firstForm.getByPlaceholder("Documento").fill(guestDocument);
  await firstForm.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();
  // Once assigned, the panel shows a read-only-looking confirm card, not the
  // quick-create fields anymore.
  await expect(firstForm.getByTestId("guest-confirm-card")).toContainText(guestLastName);

  await selectCategoryAndRoom(firstForm);
  await firstForm.locator("label").filter({ hasText: "Check-in" }).locator('input[type="date"]').fill(checkInA);
  await firstForm.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]').fill(checkOutA);
  await expect(firstForm.getByRole("button", { name: "Crear", exact: true })).toBeEnabled();
  await firstForm.getByRole("button", { name: "Crear", exact: true }).click();
  await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Cerrar", exact: true }).last().click();

  // 2) Open a new reservation and search for that guest by (partial) name.
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  const form = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(form).toBeVisible();

  const searchInput = form.getByPlaceholder("Buscar por nombre, documento o email");
  await expect(searchInput).toBeVisible();
  await searchInput.fill("Buscador");

  const results = form.getByTestId("guest-search-results");
  await expect(results).toBeVisible({ timeout: 5_000 });
  const resultButton = results.locator("button").filter({ hasText: guestLastName });
  await expect(resultButton).toBeVisible();
  await expect(resultButton).toContainText(guestDocument);

  await resultButton.click();

  // 3) Confirmation card shows name/email/phone/DNI before assigning.
  const pendingCard = form.getByTestId("guest-confirm-card");
  await expect(pendingCard).toContainText(guestLastName);
  await expect(pendingCard).toContainText(guestEmail);
  await expect(pendingCard).toContainText(guestPhone);
  await expect(pendingCard).toContainText(guestDocument);

  // "Buscar otro" backs out without assigning -- back to the search box.
  await form.getByTestId("guest-search-again-button").click();
  await expect(searchInput).toBeVisible();
  await expect(results).toBeVisible();

  await resultButton.click();
  await expect(pendingCard).toBeVisible();
  await form.getByTestId("guest-confirm-button").click();

  // 4) Confirmed: search UI is gone, replaced by the assigned-guest card.
  await expect(searchInput).toBeHidden();
  const confirmedCard = form.getByTestId("guest-confirm-card");
  await expect(confirmedCard).toContainText(guestLastName);
  await expect(form.getByTestId("guest-change-button")).toBeVisible();

  await selectCategoryAndRoom(form);
  await form.locator("label").filter({ hasText: "Check-in" }).locator('input[type="date"]').fill(checkInB);
  await form.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]').fill(checkOutB);
  await expect(form.getByRole("button", { name: "Crear", exact: true })).toBeEnabled();
  await form.getByRole("button", { name: "Crear", exact: true }).click();
  await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Cerrar", exact: true }).last().click();

  // 5) The reservation table shows the correct (searched, not manually
  // typed) guest name -- proves the confirmed search result's id was the
  // one actually sent to the backend.
  const reservationsTable = page.locator("table").filter({ hasText: "Código" });
  const guestRows = reservationsTable.locator("tbody tr").filter({ hasText: guestLastName });
  await expect(guestRows).toHaveCount(2);

  // 6) Editing an existing reservation must not allow changing the guest
  // (guestIdDisabled): the card shows the assigned guest read-only, with no
  // "buscar otro"/"cambiar" control and no search box.
  await guestRows.first().getByRole("button", { name: "Editar", exact: true }).click();
  const editForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(editForm).toBeVisible();
  await expect(editForm.getByTestId("guest-confirm-card")).toContainText(guestLastName);
  await expect(editForm.getByTestId("guest-change-button")).toHaveCount(0);
  await expect(editForm.getByPlaceholder("Buscar por nombre, documento o email")).toHaveCount(0);
});

test("buscar un huésped sin coincidencias ofrece el fallback de Huésped rápido", async ({ page }) => {
  await login(page);
  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();

  const form = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(form).toBeVisible();

  const searchInput = form.getByPlaceholder("Buscar por nombre, documento o email");
  await searchInput.fill(`Sin-Coincidencias-${Date.now()}`);
  await expect(form.getByText(/No se encontraron huéspedes/)).toBeVisible({ timeout: 5_000 });

  const toggle = form.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true });
  await expect(toggle).toBeVisible();
  await toggle.click();
  await expect(form.getByPlaceholder("Nombre")).toBeVisible();
  await expect(form.getByPlaceholder("Apellido")).toBeVisible();
});
