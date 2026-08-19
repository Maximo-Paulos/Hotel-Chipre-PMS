import { expect, test, type Locator, type Page, type TestInfo } from "@playwright/test";

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
// and run this exact spec concurrently, promoting the same pre-seeded
// "Huesped E2E" guest into room 101 for the same relative dates. A
// per-project date salt gives each device project its own calendar days so
// the room booking can never race and each project's own promoted
// reservation stays uniquely identifiable for cleanup.
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
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
  await expect(page.getByText(`Usuario ${credentials.email}`)).toBeVisible();
}

// B6.1: routes not in the daily nav row now sit inside a collapsed <details>
// group in the sidebar. Open its <summary> first -- closed <details> content
// isn't visible, so a plain click on the link would fail actionability.
async function revealCollapsedNavLink(link: Locator) {
  const group = link.locator("xpath=ancestor::details[1]");
  if ((await group.count()) > 0 && !(await group.evaluate((el) => (el as HTMLDetailsElement).open))) {
    await group.locator("summary").first().click();
  }
}

async function navigateFromShell(page: Page, path: string) {
  const desktopLink = page.locator(`aside nav a[href="${path}"]`);
  await revealCollapsedNavLink(desktopLink);
  if (await desktopLink.isVisible().catch(() => false)) {
    await expect(desktopLink).toHaveCount(1);
    await desktopLink.click();
    await expect(page).toHaveURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
    return;
  }
  // B7: on mobile the whole nav lives inside a slide-over panel opened via
  // the hamburger button -- open it before looking for the link.
  const menuButton = page.getByTestId("mobile-menu-button");
  if (await menuButton.isVisible().catch(() => false)) {
    await menuButton.click();
  }
  const mobileLink = page.locator(`nav[aria-label="Navegación móvil"] a[href="${path}"]`);
  await expect(mobileLink).toHaveCount(1);
  await expect(mobileLink).toBeVisible();
  await mobileLink.click();
  await expect(page).toHaveURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
}

async function syntheticProofBuffer(page: Page, seed: number) {
  return Buffer.from(await page.evaluate((hue) => {
    const canvas = document.createElement("canvas");
    canvas.width = 1;
    canvas.height = 1;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Canvas no disponible para el fixture del comprobante");
    context.fillStyle = `hsl(${hue % 360} 70% 50%)`;
    context.fillRect(0, 0, 1, 1);
    return canvas.toDataURL("image/png").split(",")[1];
  }, seed), "base64");
}

