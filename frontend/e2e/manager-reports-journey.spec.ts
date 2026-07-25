import { expect, test, type Page } from "@playwright/test";

// Fase 8: manager generates and reads the operational report, and the
// numbers must reconcile with the operations just performed (not just
// "the page renders"), for the manager persona specifically.
//
// The seeded "Standard E2E" category prices at $100/night (CategoryPricing
// price_cash=100), so a 1-night, unpaid, today-check-in reservation has a
// known, deterministic total/balance of $100 -- asserted directly instead of
// parsing it back out of a create-reservation network response, which is a
// source of timing flakiness against React Query's own report refetch.
const manager = {
  email: process.env.E2E_MANAGER_EMAIL || "manager@e2e.com",
  password: process.env.E2E_MANAGER_PASSWORD || "E2eManager1234!"
};

const todayIso = (offsetDays = 0) => {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
};

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(manager.email);
  await page.locator('input[type="password"]').fill(manager.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
  await expect(page.getByTestId("session-role")).toHaveText("Manager");
}

test("manager reads a daily report whose arrivals and pending balance match a reservation just created", async ({
  page
}) => {
  const suffix = Date.now().toString();
  const guestLastName = `QA-Manager ${suffix}`;

  await login(page);

  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  const reservationForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(reservationForm).toBeVisible();

  await reservationForm.getByPlaceholder("Nombre").fill("Huésped");
  await reservationForm.getByPlaceholder("Apellido").fill(guestLastName);
  await reservationForm.getByPlaceholder("Email").fill(`qa.manager.${suffix}@example.test`);
  await reservationForm.getByPlaceholder("Teléfono").fill("1112345678");
  await reservationForm.getByLabel("Tipo de documento").selectOption("DNI");
  await reservationForm.getByPlaceholder("Documento").fill(`QA-MGR-${suffix}`);
  await reservationForm.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = reservationForm.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  const categoryValue = await categoryOption.getAttribute("value");
  expect(categoryValue).toBeTruthy();
  await categorySelect.selectOption(categoryValue!);

  const roomSelect = reservationForm.locator("label").filter({ hasText: "Habitación (opcional)" }).locator("select");
  const roomOption = roomSelect.locator("option").filter({ hasText: "101" });
  await expect(roomOption).toHaveCount(1);
  const roomValue = await roomOption.getAttribute("value");
  expect(roomValue).toBeTruthy();
  await roomSelect.selectOption(roomValue!);

  // Check-in hoy, 1 noche: el reporte diario por defecto usa la fecha de hoy,
  // y a $100/noche (Standard E2E) el total/saldo esperado es exactamente $100.
  await reservationForm
    .locator("label")
    .filter({ hasText: "Check-in" })
    .locator('input[type="date"]')
    .fill(todayIso());
  await reservationForm
    .locator("label")
    .filter({ hasText: "Check-out" })
    .locator('input[type="date"]')
    .fill(todayIso(1));

  const createReservationButton = reservationForm.getByRole("button", { name: "Crear", exact: true });
  await expect(createReservationButton).toBeEnabled();
  await createReservationButton.click();
  await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();

  const reservationTable = page.locator("table").filter({ hasText: "Código" });
  const reservationRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await expect(reservationRow).toHaveCount(1);
  const confirmationCode = (await reservationRow.locator("td").first().innerText()).trim();
  expect(confirmationCode).toMatch(/^RES-/);
  await expect(reservationRow.locator("td").nth(6)).toContainText("$ 100");
  await expect(reservationRow.locator("td").nth(5)).toContainText("Pendiente");

  await page.goto("/reportes");
  await expect(page.getByRole("heading", { name: "Reportes", exact: true })).toBeVisible();
  await expect(page.getByText("Llegadas del dia", { exact: true })).toBeVisible();

  // `section` filtered by text also matches the outer grid wrapper (which
  // contains every card, including Alertas -- which can independently
  // mention this same reservation code in a pending-payment warning).
  // Anchor on the exact heading and walk up to its own <section> instead.
  const arrivalsSection = page
    .getByRole("heading", { name: "Llegadas del dia", exact: true })
    .locator("xpath=ancestor::section[1]");
  const arrivalRow = arrivalsSection.locator("div").filter({ hasText: confirmationCode }).last();
  await expect(arrivalRow).toBeVisible();
  await expect(arrivalRow).toContainText(guestLastName);
  await expect(arrivalRow).toContainText("pending");

  const pendingSection = page
    .getByRole("heading", { name: "Pagos pendientes", exact: true })
    .locator("xpath=ancestor::section[1]");
  const pendingRow = pendingSection.locator("div.grid").filter({ hasText: confirmationCode });
  await expect(pendingRow).toBeVisible();
  await expect(pendingRow).toContainText("$ 100,00");

  // Cleanup: this test pins room 101 for today/tomorrow so its own report
  // assertions are deterministic. Only 2 rooms exist in the seeded E2E
  // category, and the WebKit Apple matrix reruns this exact spec once per
  // device project against the same shared database, so a stale "pending"
  // reservation left behind here would make the very next device run fail
  // room availability with "Room 101 is not available for the requested
  // dates" -- a false negative caused by test leftovers, not a real defect.
  // Cancelling (not checking out) frees the room for the next device run.
  await page.goto("/reservas");
  const reservasTable = page.locator("table").filter({ hasText: "Código" });
  const ownReservationRow = reservasTable.locator("tbody tr").filter({ hasText: guestLastName });
  await ownReservationRow.getByRole("button", { name: "Cancelar", exact: true }).click();
  await expect(page.getByText("Reserva cancelada", { exact: true })).toBeVisible();
});
