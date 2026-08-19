import { expect, test, type Page } from "@playwright/test";

// Fase 7 (goal maestro): recorrido completo del inventario operativo, no solo
// gating de permisos. Cubre: alta de item/ubicacion, ingreso, egreso, ajuste
// en ambas direcciones (alta y baja de stock), previsualizacion antes de
// confirmar, busqueda de reserva por huesped/codigo, asociacion de un
// movimiento a una reserva, bloqueo de stock negativo (egreso y ajuste a la
// baja) y alerta de bajo stock. Usa la persona owner (unico rol con
// stock:adjust) para poder probar el flujo de Ajuste completo.
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

test("owner runs the full inventory journey: item/location, movements, adjustment in both directions, reservation link, negative guard and low-stock alert", async ({
  page
}) => {
  const suffix = Date.now().toString();
  const itemName = `QA-Sabanas ${suffix}`;
  const locationName = `QA-Deposito ${suffix}`;
  const categoryName = `QA-Stock ${suffix}`;
  const categoryCode = `QS${suffix.slice(-6)}`;
  const roomNumber = `QS${suffix.slice(-5)}`;
  const guestLastName = `QA-Stock ${suffix}`;

  await login(page);

  // Reserva "anfitriona" para probar la busqueda por huesped/codigo y la
  // asociacion de un movimiento de stock (item 6 y 7 del checklist).
  await page.goto("/settings/hotel");
  await page.getByPlaceholder("Nombre").fill(categoryName);
  await page.getByPlaceholder("Código").fill(categoryCode);
  await page.getByPlaceholder("Precio base").fill("50000");
  await page.getByPlaceholder("Ocupación máx").fill("2");
  await page.getByRole("button", { name: "Agregar categoría", exact: true }).click();
  await expect(page.getByText(`${categoryName} (${categoryCode})`, { exact: true })).toBeVisible();

  const roomCategorySelect = page.locator("select").filter({ hasText: categoryName });
  await roomCategorySelect.selectOption({ label: categoryName });
  await page.getByPlaceholder("Número").fill(roomNumber);
  await page.getByRole("button", { name: "Agregar habitación", exact: true }).click();
  await expect(page.getByText(`Hab ${roomNumber}`, { exact: false })).toBeVisible();

  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  const reservationForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await reservationForm.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
  await reservationForm.getByPlaceholder("Nombre").fill("Huésped");
  await reservationForm.getByPlaceholder("Apellido").fill(guestLastName);
  await reservationForm.getByPlaceholder("Email").fill(`qa.stock.${suffix}@example.test`);
  await reservationForm.getByPlaceholder("Teléfono").fill("1112345678");
  await reservationForm.getByLabel("Tipo de documento").selectOption("DNI");
  await reservationForm.getByPlaceholder("Documento").fill(`QA-STOCK-${suffix}`);
  await reservationForm.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = reservationForm.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: categoryName });
  const categoryValue = await categoryOption.getAttribute("value");
  await categorySelect.selectOption(categoryValue!);
  const roomSelect = reservationForm.locator("label").filter({ hasText: "Habitación (opcional)" }).locator("select");
  const roomOption = roomSelect.locator("option").filter({ hasText: roomNumber });
  const roomValue = await roomOption.getAttribute("value");
  await roomSelect.selectOption(roomValue!);

  const localIsoDate = (offsetDays: number) => {
    const value = new Date();
    value.setDate(value.getDate() + offsetDays);
    const pad = (part: number) => String(part).padStart(2, "0");
    return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
  };
  await reservationForm.locator("label").filter({ hasText: "Check-in" }).locator('input[type="date"]').fill(localIsoDate(50));
  await reservationForm.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]').fill(localIsoDate(52));
  await reservationForm.getByRole("button", { name: "Crear", exact: true }).click();
  await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();

  const reservationTable = page.locator("table").filter({ hasText: "Código" });
  const reservationRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await expect(reservationRow).toHaveCount(1);
  const confirmationCode = (await reservationRow.locator("td").first().textContent())?.trim();
  expect(confirmationCode).toBeTruthy();

  // --- Inventario: alta de ubicacion e item (item 1) ---
  await page.goto("/operacion/stock");
  await expect(page.getByRole("heading", { name: "Stock", exact: true })).toBeVisible();

  const locationForm = page.locator("form").filter({ hasText: "Nueva ubicacion" });
  await locationForm.getByLabel("Nombre").fill(locationName);
  await locationForm.getByRole("button", { name: "Crear ubicacion", exact: true }).click();
  await expect(page.getByText("Ubicacion creada.", { exact: true })).toBeVisible();

  const itemForm = page.locator("form").filter({ hasText: "Alta de stock" });
  await itemForm.getByLabel("Nombre").fill(itemName);
  await itemForm.getByLabel("Minimo").fill("5");
  await itemForm.getByRole("button", { name: "Crear item", exact: true }).click();
  await expect(page.getByRole("heading", { name: itemName, exact: true })).toBeVisible();

  const movementForm = page.locator("#stock-movement-form");
  const movementHistory = page.getByRole("region", { name: "Historial reciente", exact: true });

  // --- Camino rapido por default (D4 parte 1): item -> tipo -> cantidad -> confirmar,
  // sin tocar "Opciones avanzadas". Ubicacion y reserva quedan colapsadas y no deben
  // hacer falta para un movimiento simple (item 2, con previsualizacion, item 5).
  const advancedOptionsToggle = movementForm.getByText("Opciones avanzadas", { exact: true });
  await page.getByRole("button", { name: `Registrar ingreso de ${itemName}`, exact: true }).click();
  await movementForm.getByLabel("Item").selectOption({ label: itemName });
  await expect(movementForm.getByLabel("Ubicacion")).toBeHidden();
  await movementForm.getByLabel("Cantidad").fill("10");
  await movementForm.getByLabel("Motivo").fill("Compra inicial QA");
  await expect(movementForm.getByText("Resultado previsto:", { exact: false })).toContainText("10.00 unidad");
  await movementForm.getByRole("button", { name: "Registrar Ingreso", exact: true }).click();
  await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();
  await expect(movementForm.getByText(/^(?:10|10\.00) unidad$/, { exact: true })).toBeVisible();

  // --- Egreso (item 3), abriendo "Opciones avanzadas" para vincular a una reserva
  // buscada por apellido (items 6 y 7) -- confirma que el camino avanzado sigue
  // disponible y funcional cuando se lo necesita.
  await page.getByRole("button", { name: `Registrar egreso de ${itemName}`, exact: true }).click();
  await movementForm.getByLabel("Cantidad").fill("4");
  await movementForm.getByLabel("Motivo").fill("Consumo huésped QA");
  await advancedOptionsToggle.click();
  // Not selecting locationName here: the ingreso above deliberately used the
  // quick default path (no location, see D4 parte 1), and register_movement
  // now validates an outbound movement against ONLY the location it names
  // (stock_service.py's "an outbound movement scoped to one location must
  // only be checked against THAT location's balance" fix) -- so drawing this
  // egreso from a named location that never received stock would correctly
  // fail as "would make stock negative". Stay on "Sin ubicacion" (the same
  // hotel-wide bucket the ingreso wrote to) to keep exercising the advanced
  // options' reservation-search field without that false negative.
  const reservationSearchInput = movementForm.getByPlaceholder("Buscar huésped o código");
  await reservationSearchInput.fill(guestLastName);
  const reservationSelect = movementForm.locator("select").filter({ hasText: "Sin reserva asociada" });
  await expect(reservationSelect.locator("option").filter({ hasText: guestLastName })).toHaveCount(1);
  // La busqueda por codigo tambien debe encontrar la misma reserva.
  await reservationSearchInput.fill(confirmationCode!);
  await expect(reservationSelect.locator("option").filter({ hasText: confirmationCode! })).toHaveCount(1);
  const reservationOptionValue = await reservationSelect
    .locator("option")
    .filter({ hasText: confirmationCode! })
    .getAttribute("value");
  await reservationSelect.selectOption(reservationOptionValue!);
  await expect(movementForm.getByText("Resultado previsto:", { exact: false })).toContainText("6.00 unidad");
  await movementForm.getByRole("button", { name: "Registrar Egreso", exact: true }).click();
  await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();
  await expect(movementForm.getByText(/^(?:6|6\.00) unidad$/, { exact: true })).toBeVisible();
  await expect(movementHistory).toContainText(`Egreso · ${itemName}`);
  await expect(movementHistory).toContainText(`Reserva ${confirmationCode}`);

  // --- Ajuste al alza (item 4, direccion "encontre mas") ---
  await movementForm.getByRole("button", { name: /^Ajuste/ }).click();
  await expect(movementForm.getByRole("button", { name: "Encontré más stock" })).toHaveAttribute("aria-pressed", "true");
  await movementForm.getByLabel("Cantidad").fill("2");
  await movementForm.getByLabel("Motivo").fill("Conteo QA: aparecieron unidades");
  await expect(movementForm.getByText("Resultado previsto:", { exact: false })).toContainText("8.00 unidad");
  await movementForm.getByRole("button", { name: "Registrar Ajuste", exact: true }).click();
  await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();
  await expect(movementForm.getByText(/^(?:8|8\.00) unidad$/, { exact: true })).toBeVisible();
  await expect(movementHistory).toContainText(`Ajuste (alta) · ${itemName}`);

  // --- Ajuste a la baja (item 4, la correccion real de esta sesion) ---
  await movementForm.getByRole("button", { name: /^Ajuste/ }).click();
  await movementForm.getByRole("button", { name: "Encontré menos stock" }).click();
  await movementForm.getByLabel("Cantidad").fill("3");
  await movementForm.getByLabel("Motivo").fill("Conteo QA: faltan unidades");
  await expect(movementForm.getByRole("alert")).toHaveCount(0);
  await expect(movementForm.getByText("Resultado previsto:", { exact: false })).toContainText("5.00 unidad");
  await movementForm.getByRole("button", { name: "Registrar Ajuste", exact: true }).click();
  await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();
  await expect(movementForm.getByText(/^(?:5|5\.00) unidad$/, { exact: true })).toBeVisible();
  await expect(movementHistory).toContainText(`Ajuste (baja) · ${itemName}`);
  await expect(movementHistory).toContainText("Conteo QA: faltan unidades");

  // --- Bloqueo de stock negativo tambien para el ajuste a la baja (item 8) ---
  await movementForm.getByRole("button", { name: /^Ajuste/ }).click();
  await movementForm.getByRole("button", { name: "Encontré menos stock" }).click();
  await movementForm.getByLabel("Cantidad").fill("999");
  await movementForm.getByLabel("Motivo").fill("Intento invalido QA");
  await expect(movementForm.getByRole("alert")).toContainText("stock en negativo");
  await expect(movementForm.getByRole("button", { name: "Registrar Ajuste", exact: true })).toBeDisabled();

  // --- Bajo stock (item 9): un ultimo egreso deja el stock por debajo del minimo (5) ---
  await page.getByRole("button", { name: `Registrar egreso de ${itemName}`, exact: true }).click();
  await movementForm.getByLabel("Cantidad").fill("1");
  await movementForm.getByLabel("Motivo").fill("Ultimo consumo QA");
  await movementForm.getByRole("button", { name: "Registrar Egreso", exact: true }).click();
  await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();
  await expect(movementForm.getByText(/^(?:4|4\.00) unidad$/, { exact: true })).toBeVisible();

  const itemCard = page
    .locator("div.rounded-xl.border.border-slate-200.bg-white.p-4.shadow-sm")
    .filter({ hasText: itemName });
  await expect(itemCard.getByText("Bajo", { exact: true })).toBeVisible();

  // --- D5 (Via D): reporte de consumo por periodo refleja los egresos/ajustes
  // de baja de esta sesion (4 egreso + 3 ajuste a la baja + 1 egreso = 8), no
  // los 10 de ingreso ni los 2 de ajuste al alza. Rango explicito y amplio
  // (en vez del preset "Semana actual") para no depender de a que lado de la
  // medianoche UTC/local cae "hoy" en el navegador de e2e.
  const consumptionSection = page.locator("section").filter({ hasText: "Consumo de stock por periodo" });
  await consumptionSection.getByLabel("Desde").fill(localIsoDate(-10));
  await consumptionSection.getByLabel("Hasta").fill(localIsoDate(1));
  const consumptionRow = consumptionSection.locator("tbody tr").filter({ hasText: itemName });
  await expect(consumptionRow).toContainText("8.00 unidad");

  // --- Editar item completo (owner: "editar el producto por las dudas"):
  // nombre, SKU, unidad y minimo, no solo el costo por unidad (ese ya tenia
  // su propio campo inline, UnitCostField). Bajar el minimo de 5 a 2 tambien
  // prueba que el cambio se aplico de verdad: el stock actual (4) pasa de
  // "Bajo" a "OK".
  const editedItemName = `${itemName} editado`;
  const editModal = page.getByRole("dialog", { name: "Editar item de stock" });
  await itemCard.getByRole("button", { name: `Editar ${itemName}`, exact: true }).click();
  await expect(editModal).toBeVisible();
  await editModal.locator("input").nth(0).fill(editedItemName);
  await editModal.locator("input").nth(1).fill(`QA-EDITED-${suffix}`);
  await editModal.locator("input").nth(2).fill("paquete");
  await editModal.locator("input").nth(3).fill("2");
  await editModal.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(page.getByText("Item actualizado.", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: editedItemName, exact: true })).toBeVisible();
  const editedItemCard = page
    .locator("div.rounded-xl.border.border-slate-200.bg-white.p-4.shadow-sm")
    .filter({ hasText: editedItemName });
  await expect(editedItemCard.getByText("QA-EDITED-" + suffix, { exact: true })).toBeVisible();
  await expect(editedItemCard.getByText(/^4(?:\.00)? paquete$/, { exact: true })).toBeVisible();
  await expect(editedItemCard.getByText("OK", { exact: true })).toBeVisible();

  // --- Eliminar item (item 10, D4 parte 3): boton "Eliminar" pide confirmacion
  // via un modal propio (no window.confirm -- algunos navegadores embebidos
  // moviles no renderizan dialogos JS nativos, ver ConfirmDialog.tsx).
  const confirmDialog = page.getByRole("alertdialog", { name: "Eliminar item de stock" });
  await editedItemCard.getByRole("button", { name: `Eliminar ${editedItemName}`, exact: true }).click();
  await expect(confirmDialog).toBeVisible();
  await confirmDialog.getByRole("button", { name: "Cancelar", exact: true }).click();
  await expect(confirmDialog).toBeHidden();
  await expect(page.getByRole("heading", { name: editedItemName, exact: true })).toBeVisible();

  await editedItemCard.getByRole("button", { name: `Eliminar ${editedItemName}`, exact: true }).click();
  await expect(confirmDialog).toBeVisible();
  await confirmDialog.getByRole("button", { name: "Eliminar", exact: true }).click();
  await expect(page.getByText("Item eliminado.", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: editedItemName, exact: true })).toHaveCount(0);
});