test("owner completes the core reservation journey through the UI", async ({ page }) => {
  const suffix = Date.now().toString();
  const categoryName = `Journey ${suffix}`;
  const categoryCode = `J${suffix.slice(-6)}`;
  const roomNumber = `J${suffix.slice(-5)}`;
  const guestLastName = `Journey ${suffix}`;

  await login(page);

  // Closing a cash session always opens a new successor session
  // (see close_session() in app/services/cash_register_service.py), so a
  // prior device project's/spec's run of this journey (or any other cash
  // activity) against the shared E2E database can leave one already open.
  // Reuse it instead of assuming "Abrir caja" is always the first move.
  // The "Abrir caja" button starts enabled optimistically and only flips to
  // "Ya hay una caja abierta" once GET /api/cash-register/sessions resolves
  // (CashRegisterPage derives openSession from an initially-empty sessions
  // array), so wait for that response before reading the button state --
  // otherwise the decision (and the click right after) can race the real
  // data and target a button that is about to disappear.
  const sessionsResponse = page.waitForResponse(
    (response) => response.url().includes("/api/cash-register/sessions") && response.request().method() === "GET"
  );
  await navigateFromShell(page, "/caja");
  await sessionsResponse;
  const openingForm = page.locator("form").filter({ hasText: "Saldo inicial" }).filter({ hasText: "Abrir caja" });
  const openButton = openingForm.getByRole("button", { name: "Abrir caja", exact: true });
  if (await openButton.isVisible().catch(() => false)) {
    await openButton.click();
    await expect(page.getByText("Caja abierta.", { exact: true })).toBeVisible();
  } else {
    await expect(page.getByRole("button", { name: "Ya hay una caja abierta", exact: true })).toBeVisible();
  }

  await navigateFromShell(page, "/settings/hotel");
  await expect(page.getByRole("heading", { name: "Hotel", exact: true })).toBeVisible();

  await page.getByPlaceholder("Nombre").fill(categoryName);
  await page.getByPlaceholder("Código").fill(categoryCode);
  await page.getByPlaceholder("Precio base").fill("65000");
  await page.getByPlaceholder("Ocupación máx").fill("2");
  await page.getByPlaceholder("Amenidades").fill("wifi, aire acondicionado");
  await page.getByPlaceholder("Descripción").fill("Categoría de journey E2E");
  await page.getByRole("button", { name: "Agregar categoría", exact: true }).click();
  await expect(page.getByText(`${categoryName} (${categoryCode})`, { exact: true })).toBeVisible();

  const roomCategorySelect = page.locator("select").filter({ hasText: categoryName });
  await expect(roomCategorySelect).toHaveCount(1);
  await roomCategorySelect.selectOption({ label: categoryName });
  await page.getByPlaceholder("Número").fill(roomNumber);
  await page.getByPlaceholder("Piso").fill("2");
  await page.getByPlaceholder("Notas").fill("Habitación de journey E2E");
  await page.getByRole("button", { name: "Agregar habitación", exact: true }).click();
  await expect(page.getByText(`Hab ${roomNumber}`, { exact: false })).toBeVisible();

  await navigateFromShell(page, "/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  const reservationForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(reservationForm).toBeVisible();

  await reservationForm.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
  await reservationForm.getByPlaceholder("Nombre").fill("Huésped");
  await reservationForm.getByPlaceholder("Apellido").fill(guestLastName);
  await reservationForm.getByPlaceholder("Email").fill(`journey.${suffix}@example.test`);
  await reservationForm.getByPlaceholder("Teléfono").fill("1112345678");
  await reservationForm.getByLabel("Tipo de documento").selectOption("DNI");
  await reservationForm.getByPlaceholder("Documento").fill(`E2E-${suffix}`);
  await reservationForm.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = reservationForm.locator("label").filter({ hasText: "Categoría" }).locator("select");
  await expect(categorySelect).toHaveCount(1);
  const categoryOption = categorySelect.locator("option").filter({ hasText: categoryName });
  await expect(categoryOption).toHaveCount(1);
  const categoryValue = await categoryOption.getAttribute("value");
  expect(categoryValue).toBeTruthy();
  await categorySelect.selectOption(categoryValue!);

  const roomSelect = reservationForm.locator("label").filter({ hasText: "Habitación (opcional)" }).locator("select");
  await expect(roomSelect).toHaveCount(1);
  const roomOption = roomSelect.locator("option").filter({ hasText: roomNumber });
  await expect(roomOption).toHaveCount(1);
  const roomValue = await roomOption.getAttribute("value");
  expect(roomValue).toBeTruthy();
  await roomSelect.selectOption(roomValue!);

  const checkIn = reservationForm.locator("label").filter({ hasText: "Check-in" }).locator('input[type="date"]');
  const checkOut = reservationForm.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]');
  await checkIn.fill(localIsoDate(0));
  await checkOut.fill(localIsoDate(1));
  await reservationForm.getByPlaceholder("Usar configuración del hotel").fill("1000");

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

  const reservationTable = page.locator("table").filter({ hasText: "Código" });
  const reservationRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await expect(reservationRow).toHaveCount(1);
  await reservationRow.getByRole("button", { name: "Check-in", exact: true }).click();
  await expect(page.getByText(/Saldo pendiente de .*Cobralo con "Pago total"/)).toBeVisible();
  const editModal = page.locator("div.fixed").filter({ hasText: "Pagos y balance" });
  const editForm = editModal.locator("form").filter({ hasText: "Pagos y balance" });
  await expect(editForm.getByText("Resumen financiero y acciones rápidas.", { exact: true })).toBeVisible();
  const partialAmount = editForm.getByLabel("Monto a cobrar");
  await expect(partialAmount).toBeVisible();
  await partialAmount.fill("70000");
  await editForm.getByRole("button", { name: "Cobro parcial", exact: true }).click();
  await expect(page.getByText("Ingresá un importe positivo que no supere el saldo pendiente.", { exact: true })).toBeVisible();
  await partialAmount.fill("500");
  await editForm.getByRole("button", { name: "Cobro parcial", exact: true }).click();
  await expect(page.getByText("Cobro parcial registrado", { exact: true })).toBeVisible();
  await editForm.getByLabel("Medio de pago").selectOption("bank_transfer");
  await expect(editForm.getByLabel("Imagen del comprobante")).toBeVisible();
  await partialAmount.fill("500");
  await editForm.getByLabel("Imagen del comprobante").setInputFiles({
    name: "transfer-proof.png",
    mimeType: "image/png",
    buffer: await syntheticProofBuffer(page, Number(suffix.slice(-6)))
  });
  await editForm.getByRole("button", { name: "Enviar comprobante", exact: true }).click();
  await expect(page.getByText("Comprobante enviado para aprobación", { exact: true })).toBeVisible();
  await expect(editForm.getByText(/pending$/)).toBeVisible();

  await editForm.getByRole("button", { name: "Rechazar", exact: true }).click();
  await editForm.getByPlaceholder("Motivo del rechazo").fill("Comprobante ilegible");
  await editForm.getByRole("button", { name: "Confirmar rechazo", exact: true }).click();
  await expect(page.getByText("Comprobante rechazado", { exact: true })).toBeVisible();
  const rejectedProof = editForm.locator("li").filter({ hasText: "rejected" });
  await expect(rejectedProof).toContainText("Comprobante ilegible");

  await partialAmount.fill("500");
  await editForm.getByLabel("Imagen del comprobante").setInputFiles({
    name: "transfer-proof-retry.png",
    mimeType: "image/png",
    buffer: await syntheticProofBuffer(page, Number(suffix.slice(-6)) + 1)
  });
  await editForm.getByRole("button", { name: "Enviar comprobante", exact: true }).click();
  await expect(page.getByText("Comprobante enviado para aprobación", { exact: true })).toBeVisible();
  await expect(editForm.locator("li").filter({ hasText: "pending" })).toHaveCount(1);
  await editForm.getByRole("button", { name: "Aprobar", exact: true }).click();
  await expect(editForm.getByText(/approved$/)).toBeVisible();
  await editForm.getByLabel("Medio de pago").selectOption("cash");
  await partialAmount.fill("100");
  page.once("dialog", (dialog) => dialog.accept());
  await editForm.getByRole("button", { name: "Registrar devolución", exact: true }).click();
  await expect(page.getByText("Devolución registrada", { exact: true })).toBeVisible();
  await editForm.getByRole("button", { name: "Pago total", exact: true }).click();
  await expect(page.getByText("Pago completo registrado", { exact: true })).toBeVisible();
  await editModal.getByRole("button", { name: "Cerrar", exact: true }).click();

  const paidRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await expect(paidRow.getByRole("button", { name: "Check-in", exact: true })).toBeEnabled();
  await paidRow.getByRole("button", { name: "Check-in", exact: true }).click();
  // B3.3: this guest (quick "Alta rápida", no birth place/country/marital
  // status/occupation) can't check in yet -- the row action redirects to the
  // reservation panel, which shows the capture form up front instead of a
  // bare 400.
  await expect(
    page.getByText("Faltan datos del huésped para el check-in: completalos en el panel de la reserva.", {
      exact: true
    })
  ).toBeVisible();
  const drawer = page.getByRole("dialog", { name: confirmationCode });
  await expect(drawer).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`reserva=${reservationId}`));
  const captureForm = drawer.getByTestId("checkin-capture-form");
  await expect(captureForm).toBeVisible();
  await captureForm.getByLabel("Lugar de nacimiento").fill("Mendoza");
  await captureForm.getByLabel("País de nacimiento").fill("Argentina");
  await captureForm.getByLabel("Estado civil").fill("Soltero/a");
  await captureForm.getByLabel("Profesión").fill("QA");
  await drawer.getByRole("button", { name: "Confirmar check-in", exact: true }).click();
  await expect(drawer.getByText("Check-in registrado.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Cerrar detalle de reserva" }).click();
  await expect(drawer).not.toBeVisible();

  const checkedInRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await checkedInRow.getByRole("button", { name: "Check-out", exact: true }).click();
  await expect(page.getByText("Check-out registrado", { exact: true })).toBeVisible();

  await navigateFromShell(page, "/caja");
  const closeCashForm = page.locator("form").filter({ hasText: "Cerrar caja" });
  const expectedBalanceLabel = closeCashForm.getByText(/Saldo esperado:/);
  await expect(expectedBalanceLabel).not.toContainText("$ 0,00");
  const expectedBalanceText = await expectedBalanceLabel.innerText();
  const expectedBalance = Number(expectedBalanceText.replace(/[^0-9,.-]/g, "").replace(/\./g, "").replace(",", "."));
  expect(expectedBalance).toBeGreaterThan(0);
  await closeCashForm.locator('input[type="number"]').fill(String(expectedBalance));
  await closeCashForm.getByRole("button", { name: "Cerrar caja", exact: true }).click();
  await expect(page.getByText("Caja cerrada.", { exact: true })).toBeVisible();
  await expect(page.getByText(/Caja sucesora: .* abierta con saldo \$0/)).toBeVisible();
  await expect(page.getByText(/Custodia: recepción confirmada\./)).toBeVisible();
});

