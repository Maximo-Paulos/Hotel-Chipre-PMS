import { expect, test, type Page } from "@playwright/test";

// B2: planilla de ocupación (OccupancyPlanningPage). Loads the current
// month's grid with a real reservation created in this test, clicks its
// cell to open the same ReservationDetailDrawer from B1 (not a separate
// component), and navigates ±30 days.

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

function localIsoDate(offsetDays: number) {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

test("owner sees a real reservation on the current-month grid and opens it via the drawer", async ({ page }) => {
  const suffix = Date.now().toString();
  const guestLastName = `PlanillaQA-${suffix}`;
  // Salted, near-future offset (day 3-17) so it lands well inside the grid's
  // default 30-day window regardless of when this spec runs, while staying
  // clear of other specs' "today" (offset 0) fixtures.
  const salt = Number(suffix.slice(-3));
  const checkIn = localIsoDate(3 + (salt % 15));
  const checkOut = localIsoDate(3 + (salt % 15) + 2);

  await login(page);

  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();

  const form = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(form).toBeVisible();
  await form.getByPlaceholder("Nombre").fill("Huésped");
  await form.getByPlaceholder("Apellido").fill(guestLastName);
  await form.getByPlaceholder("Email").fill(`${guestLastName.toLowerCase()}@example.test`);
  await form.getByPlaceholder("Teléfono").fill("1112345678");
  await form.getByLabel("Tipo de documento").selectOption("DNI");
  await form.getByPlaceholder("Documento").fill(`PLANILLA-${suffix}`);
  await form.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = form.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  const categoryValue = await categoryOption.getAttribute("value");
  await categorySelect.selectOption(categoryValue!);

  // Leave "Habitación (opcional)" as "Sin asignar" -- the backend
  // auto-assigns whichever of the fixture's two rooms is free, so this
  // doesn't depend on a specific room number being unbooked.
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
  expect(created.room_id).toBeTruthy();

  // Load the current month's grid (default window starts today).
  const gridResponse = page.waitForResponse(
    (res) => res.url().includes("/api/reservations/occupancy-grid") && res.request().method() === "GET"
  );
  await page.goto("/operacion/planilla");
  await gridResponse;
  await expect(page.getByRole("heading", { name: "Planilla de ocupación" })).toBeVisible();
  await expect(page.getByTestId("occupancy-grid")).toBeVisible();

  // The 2-night stay occupies 2 day columns, each rendering its own cell
  // with this same testid -- take the first for the click/visibility checks.
  const cell = page.getByTestId(`occupancy-reservation-${reservationId}`).first();
  await expect(cell).toBeVisible();
  await expect(cell).toContainText(guestLastName);

  await cell.click();
  const drawer = page.getByRole("dialog", { name: confirmationCode });
  await expect(drawer).toBeVisible();
  await expect(drawer).toContainText(guestLastName);
  await expect(drawer.getByText("Pendiente", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Cerrar detalle de reserva" }).click();
  await expect(drawer).not.toBeVisible();

  // ±30 days navigation: the reservation (day 3-17ish) drops out of view
  // once the window moves forward a full 30 days, and reappears going back.
  // No waitForResponse here -- the adjacent windows are prefetched on mount
  // (that's the point of usePrefetchOccupancyGrid), so navigating often
  // resolves straight from cache with no new network round-trip.
  await page.getByTestId("occupancy-next-window").click();
  await expect(page.getByTestId(`occupancy-reservation-${reservationId}`)).toHaveCount(0);

  await page.getByTestId("occupancy-prev-window").click();
  await expect(page.getByTestId(`occupancy-reservation-${reservationId}`).first()).toBeVisible();
});
