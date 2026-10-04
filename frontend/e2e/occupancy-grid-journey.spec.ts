import { expect, test, type Page } from "@playwright/test";

// B2: planilla de ocupación (OccupancyPlanningPage). Loads the current
// month's grid with a real reservation created in this test, clicks its
// cell to open the same ReservationDetailDrawer from B1 (not a separate
// component), and navigates two-week windows without horizontal scrolling on desktop.

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

function plusIsoDays(isoDate: string, offsetDays: number) {
  const value = new Date(`${isoDate}T00:00:00`);
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

const displayDate = (isoDate: string) => `${isoDate.slice(8, 10)}/${isoDate.slice(5, 7)}/${isoDate.slice(0, 4)}`;

test("owner sees a real reservation on the current-month grid and opens it via the drawer", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  const suffix = Date.now().toString();
  const guestLastName = `PlanillaQA-${suffix}`;
  // Salted, near-future offset (day 3-10) so it lands well inside the grid's
  // default 14-day window regardless of when this spec runs, while staying
  // clear of other specs' "today" (offset 0) fixtures.
  const salt = Number(suffix.slice(-3));
  const checkIn = localIsoDate(3 + (salt % 8));
  const checkOut = localIsoDate(3 + (salt % 8) + 2);

  await login(page);

  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();

  const form = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(form).toBeVisible();
  await form.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
  await form.getByPlaceholder("Nombre").fill("Huésped");
  await form.getByPlaceholder("Apellido").fill(guestLastName);
  await form.getByPlaceholder("Email").fill(`${guestLastName.toLowerCase()}@example.test`);
  await form.getByPlaceholder("Teléfono").fill(`11${Date.now().toString().slice(-8)}${Math.floor(Math.random() * 100).toString().padStart(2, "0")}`);
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
  await form.getByLabel("Check-in", { exact: true }).fill(checkIn);
  await form.getByLabel("Check-out", { exact: true }).fill(checkOut);
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

  await page.goto("/habitaciones");
  const blockForm = page.locator("form").filter({ has: page.getByRole("button", { name: "Crear bloqueo", exact: true }) });
  await blockForm.getByLabel("Habitación").selectOption(String(created.room_id));
  await blockForm.getByLabel("Desde").fill(checkIn);
  await blockForm.getByLabel("Hasta").fill(checkOut);
  const blockConflictWarning = page.getByRole("alert").filter({ hasText: "Reservas superpuestas" });
  await expect(blockConflictWarning).toContainText("Reservas superpuestas: 1");
  await expect(blockConflictWarning).toContainText("Revisá la Planilla");
  await blockForm.getByRole("button", { name: "Crear bloqueo", exact: true }).click();
  await expect(page.getByText("Bloqueo creado.", { exact: true })).toBeVisible();

  // Load the current month's grid (default window starts today).
  const gridResponse = page.waitForResponse(
    (res) => res.url().includes("/api/reservations/occupancy-grid") && res.request().method() === "GET"
  );
  await page.goto("/operacion/planilla");
  const occupancyData = await (await gridResponse).json() as {
    rooms: Array<{ id: number; room_number: string; floor: number; category_id: number; category_name: string; status: string }>;
    reservations: Array<{ room_id: number | null; check_in_date: string; check_out_date: string }>;
    blocks: Array<{ room_id: number; starts_at: string; ends_at: string | null }>;
  };
  await expect(page.getByRole("heading", { name: "Planilla de ocupación" })).toBeVisible();
  await expect(page.getByTestId("occupancy-grid")).toBeVisible();
  await expect(page.getByText("Leyenda", { exact: true })).toBeVisible();
  await expect(page.getByTestId(`occupancy-free-row-${created.category_id}`)).toBeVisible();
  await expect(page.getByTestId(`occupancy-free-count-${created.category_id}-${localIsoDate(13)}`)).toBeVisible();
  const gridFitsDesktop = await page.getByTestId("occupancy-grid").evaluate((element) => element.scrollWidth <= element.clientWidth);
  expect(gridFitsDesktop).toBe(true);

  // The 2-night stay occupies 2 day columns, each rendering its own cell
  // with this same testid -- take the first for the click/visibility checks.
  const cell = page.getByTestId(`occupancy-reservation-${reservationId}`).first();
  await expect(cell).toBeVisible();
  await expect(cell).toContainText(guestLastName);
  const blockConflictCell = page.getByTestId(`occupancy-block-conflict-${reservationId}`).first();
  await expect(blockConflictCell).toBeVisible();
  await expect(blockConflictCell).toContainText("Bloqueo superpuesto: Mantenimiento");

  await cell.click();
  const drawer = page.getByRole("dialog", { name: confirmationCode });
  await expect(drawer).toBeVisible();
  await expect(drawer).toContainText(guestLastName);
  await expect(drawer.getByText("Pendiente", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Cerrar detalle de reserva" }).click();
  await expect(drawer).not.toBeVisible();

  // Advancing one two-week window drops the reservation, and going back
  // shows it again.
  // No waitForResponse here -- the adjacent windows are prefetched on mount
  // (that's the point of usePrefetchOccupancyGrid), so navigating often
  // resolves straight from cache with no new network round-trip.
  await page.getByTestId("occupancy-next-window").click();
  await expect(page.getByTestId(`occupancy-reservation-${reservationId}`)).toHaveCount(0);

  await page.getByTestId("occupancy-prev-window").click();
  await expect(page.getByTestId(`occupancy-reservation-${reservationId}`).first()).toBeVisible();

  const roomGroupIds = occupancyData.rooms.map((room) => room.category_id);
  const categoryOrder = [...new Set(roomGroupIds)].sort((a, b) => {
    const aName = occupancyData.rooms.find((room) => room.category_id === a)!.category_name;
    const bName = occupancyData.rooms.find((room) => room.category_id === b)!.category_name;
    return aName.localeCompare(bName);
  });
  await page.getByTestId("occupancy-sort").selectOption("category");
  const categoryHeaders = await page.locator('[data-testid^="occupancy-group-category-"]').evaluateAll((nodes) =>
    nodes.map((node) => Number(node.getAttribute("data-testid")!.replace("occupancy-group-category-", "")))
  );
  expect(categoryHeaders).toEqual(categoryOrder);
  await page.getByTestId("occupancy-sort").selectOption("floor");
  const floorHeaders = await page.locator('[data-testid^="occupancy-group-floor-"]').evaluateAll((nodes) =>
    nodes.map((node) => Number(node.getAttribute("data-testid")!.replace("occupancy-group-floor-", "")))
  );
  expect(floorHeaders).toEqual([...floorHeaders].sort((a, b) => a - b));

  const createTarget = occupancyData.rooms.flatMap((room) =>
    // Use a future visible date. The current-day column can straddle a hotel
    // timezone boundary during local/CI runs and is not required to verify
    // the empty-cell creation path.
    Array.from({ length: 13 }, (_, index) => ({ room, date: localIsoDate(index + 1) }))
  ).find(({ room, date }) =>
    !["maintenance", "blocked"].includes(room.status)
    && !occupancyData.reservations.some((reservation) =>
      reservation.room_id === room.id && reservation.check_in_date <= date && date < reservation.check_out_date
    )
    && !occupancyData.blocks.some((block) =>
      block.room_id === room.id && block.starts_at <= date && (block.ends_at === null || date < block.ends_at)
    )
  );
  expect(createTarget).toBeTruthy();
  await page.setViewportSize({ width: 390, height: 844 });
  const mobileLayout = await page.evaluate(() => ({
    pageWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
    gridWidth: document.querySelector('[data-testid="occupancy-grid"]')!.clientWidth,
    gridContentWidth: document.querySelector('[data-testid="occupancy-grid"]')!.scrollWidth
  }));
  expect(mobileLayout.pageWidth).toBeLessThanOrEqual(mobileLayout.viewportWidth);
  expect(mobileLayout.gridContentWidth).toBeGreaterThan(mobileLayout.gridWidth);
  await page.getByTestId(`occupancy-create-${createTarget!.room.id}-${createTarget!.date}`).click();
  await expect(page).toHaveURL(/\/reservas(?:\?.*)?$/);
  const createForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(createForm).toBeVisible();
  await expect(createForm.locator("label").filter({ hasText: "Categoría" }).locator("select")).toHaveValue(String(createTarget!.room.category_id));
  await expect(createForm.locator("label").filter({ hasText: "Habitación" }).locator("select")).toHaveValue(String(createTarget!.room.id));
  await expect(createForm.getByLabel("Check-in", { exact: true })).toHaveValue(displayDate(createTarget!.date));
  await expect(createForm.getByLabel("Check-out", { exact: true })).toHaveValue(displayDate(plusIsoDays(createTarget!.date, 1)));
  await expect(page.getByText("Habitación vs fechas", { exact: true })).toHaveCount(0);
});