test("owner completes guided stock movements through the UI", async ({ page }) => {
  const suffix = Date.now().toString();
  const itemName = `Toallas journey ${suffix}`;
  const sku = `STK-${suffix.slice(-8)}`;

  await login(page);
  await navigateFromShell(page, "/operacion/stock");
  await expect(page.getByRole("heading", { name: "Stock", exact: true })).toBeVisible();

  const locationForm = page.locator("form").filter({ hasText: "Nueva ubicacion" });
  await locationForm.getByLabel("Nombre").fill(`Lencería ${suffix}`);
  await locationForm.getByRole("button", { name: "Crear ubicacion", exact: true }).click();
  await expect(page.getByText("Ubicacion creada.", { exact: true })).toBeVisible();

  const itemForm = page.locator("form").filter({ hasText: "Alta de stock" });
  await itemForm.getByLabel("Nombre").fill(itemName);
  await itemForm.getByLabel("SKU").fill(sku);
  await itemForm.getByLabel("Minimo").fill("2");
  await itemForm.getByRole("button", { name: "Crear item", exact: true }).click();
  await expect(page.getByRole("heading", { name: itemName, exact: true })).toBeVisible();

  const movementForm = page.locator("#stock-movement-form");
  const movementHistory = page.getByRole("region", { name: "Historial reciente", exact: true });
  await page.getByRole("button", { name: `Registrar ingreso de ${itemName}`, exact: true }).click();
  await expect(movementForm.getByRole("heading", { name: "Registrar Ingreso", exact: true })).toBeVisible();
  await movementForm.getByLabel("Item").selectOption({ label: itemName });
  await movementForm.getByText("Opciones avanzadas", { exact: true }).click();
  await movementForm.getByLabel("Ubicacion").selectOption({ label: `Lencería ${suffix}` });
  await movementForm.getByLabel("Cantidad").fill("10");
  await movementForm.getByLabel("Motivo").fill("Compra inicial");
  await movementForm.getByRole("button", { name: "Registrar Ingreso", exact: true }).click();
  await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();
  await expect(movementForm.getByText(/^(?:10|10\.00) unidad$/, { exact: true })).toBeVisible();
  await expect(movementHistory).toContainText(`Ingreso · ${itemName}`);
  await expect(movementHistory).toContainText("Compra inicial");

  await page.getByRole("button", { name: `Registrar egreso de ${itemName}`, exact: true }).click();
  await expect(movementForm.getByRole("heading", { name: "Registrar Egreso", exact: true })).toBeVisible();
  await movementForm.getByLabel("Cantidad").fill("3");
  await movementForm.getByLabel("Motivo").fill("Consumo habitación");
  await movementForm.getByRole("button", { name: "Registrar Egreso", exact: true }).click();
  await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();
  await expect(movementForm.getByText(/^(?:7|7\.00) unidad$/, { exact: true })).toBeVisible();
  await expect(movementHistory).toContainText(`Egreso · ${itemName}`);
  await expect(movementHistory).toContainText("Consumo habitación");

  await movementForm.getByRole("button", { name: /^Ajuste/ }).click();
  await movementForm.getByLabel("Cantidad").fill("1");
  await movementForm.getByLabel("Motivo").fill("Conteo autorizado");
  await movementForm.getByRole("button", { name: "Registrar Ajuste", exact: true }).click();
  await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();
  await expect(movementForm.getByText(/^(?:8|8\.00) unidad$/, { exact: true })).toBeVisible();

  await page.getByRole("button", { name: `Registrar egreso de ${itemName}`, exact: true }).click();
  await movementForm.getByLabel("Cantidad").fill("99");
  await expect(movementForm.getByRole("alert")).toContainText("stock en negativo");
  await expect(movementForm.getByRole("button", { name: "Registrar Egreso", exact: true })).toBeDisabled();
});

