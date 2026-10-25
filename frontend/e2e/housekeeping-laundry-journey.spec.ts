import { expect, test, type Page } from "@playwright/test";

test.use({ screenshot: "off", video: "off", trace: "off" });

// D2 (Via D lavanderia): full laundry cycle for the housekeeping role.
// laundry:manage_vendors (vendor + pricing setup) is owner/co_owner/manager
// only; laundry:operate_remitos (day-to-day remito create/list/balance) also
// includes housekeeping -- so the owner does setup here, then housekeeping
// does the real daily work: send a remito and see it reflected in the
// vendor balance, same as they did with LaundryBatch status transitions
// before D2 replaced that flow. Detailed error-path and cross-direction
// coverage lives in laundry-vendor-cycle-journey.spec.ts; this file only
// covers the housekeeping/owner permission split on the new flow.
const owner = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};
const housekeeping = {
  email: process.env.E2E_HOUSEKEEPING_EMAIL || "housekeeping@e2e.com",
  password: process.env.E2E_HOUSEKEEPING_PASSWORD || "E2eHousekeeping1234!"
};

async function login(page: Page, credentials: { email: string; password: string }, landingPath: string) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL(`**${landingPath}`, { timeout: 20_000 });
}

async function logout(page: Page) {
  await page.getByTestId("logout-btn").click();
  await page.waitForURL("**/login");
}

test("laundry data stays cached across navigation and refreshes after a saved vendor", async ({ page }) => {
  test.skip(process.env.REALTIME_E2E !== "true", "La actualización tras guardar depende de realtime activo.");
  const watchedPaths = [
    "/api/laundry/vendors",
    "/api/laundry/items",
    "/api/laundry/locations",
    "/api/laundry/remitos"
  ];
  const requestCounts = new Map(watchedPaths.map((path) => [path, 0]));
  page.on("request", (request) => {
    if (request.method() !== "GET") return;
    const pathname = new URL(request.url()).pathname;
    if (requestCounts.has(pathname)) requestCounts.set(pathname, requestCounts.get(pathname)! + 1);
  });

  await login(page, owner, "/dashboard");
  const initialReads = watchedPaths.map((path) => page.waitForResponse((response) =>
    response.request().method() === "GET" && new URL(response.url()).pathname === path
  ));
  await page.goto("/operacion/lavanderia");
  for (const response of await Promise.all(initialReads)) expect(response.status()).toBe(200);
  await expect(page.getByText("Conectado: cambios en tiempo real activos.", { exact: true })).toBeVisible();
  await page.waitForTimeout(500);
  const warmCounts = new Map(requestCounts);

  const dashboardLink = page.getByRole("link", { name: "Dashboard", exact: true });
  if (!(await dashboardLink.isVisible())) await page.getByText("Más operación", { exact: true }).click();
  await dashboardLink.click();
  await expect(page.getByRole("heading", { name: "Visión general", exact: true })).toBeVisible();
  const laundryLink = page.getByRole("link", { name: "Lavandería", exact: true });
  if (!(await laundryLink.isVisible())) await page.getByText("Más operación", { exact: true }).click();
  await laundryLink.click();
  await expect(page.getByRole("heading", { name: "Lavandería", exact: true })).toBeVisible();
  await page.waitForTimeout(500);
  expect(requestCounts).toEqual(warmCounts);

  const vendorName = `QA Cache Lavadero ${Date.now()}`;
  const vendorRefresh = page.waitForResponse((response) =>
    response.request().method() === "GET" && new URL(response.url()).pathname === "/api/laundry/vendors"
  );
  const vendorCreate = page.waitForResponse((response) =>
    response.request().method() === "POST" && new URL(response.url()).pathname === "/api/laundry/vendors"
  );
  const vendorForm = page.locator("form").filter({ hasText: "Nuevo lavadero" });
  await vendorForm.getByLabel("Nombre").fill(vendorName);
  await vendorForm.getByRole("button", { name: "Crear lavadero", exact: true }).click();
  expect((await vendorCreate).status()).toBe(201);
  expect((await vendorRefresh).status()).toBe(200);
  await expect(page.getByText(`Lavadero \"${vendorName}\" creado.`, { exact: true })).toBeVisible();
  expect(requestCounts.get("/api/laundry/vendors")).toBe((warmCounts.get("/api/laundry/vendors") ?? 0) + 1);
});

