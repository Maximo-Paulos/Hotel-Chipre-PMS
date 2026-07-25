import { expect, test, type Page } from "@playwright/test";

// B1: ReservationDetailDrawer + global access (header search, "Reserva
// rápida", and the ?reserva=<id> deep link). Covers opening the drawer from
// three different entry points and verifies it shows the real state,
// guest, and financials of a reservation created in this test.

const credentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("owner opens the reservation drawer from the dashboard, global search, and a deep link", async ({ page }) => {
  const suffix = Date.now().toString();
  const guestLastName = `DrawerQA-${suffix}`;
  // Post-A2: dashboard's "Próximas reservas" widget is fed by the 10 most
  // recently CREATED reservations (order=recent, limit=10), then sorted by
  // check_in_date for display. A reservation created by this test is by
  // definition the most recently created one, so it lands in that top-10
  // window regardless of check_in_date -- the far-past date below no longer
  // drives dashboard placement, it's just a value that's easy to keep out of
  // the way of other specs' fixture dates.
  // Salted per run (not a fixed date) so re-running this spec doesn't
  // collide with room 101 already booked by a previous run's leftovers.
  const salt = Number(suffix.slice(-4));
  const pastIsoDate = (daysAgo: number) => {
    const value = new Date();
    value.setDate(value.getDate() - daysAgo);
    const pad = (part: number) => String(part).padStart(2, "0");
    return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
  };
  const checkIn = pastIsoDate(5000 + salt);
  const checkOut = pastIsoDate(5000 + salt - 2);

  await login(page);

  // Only "cash" completes a payment immediately in this backend (bank
  // transfer/gateway methods stay pending until a proof/webhook confirms
  // them) -- see app/services/payment_service.py:process_payment. Cash
  // requires an open register, so open one first (idempotent: another spec
  // may have already left this hotel's register open).
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
    await openResponse;
  }

  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();

  const form = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(form).toBeVisible();
  await form.getByPlaceholder("Nombre").fill("Huésped");
  await form.getByPlaceholder("Apellido").fill(guestLastName);
  await form.getByPlaceholder("Email").fill(`${guestLastName.toLowerCase()}@example.test`);
  await form.getByPlaceholder("Teléfono").fill("1112345678");
  await form.getByLabel("Tipo de documento").selectOption("DNI");
  await form.getByPlaceholder("Documento").fill(`DRAWER-${suffix}`);
  await form.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = form.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  const categoryValue = await categoryOption.getAttribute("value");
  await categorySelect.selectOption(categoryValue!);

  const roomSelect = form.locator("label").filter({ hasText: "Habitación (opcional)" }).locator("select");
  const roomOption = roomSelect.locator("option").filter({ hasText: "101" });
  await expect(roomOption).toHaveCount(1);
  const roomValue = await roomOption.getAttribute("value");
  await roomSelect.selectOption(roomValue!);
  await form.locator("label").filter({ hasText: "Check-in" }).locator('input[type="date"]').fill(checkIn);
  await form.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]').fill(checkOut);
  await expect(form.getByRole("button", { name: "Crear", exact: true })).toBeEnabled();

  const [createResponse] = await Promise.all([
    page.waitForResponse((res) => res.url().includes("/api/reservations/") && res.request().method() === "POST"),
    form.getByRole("button", { name: "Crear", exact: true }).click()
  ]);
  await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();
  const created = await createResponse.json();
  const reservationId: number = created.id;
  const confirmationCode: string = created.confirmation_code;
  expect(reservationId).toBeGreaterThan(0);

  // 1) Open from the dashboard.
  await page.goto("/dashboard");
  await page.getByRole("button", { name: confirmationCode }).click();

  const drawer = page.getByRole("dialog", { name: confirmationCode });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByText("Pendiente", { exact: true })).toBeVisible();
  await expect(drawer.getByText(`Huésped ${guestLastName}`, { exact: false })).toBeVisible();
  await expect(drawer).toContainText(guestLastName);
  await expect(drawer.getByText("Sin acompañantes cargados.", { exact: true })).toBeVisible();
  const balanceBeforePayment = await drawer.getByTestId("drawer-balance-due").innerText();
  expect(balanceBeforePayment).toMatch(/\d/);
  expect(balanceBeforePayment).not.toMatch(/^\D*0[.,]00\D*$/);

  // Cobrar seña en el momento, directly from the drawer.
  await drawer.getByLabel("Importe a cobrar").fill("100");
  await drawer.getByRole("button", { name: "Registrar cobro", exact: true }).click();
  await expect(drawer.getByText("Pago registrado.", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Cerrar detalle de reserva" }).click();
  await expect(drawer).not.toBeVisible();
  await expect(page).toHaveURL(/\/dashboard$/);

  // 2) Open from the global header search.
  await page.getByRole("searchbox", { name: "Buscar reserva" }).fill(guestLastName);
  const searchResult = page.getByTestId("reservation-search-results").getByRole("button", { name: new RegExp(confirmationCode) });
  await expect(searchResult).toBeVisible();
  await searchResult.click();

  await expect(drawer).toBeVisible();
  await expect(drawer).toContainText(confirmationCode);
  await expect(page).toHaveURL(new RegExp(`reserva=${reservationId}`));
  // The payment summary refetches after the mutation invalidates it, so
  // poll instead of reading innerText() once (which can race the refetch).
  await expect(drawer.getByTestId("drawer-balance-due")).not.toHaveText(balanceBeforePayment);

  const deepLinkUrl = page.url();
  await page.getByRole("button", { name: "Cerrar detalle de reserva" }).click();
  await expect(drawer).not.toBeVisible();

  // 3) Deep link: loading ?reserva=<id> directly opens the drawer.
  await page.goto(deepLinkUrl);
  await expect(drawer).toBeVisible();
  await expect(drawer).toContainText(confirmationCode);
  await expect(drawer.getByText("Seña", { exact: true })).toBeVisible();
});