test("owner sees an actionable error when a housekeeping status change fails", async ({ page }) => {
  await login(page);
  await navigateFromShell(page, "/habitaciones");

  const roomCard = page.getByText("Hab. 101", { exact: true }).first().locator("..").locator("..").locator("..");
  const statusSelect = roomCard.locator("select");
  await expect(statusSelect).toHaveValue("available");

  await page.route("**/api/rooms/*/status", async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Reasignación temporalmente no disponible" })
    });
  });

  await statusSelect.selectOption("cleaning");
  await expect(roomCard.getByRole("alert")).toContainText("Reasignación temporalmente no disponible");
  await expect(statusSelect).toHaveValue("available");
});

test("owner can complete a housekeeping cleaning cycle", async ({ page }) => {
  await login(page);
  await navigateFromShell(page, "/habitaciones");

  const roomCard = page.getByText("Hab. 101", { exact: true }).first().locator("..").locator("..").locator("..");
  const statusSelect = roomCard.locator("select");
  await expect(statusSelect).toHaveValue("available");

  await statusSelect.selectOption("cleaning");
  await expect(statusSelect).toHaveValue("cleaning");
  await statusSelect.selectOption("available");
  await expect(statusSelect).toHaveValue("available");
});

test("owner manages a room move and no-show from the reservation ficha", async ({ page }) => {
  const suffix = Date.now().toString();
  const categoryName = `Operación ${suffix}`;
  const categoryCode = `O${suffix.slice(-6)}`;
  const firstRoomNumber = `O${suffix.slice(-5)}A`;
  const secondRoomNumber = `O${suffix.slice(-5)}B`;
  const guestLastName = `Operación ${suffix}`;

  await login(page);

  await navigateFromShell(page, "/settings/hotel");
  await page.getByPlaceholder("Nombre").fill(categoryName);
  await page.getByPlaceholder("Código").fill(categoryCode);
  await page.getByPlaceholder("Precio base").fill("72000");
  await page.getByPlaceholder("Ocupación máx").fill("2");
  await page.getByPlaceholder("Amenidades").fill("wifi");
  await page.getByPlaceholder("Descripción").fill("Categoría de operaciones E2E");
  await page.getByRole("button", { name: "Agregar categoría", exact: true }).click();
  await expect(page.getByText(`${categoryName} (${categoryCode})`, { exact: true })).toBeVisible();

  const roomCategorySelect = page.locator("select").filter({ hasText: categoryName });
  await roomCategorySelect.selectOption({ label: categoryName });
  await page.getByPlaceholder("Número").fill(firstRoomNumber);
  await page.getByPlaceholder("Piso").fill("3");
  await page.getByPlaceholder("Notas").fill("Habitación origen de operaciones E2E");
  await page.getByRole("button", { name: "Agregar habitación", exact: true }).click();
  await expect(page.getByText(`Hab ${firstRoomNumber}`, { exact: false })).toBeVisible();

  await roomCategorySelect.selectOption({ label: categoryName });
  await page.getByPlaceholder("Número").fill(secondRoomNumber);
  await page.getByPlaceholder("Piso").fill("3");
  await page.getByPlaceholder("Notas").fill("Habitación destino de operaciones E2E");
  await page.getByRole("button", { name: "Agregar habitación", exact: true }).click();
  await expect(page.getByText(`Hab ${secondRoomNumber}`, { exact: false })).toBeVisible();

  await navigateFromShell(page, "/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  const reservationForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await reservationForm.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
  await reservationForm.getByPlaceholder("Nombre").fill("Huésped");
  await reservationForm.getByPlaceholder("Apellido").fill(guestLastName);
  await reservationForm.getByPlaceholder("Email").fill(`operations.${suffix}@example.test`);
  await reservationForm.getByPlaceholder("Teléfono").fill("1112345678");
  await reservationForm.getByLabel("Tipo de documento").selectOption("DNI");
  await reservationForm.getByPlaceholder("Documento").fill(`OPS-${suffix}`);
  await reservationForm.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = reservationForm.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: categoryName });
  await expect(categoryOption).toHaveCount(1);
  const categoryValue = await categoryOption.getAttribute("value");
  expect(categoryValue).toBeTruthy();
  await categorySelect.selectOption(categoryValue!);
  const roomSelect = reservationForm.locator("label").filter({ hasText: "Habitación (opcional)" }).locator("select");
  const roomOption = roomSelect.locator("option").filter({ hasText: firstRoomNumber });
  await expect(roomOption).toHaveCount(1);
  const roomValue = await roomOption.getAttribute("value");
  expect(roomValue).toBeTruthy();
  await roomSelect.selectOption(roomValue!);
  await reservationForm.locator("label").filter({ hasText: "Check-in" }).locator('input[type="date"]').fill(localIsoDate(2));
  await reservationForm.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]').fill(localIsoDate(4));
  await expect(reservationForm.getByRole("button", { name: "Crear", exact: true })).toBeEnabled();
  await reservationForm.getByRole("button", { name: "Crear", exact: true }).click();
  await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();

  const reservationTable = page.locator("table").filter({ hasText: "Código" });
  const reservationRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await expect(reservationRow).toHaveCount(1);
  await reservationRow.getByRole("button", { name: "Ficha", exact: true }).click();

  const detailsModal = page.locator("div.fixed").filter({ hasText: "Ficha" });
  await expect(detailsModal.getByRole("heading", { name: /Reserva/ })).toBeVisible();
  const stayOperations = detailsModal.getByRole("region", { name: "Operaciones de estadía" });
  await expect(stayOperations).toBeVisible();
  const destinationSelect = stayOperations.getByLabel("Habitación destino");
  const destinationOption = destinationSelect.locator("option").filter({ hasText: secondRoomNumber });
  await expect(destinationOption).toHaveCount(1);
  const destinationValue = await destinationOption.getAttribute("value");
  expect(destinationValue).toBeTruthy();
  await destinationSelect.selectOption(destinationValue!);
  await stayOperations.getByLabel("Motivo del cambio").fill("Cambio operativo");
  await stayOperations.getByLabel("Notas del cambio").fill("Mantenimiento preventivo de la habitación origen");
  await stayOperations.getByRole("button", { name: "Mover habitación", exact: true }).click();
  await expect(page.getByText("Habitación cambiada.", { exact: true })).toBeVisible();
  await expect(detailsModal).toContainText(`Hab ${secondRoomNumber}`);

  await stayOperations.getByLabel("Notas del no-show").fill("No se presentó al horario límite");
  page.once("dialog", (dialog) => dialog.accept());
  await stayOperations.getByRole("button", { name: "Marcar no-show", exact: true }).click();
  await expect(page.getByText("No-show registrado.", { exact: true })).toBeVisible();
  await expect(detailsModal).toContainText("No-show");
});