test("housekeeping sends a laundry remito on a vendor set up by the owner", async ({ page }) => {
  const suffix = Date.now().toString();
  const vendorName = `QA HK Lavadero ${suffix}`;
  const locationName = `QA HK Deposito ${suffix}`;
  const destinationLocationName = `QA HK Office ${suffix}`;
  const itemName = `QA HK Toallas ${suffix}`;

  await login(page, owner, "/dashboard");

  // D (stock/lavanderia separation, split real): ropa blanca vive en su
  // propia tabla/API (linen_items/linen_locations/linen_movements) -- alta
  // de item, ubicacion y carga de stock inicial se hacen todas desde
  // LaundryPage ahora, StockPage ya no puede targetear un item de linen.
  await page.goto("/operacion/lavanderia");
  const linenItemForm = page.locator("form").filter({ hasText: "Nuevo tipo de ropa blanca" });
  await linenItemForm.getByLabel("Nombre").fill(itemName);
  await linenItemForm.getByRole("button", { name: "Crear tipo de ropa blanca", exact: true }).click();
  await expect(page.getByText("Tipo de ropa blanca creado.", { exact: true })).toBeVisible();

  const linenLocationForm = page.locator("form").filter({ hasText: "Nueva ubicación" });
  await linenLocationForm.getByLabel("Nombre").fill(locationName);
  await linenLocationForm.getByRole("button", { name: "Crear ubicación", exact: true }).click();
  await expect(page.getByText("Ubicación de lavandería creada.", { exact: true })).toBeVisible();

  await linenLocationForm.getByLabel("Nombre").fill(destinationLocationName);
  await linenLocationForm.getByRole("button", { name: "Crear ubicación", exact: true }).click();
  await expect(page.getByText("Ubicación de lavandería creada.", { exact: true })).toBeVisible();

  const openingGrid = page.getByTestId("linen-opening-count-grid");
  await openingGrid.getByLabel(`Conteo inicial ${itemName} en ${locationName}`).fill("8");
  await openingGrid.getByLabel("Motivo").fill("Stock inicial QA housekeeping");
  await openingGrid.getByRole("button", { name: "Guardar conteo inicial", exact: true }).click();
  await expect(page.getByText("Conteo inicial guardado para 1 ítem.", { exact: true })).toBeVisible();

  const hotelLinenStock = page.locator('section[aria-labelledby="house-stock-title"]');
  await hotelLinenStock.getByLabel("Ubicación").selectOption({ label: locationName });
  const linenItemRow = hotelLinenStock.locator("li").filter({ hasText: itemName });
  await linenItemRow.getByLabel("Mínimo en esta ubicación").fill("10");
  await linenItemRow.getByRole("button", { name: "Guardar mínimo", exact: true }).click();
  await expect(hotelLinenStock.getByRole("alert")).toContainText(`${itemName}: 8 disponibles; mínimo 10.`);

  const transferForm = page.getByTestId("linen-transfer-form");
  await transferForm.getByLabel("Tipo de ropa blanca").selectOption({ label: itemName });
  await transferForm.getByLabel("Cantidad").fill("3");
  await transferForm.getByLabel("Desde").selectOption({ label: locationName });
  await transferForm.getByLabel("Hacia").selectOption({ label: destinationLocationName });
  await transferForm.getByLabel("Motivo").fill("Reposición de office QA");
  await transferForm.getByRole("button", { name: "Guardar traspaso", exact: true }).click();
  await expect(page.getByText("Traspaso de ropa blanca registrado.", { exact: true })).toBeVisible();

  await expect(hotelLinenStock.getByRole("alert")).toContainText(`${itemName}: 5 disponibles; mínimo 10.`);
  await hotelLinenStock.locator("select").selectOption({ label: destinationLocationName });
  await expect(hotelLinenStock.locator("li").filter({ hasText: itemName }).getByText("3 unidad", { exact: true })).toBeVisible();
  await hotelLinenStock.locator("select").selectOption({ label: locationName });

  await page.goto("/operacion/lavanderia");
  const vendorForm = page.locator("form").filter({ hasText: "Nuevo lavadero" });
  await vendorForm.getByLabel("Nombre").fill(vendorName);
  await vendorForm.getByRole("button", { name: "Crear lavadero", exact: true }).click();
  await expect(page.getByText(`Lavadero "${vendorName}" creado.`, { exact: true })).toBeVisible();
  const vendorPriceForm = page.locator("form").filter({ hasText: "Guardar precio" });
  await vendorPriceForm.getByLabel("Ítem").selectOption({ label: itemName });
  await vendorPriceForm.getByLabel("Precio por unidad").fill("100");
  await vendorPriceForm.getByRole("button", { name: "Guardar precio", exact: true }).click();
  await expect(page.getByText("Precio guardado.", { exact: true })).toBeVisible();
  await logout(page);

  await login(page, housekeeping, "/habitaciones");
  await expect(page.getByTestId("session-role")).toHaveText("Limpieza");
  await page.goto("/operacion/lavanderia");

  const main = page.locator("main");
  await expect(main.getByRole("heading", { name: "Lavandería", exact: true })).toBeVisible();
  const housekeepingLinenStock = page.locator('section[aria-labelledby="house-stock-title"]');
  await housekeepingLinenStock.getByLabel("Ubicación").selectOption({ label: locationName });
  // housekeeping never sees the vendor/pricing admin panel at all -- it's
  // gated by laundry:manage_vendors, not just the "Crear lavadero" button.
  await expect(main.getByRole("button", { name: "Crear lavadero" })).toHaveCount(0);
  await expect(main.getByText("Lavaderos y precios", { exact: false })).toHaveCount(0);

  const remitoForm = main.locator("form").filter({ hasText: "Nuevo remito" });
  await remitoForm.getByLabel("Lavadero").selectOption({ label: vendorName });
  await remitoForm.getByLabel("Ubicación casa (origen/destino en el hotel)").selectOption({ label: locationName });
  await remitoForm.getByLabel("N° de remito (papel)").fill(`R-HK-${suffix}`);
  await remitoForm.getByLabel(`Retiro ${itemName}`, { exact: true }).fill("5");
  await remitoForm.getByRole("button", { name: "Guardar remito", exact: true }).click();
  await expect(page.getByText(`Remito R-HK-${suffix} guardado.`, { exact: false })).toBeVisible();

  const remitoEntry = main
    .getByRole("list", { name: "Historial de remitos" })
    .getByRole("listitem")
    .filter({ hasText: `Remito R-HK-${suffix}` });
  await expect(remitoEntry).toContainText(`Ubicación: ${locationName}`);
  await expect(remitoEntry.getByText(/Cargó:/)).toBeVisible();

  await expect(housekeepingLinenStock.getByRole("alert")).toContainText(`No hay unidades disponibles de ${itemName} en esta ubicación.`);

  const vendorBalance = main
    .locator("div.rounded-lg.border.border-slate-200.bg-slate-50.p-3")
    .filter({ hasText: vendorName });
  await expect(vendorBalance).toContainText(itemName);
  await expect(vendorBalance).toContainText("5");
});