test("owner operates waitlist, housekeeping, laundry and daily reports", async ({ page }, testInfo) => {
  const salt = projectDateSalt(testInfo);
  // WebKit clamps Date.now() precision, so concurrent device projects can
  // get the exact same millisecond suffix. Append the (already per-project
  // unique) date salt to keep the waitlist note text unique too.
  const suffix = `${Date.now()}-${salt}`;
  const checkIn = localIsoDate(20 + salt);
  const checkOut = localIsoDate(22 + salt);

  await login(page);

  await navigateFromShell(page, "/operacion/lista-espera");
  const waitlistForm = page.locator("form").filter({ hasText: "Agregar espera" });
  await expect(waitlistForm).toBeVisible();
  const guestSelect = waitlistForm.getByLabel("Huesped");
  const categorySelect = waitlistForm.getByLabel("Categoria");
  await expect(guestSelect.locator("option").filter({ hasText: "Huesped E2E" })).toHaveCount(1);
  await expect(categorySelect.locator("option").filter({ hasText: "Standard E2E" })).toHaveCount(1);
  const guestValue = await guestSelect.locator("option").filter({ hasText: "Huesped E2E" }).getAttribute("value");
  const categoryValue = await categorySelect.locator("option").filter({ hasText: "Standard E2E" }).getAttribute("value");
  expect(guestValue).toBeTruthy();
  expect(categoryValue).toBeTruthy();
  await guestSelect.selectOption(guestValue!);
  await categorySelect.selectOption(categoryValue!);
  await waitlistForm.getByLabel("Check-in").fill(checkIn);
  await waitlistForm.getByLabel("Check-out").fill(checkOut);
  await waitlistForm.getByLabel("Notas").fill(`Disponibilidad solicitada ${suffix}`);
  await waitlistForm.getByRole("button", { name: "Agregar a espera", exact: true }).click();
  await expect(page.getByText("Entrada agregada a la lista de espera.", { exact: true })).toBeVisible();

  const waitlistCard = page
    .locator("div.rounded-xl.border.p-4")
    .filter({ hasText: "Huesped E2E" })
    .filter({ hasText: `Disponibilidad solicitada ${suffix}` });
  await expect(waitlistCard).toHaveCount(1);
  await waitlistCard.getByRole("button", { name: "Promover", exact: true }).click();

  const promotionForm = page.locator("form").filter({ hasText: "Promocion" });
  await expect(promotionForm.getByRole("button", { name: "Promover a reserva", exact: true })).toBeEnabled();
  const promoteRoom = promotionForm.getByLabel("Habitacion");
  const roomOption = promoteRoom.locator("option").filter({ hasText: "Hab. 101" });
  await expect(roomOption).toHaveCount(1);
  const roomValue = await roomOption.getAttribute("value");
  expect(roomValue).toBeTruthy();
  await promoteRoom.selectOption(roomValue!);
  await promotionForm.getByLabel("Notas de reserva").fill("Promoción operativa E2E");
  await promotionForm.getByRole("button", { name: "Promover a reserva", exact: true }).click();
  await expect(page.getByText("Entrada promovida a reserva.", { exact: true })).toBeVisible();
  await expect(waitlistCard).toContainText("Promovida");

  await navigateFromShell(page, "/habitaciones");
  const housekeepingCard = page.getByText("Hab. 102", { exact: true }).first().locator("..").locator("..").locator("..");
  await expect(housekeepingCard).toBeVisible();
  await housekeepingCard.locator("select").selectOption("cleaning");
  await expect(housekeepingCard).toContainText("Limpieza");

  // D2 (Via D lavanderia): vendor + remito flow replaced the old
  // LaundryBatch/LaundryItem lifecycle UI entirely (D0 confirmed no open
  // batches in production). Create a vendor, give it a price, register an
  // opening stock at a house location, then send an outbound remito and
  // confirm it lands in the vendor balance.
  await navigateFromShell(page, "/operacion/stock");
  const stockLocationName = `Deposito blancos ${suffix}`;
  const stockItemName = `Sabanas E2E ${suffix}`;
  const locationForm = page.locator("form").filter({ hasText: "Nueva ubicacion" });
  await locationForm.getByLabel("Nombre").fill(stockLocationName);
  await locationForm.getByRole("button", { name: "Crear ubicacion", exact: true }).click();
  await expect(page.getByText("Ubicacion creada.", { exact: true })).toBeVisible();

  const itemForm = page.locator("form").filter({ hasText: "Alta de stock" });
  await itemForm.getByLabel("Nombre").fill(stockItemName);
  await itemForm.getByRole("button", { name: "Crear item", exact: true }).click();
  await expect(page.getByRole("heading", { name: stockItemName, exact: true })).toBeVisible();

  await page.getByRole("button", { name: `Registrar ingreso de ${stockItemName}`, exact: true }).click();
  const movementForm = page.locator("#stock-movement-form");
  await movementForm.getByText("Opciones avanzadas", { exact: true }).click();
  await movementForm.getByLabel("Ubicacion").selectOption({ label: stockLocationName });
  await movementForm.getByLabel("Cantidad").fill("10");
  await movementForm.getByLabel("Motivo").fill("Stock inicial ropa blanca E2E");
  await movementForm.getByRole("button", { name: "Registrar Ingreso", exact: true }).click();
  await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();

  // Ropa blanca vive en su propia tabla/API (linen_items/linen_locations),
  // separada del stock general recien cargado arriba -- StockPage ya no
  // puede targetear un item de linen (ver laundry-vendor-cycle-journey.spec.ts).
  // Sin este alta dedicada, el "Ítem" de mas abajo nunca encuentra la opcion.
  await navigateFromShell(page, "/operacion/lavanderia");
  const linenItemName = `Sabanas E2E ${suffix}`;
  const linenLocationName = `Deposito blancos lavanderia E2E ${suffix}`;
  const linenItemForm = page.locator("form").filter({ hasText: "Nuevo tipo de ropa blanca" });
  await linenItemForm.getByLabel("Nombre").fill(linenItemName);
  await linenItemForm.getByRole("button", { name: "Crear tipo de ropa blanca", exact: true }).click();
  await expect(page.getByText("Tipo de ropa blanca creado.", { exact: true })).toBeVisible();

  const linenLocationForm = page.locator("form").filter({ hasText: "Nueva ubicación" });
  await linenLocationForm.getByLabel("Nombre").fill(linenLocationName);
  await linenLocationForm.getByRole("button", { name: "Crear ubicación", exact: true }).click();
  await expect(page.getByText("Ubicacion de lavanderia creada.", { exact: true })).toBeVisible();

  const linenMovementForm = page.locator("form").filter({ hasText: "Registrar movimiento" });
  await linenMovementForm.getByLabel("Ítem").selectOption({ label: linenItemName });
  await linenMovementForm.getByLabel("Ubicación").selectOption({ label: linenLocationName });
  await linenMovementForm.getByRole("button", { name: "Ingreso", exact: true }).click();
  await linenMovementForm.getByLabel("Cantidad").fill("10");
  await linenMovementForm.getByLabel("Motivo").fill("Stock inicial ropa blanca E2E");
  await linenMovementForm.getByRole("button", { name: "Registrar movimiento", exact: true }).click();
  await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();

  const vendorName = `Lavadero E2E ${suffix}`;
  const vendorForm = page.locator("form").filter({ hasText: "Nuevo lavadero" });
  await vendorForm.getByLabel("Nombre").fill(vendorName);
  await vendorForm.getByRole("button", { name: "Crear lavadero", exact: true }).click();
  await expect(page.getByText(`Lavadero "${vendorName}" creado.`, { exact: true })).toBeVisible();

  const priceForm = page.locator("form").filter({ hasText: "Guardar precio" });
  await priceForm.getByLabel("Ítem").selectOption({ label: linenItemName });
  await priceForm.getByLabel("Precio por unidad").fill("200");
  await priceForm.getByRole("button", { name: "Guardar precio", exact: true }).click();
  await expect(page.getByText("Precio guardado.", { exact: true })).toBeVisible();

  const remitoForm = page.locator("form").filter({ hasText: "Nuevo remito" });
  await remitoForm.getByRole("button", { name: "Salida (se lleva sucia)", exact: true }).click();
  await remitoForm.getByLabel("Lavadero").selectOption({ label: vendorName });
  await remitoForm.getByLabel("Ubicación casa (origen/destino en el hotel)").selectOption({ label: linenLocationName });
  await remitoForm.getByLabel("N° de remito (papel)").fill(`R-${suffix}`);
  const remitoLineForm = remitoForm.locator("div").filter({ hasText: "Líneas" }).last();
  await remitoLineForm.getByLabel("Ítem").selectOption({ label: linenItemName });
  await remitoLineForm.getByLabel("Cant.").fill("4");
  await remitoLineForm.getByRole("button", { name: "Agregar línea", exact: true }).click();
  await expect(remitoForm).toContainText(`${linenItemName} × 4`);
  await expect(remitoForm.getByText(/Total estimado:\s*\$\s*800/)).toBeVisible();
  await remitoForm.getByRole("button", { name: "Guardar remito", exact: true }).click();
  await expect(page.getByText(`Remito R-${suffix} guardado.`, { exact: true })).toBeVisible();

  const vendorBalance = page
    .getByRole("region", { name: "Qué está en cada lavadero ahora", exact: true })
    .locator("div.rounded-lg.border.border-slate-200.bg-slate-50.p-3")
    .filter({ hasText: vendorName });
  await expect(vendorBalance).toContainText(linenItemName);
  await expect(vendorBalance).toContainText("4");

  await navigateFromShell(page, "/reportes");
  await expect(page.getByRole("heading", { name: "Reportes", exact: true })).toBeVisible();
  await expect(page.getByText("Llegadas del dia", { exact: true })).toBeVisible();
  const reportDate = page.getByLabel("Fecha");
  const reportResponse = page.waitForResponse(
    (response) => response.url().includes("/api/reports/operational/daily") && response.status() === 200
  );
  await reportDate.fill(localIsoDate(21));
  await reportResponse;
  await expect(page.getByText("Estado operativo", { exact: true })).toBeVisible();
  await expect(page.getByText("Riesgos operativos", { exact: true })).toBeVisible();

  // Cleanup: the waitlist promotion above pins room 101 for
  // localIsoDate(20..22). The WebKit Apple business matrix reruns this exact
  // spec once per device project against the shared database, so leaving
  // this reservation pending would make the next device run fail room
  // availability with a false "Room 101 is not available" negative.
  await navigateFromShell(page, "/reservas");
  const reservationsTable = page.locator("table").filter({ hasText: "Código" });
  // Filter by check-in date too: the 3 concurrent device projects promote
  // the same "Huesped E2E" guest, so the guest name alone is not unique
  // while all 3 runs are in flight against the shared database.
  const promotedRow = reservationsTable
    .locator("tbody tr")
    .filter({ hasText: "Huesped E2E" })
    .filter({ hasText: checkIn });
  await expect(promotedRow).toHaveCount(1);
  await promotedRow.getByRole("button", { name: "Cancelar", exact: true }).click();
  await expect(page.getByText("Reserva cancelada", { exact: true })).toBeVisible();
});