test("housekeeping checklist completes and refreshes room state on mobile in English", async ({ page }) => {
  test.setTimeout(120_000);
  const itemCodes = ["change_sheets", "clean_bathroom", "replenish_towels", "empty_waste", "check_amenities"] as const;
  const itemLabels: Record<(typeof itemCodes)[number], string> = {
    change_sheets: "Change sheets",
    clean_bathroom: "Clean the bathroom",
    replenish_towels: "Replenish towels",
    empty_waste: "Empty waste",
    check_amenities: "Check amenities"
  };
  const completedItems = new Set<(typeof itemCodes)[number]>();
  let checklistCompleted = false;

  const housekeepingBoard = () => ({
    date: "2026-10-23",
    rooms: [{
      room_id: 101,
      room_number: "101",
      floor: 1,
      category_name: "Standard",
      operational_status: checklistCompleted ? "available" : "cleaning",
      housekeeping_status: checklistCompleted ? "clean" : "in_progress",
      has_arrival_today: false,
      has_departure_today: true,
      has_stayover_today: false,
      maintenance_blocked: false
    }]
  });
  const checklist = () => ({
    checklist_id: 501,
    room: {
      id: 101,
      number: "101",
      operational_status: checklistCompleted ? "available" : "cleaning",
      housekeeping_status: checklistCompleted ? "clean" : "in_progress"
    },
    status: checklistCompleted ? "completed" : "open",
    version: completedItems.size,
    created_at: "2026-10-23T12:00:00Z",
    completed_at: checklistCompleted ? "2026-10-23T13:00:00Z" : null,
    items: itemCodes.map((code) => ({
      code,
      label: itemLabels[code],
      completed: completedItems.has(code),
      completed_at: completedItems.has(code) ? "2026-10-23T12:30:00Z" : null
    }))
  });

  await page.route("**/api/config/interface-language", async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ interface_language: "en" })
    })
  );
  await page.route("**/api/rooms/housekeeping-board", async (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(housekeepingBoard()) })
  );
  await page.route("**/api/housekeeping/checklists", async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ checklists: checklistCompleted ? [] : [checklist()] })
    })
  );
  await page.route("**/api/housekeeping/checklists/501/items/*/complete", async (route) => {
    const itemCode = new URL(route.request().url()).pathname.split("/").at(-2) as (typeof itemCodes)[number];
    expect(itemCodes).toContain(itemCode);
    completedItems.add(itemCode);
    checklistCompleted = itemCodes.every((code) => completedItems.has(code));
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(checklist()) });
  });

  await page.setViewportSize({ width: 390, height: 844 });
  const boardResponsePromise = page.waitForResponse((response) =>
    response.request().method() === "GET"
      && new URL(response.url()).pathname === "/api/rooms/housekeeping-board"
  );
  await login(page, housekeeping, "/habitaciones");
  const boardResponse = await boardResponsePromise;
  expect(boardResponse.status()).toBe(200);
  const board = await boardResponse.json() as {
    rooms: Array<Record<string, unknown>>;
  };
  const expectedRoomFields = [
    "room_id",
    "room_number",
    "floor",
    "category_name",
    "operational_status",
    "housekeeping_status",
    "has_arrival_today",
    "has_departure_today",
    "has_stayover_today",
    "maintenance_blocked"
  ].sort();
  for (const room of board.rooms) {
    expect(Object.keys(room).sort()).toEqual(expectedRoomFields);
  }

  await page.goto("/operacion/limpieza-hoy");
  const main = page.locator("main");
  await expect(main.getByRole("heading", { name: "Housekeeping today", exact: true })).toBeVisible();
  await expect(main.getByRole("button", { name: "Refresh", exact: true })).toBeVisible();
  await expect(main.getByRole("heading", { name: "Checkout checklist", exact: true })).toBeVisible();
  await expect(main.getByText("0 of 5 tasks completed", { exact: true })).toBeVisible();
  await expect(main.getByRole("checkbox")).toHaveCount(5);
  await expect(main.getByRole("combobox", { name: "Cleaning status · 101", exact: true })).toHaveCount(0);

  for (const itemCode of itemCodes) {
    const checkbox = main.getByRole("checkbox", { name: itemLabels[itemCode], exact: true });
    const completionResponse = page.waitForResponse((response) =>
      response.request().method() === "POST"
        && new URL(response.url()).pathname.endsWith(`/items/${itemCode}/complete`)
    );
    await checkbox.click();
    expect((await completionResponse).status()).toBe(200);
    if (itemCode === "check_amenities") {
      await expect(checkbox).toHaveCount(0);
    } else {
      await expect(checkbox).toBeChecked();
    }
  }
  expect([...completedItems]).toEqual(itemCodes);
  await expect(main.getByRole("combobox", { name: "Cleaning status · 101", exact: true })).toHaveValue("clean");
  const roomCard = main.locator("article").filter({ hasText: "Room 101" });
  await expect(roomCard.locator("span").filter({ hasText: /^Clean$/ })).toBeVisible();

  const layout = await page.evaluate(() => ({
    viewportWidth: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    mainWidth: document.querySelector("main")?.clientWidth ?? 0,
    mainContentWidth: document.querySelector("main")?.scrollWidth ?? 0
  }));
  expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewportWidth);
  expect(layout.mainContentWidth).toBeLessThanOrEqual(layout.mainWidth);
});
