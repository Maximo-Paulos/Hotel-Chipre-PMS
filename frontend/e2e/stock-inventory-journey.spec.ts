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
  const destinationLocationName = `QA-Piso ${suffix}`;
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
  await reservationForm.getByPlaceholder("Teléfono").fill(`11${Date.now().toString().slice(-8)}${Math.floor(Math.random() * 100).toString().padStart(2, "0")}`);
  await reservationForm.getByLabel("Tipo de documento").selectOption("DNI");
  await reservationForm.getByPlaceholder("Documento").fill(`QA-STOCK-${suffix}`);
  await reservationForm.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = reservationForm.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: categoryName });
  const categoryValue = await categoryOption.getAttribute("value");
  await categorySelect.selectOption(categoryValue!);

  const localIsoDate = (offsetDays: number) => {
    const value = new Date();
    value.setDate(value.getDate() + offsetDays);
    const pad = (part: number) => String(part).padStart(2, "0");
    return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
  };
  await reservationForm.getByLabel("Check-in", { exact: true }).fill(localIsoDate(50));
  await reservationForm.getByLabel("Check-out", { exact: true }).fill(localIsoDate(52));

  const roomSelect = reservationForm.locator("label").filter({ hasText: "Habitación (opcional)" }).locator("select");
  const roomOption = roomSelect.locator("option").filter({ hasText: roomNumber });
  const roomValue = await roomOption.getAttribute("value");
  await roomSelect.selectOption(roomValue!);

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

  const locationForm = page.locator("form").filter({ hasText: "Nueva ubicación" });
  await locationForm.getByLabel("Nombre").fill(locationName);
  await locationForm.getByRole("button", { name: "Crear ubicación", exact: true }).click();
  await expect(page.getByText("Ubicación creada.", { exact: true })).toBeVisible();

  await locationForm.getByLabel("Nombre").fill(destinationLocationName);
  await locationForm.getByRole("button", { name: "Crear ubicación", exact: true }).click();
  await expect(page.getByText("Ubicación creada.", { exact: true })).toBeVisible();

  const itemForm = page.locator("form").filter({ hasText: "Alta de stock" });
  await itemForm.getByLabel("Nombre").fill(itemName);
  await itemForm.getByLabel("Mínimo").fill("5");
  await itemForm.getByRole("button", { name: "Crear item", exact: true }).click();
  await expect(page.getByRole("heading", { name: itemName, exact: true })).toBeVisible();

  const movementForm = page.locator("#stock-movement-form");
  const movementHistory = page.getByRole("region", { name: "Historial reciente", exact: true });

  // La ubicación queda visible y se limpia después de guardar, para evitar que
  // un movimiento siguiente reutilice el último depósito por accidente.
  const advancedOptionsToggle = movementForm.getByText("Opciones avanzadas", { exact: true });
  await page.getByRole("button", { name: `Registrar ingreso de ${itemName}`, exact: true }).click();
  await movementForm.getByLabel("Item").selectOption({ label: itemName });
  const locationSelect = movementForm.getByLabel("Ubicación (opcional)");
  await expect(locationSelect).toBeVisible();
  await locationSelect.selectOption({ label: locationName });
  await movementForm.getByLabel("Cantidad").fill("10");
  await movementForm.getByLabel("Motivo").fill("Compra inicial QA");
  await expect(movementForm.getByText("Resultado previsto:", { exact: false })).toContainText("10.00 unidad");
  await movementForm.getByRole("button", { name: "Registrar Ingreso", exact: true }).click();
  await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();
  await expect(locationSelect).toHaveValue("");
  await expect(page.getByRole("list", { name: `Stock de ${itemName} por ubicación`, exact: true })).toContainText(
    "10.00 unidad"
  );
  await expect(movementForm.getByText(/^(?:10|10\.00) unidad$/, { exact: true })).toBeVisible();

  // --- Egreso (item 3), abriendo "Opciones avanzadas" para vincular a una reserva
  // buscada por apellido (items 6 y 7) -- confirma que el camino avanzado sigue
  // disponible y funcional cuando se lo necesita.
  await page.getByRole("button", { name: `Registrar egreso de ${itemName}`, exact: true }).click();
  await movementForm.getByLabel("Cantidad").fill("4");
  await movementForm.getByLabel("Motivo").fill("Consumo huésped QA");
  await locationSelect.selectOption({ label: locationName });
  await advancedOptionsToggle.click();
  // The reservation association remains an optional audit link; the balance
  // and negative-stock preview are now scoped to the chosen location.
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

  // --- D5 (Via D): reporte de consumo por periodo refleja solo los egresos
  // ordinarios (4 + 1 = 5), no los ajustes. Rango explicito y amplio
  // (en vez del preset "Semana actual") para no depender de a que lado de la
  // medianoche UTC/local cae "hoy" en el navegador de e2e.
  const consumptionSection = page.locator("section").filter({ hasText: "Consumo de stock por periodo" });
  await consumptionSection.getByLabel("Desde").fill(localIsoDate(-10));
  await consumptionSection.getByLabel("Hasta").fill(localIsoDate(1));
  const consumptionRow = consumptionSection.locator("tbody tr").filter({ hasText: itemName });
  await expect(consumptionRow).toContainText("5.00 unidad");

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

  // --- F-022: alta por grilla y traspaso entre ubicaciones ---
  const transferItemName = `QA-Toallas ${suffix}`;
  await itemForm.getByLabel("Nombre").fill(transferItemName);
  await itemForm.getByRole("button", { name: "Crear item", exact: true }).click();
  await expect(page.getByRole("heading", { name: transferItemName, exact: true })).toBeVisible();

  const openingCountForm = page.locator("#stock-opening-count-form");
  await openingCountForm.getByLabel("Ubicación del conteo inicial").selectOption({ label: locationName });
  await openingCountForm.getByLabel(`Conteo inicial ${transferItemName}`).fill("10");
  await openingCountForm.getByLabel("Motivo").fill("Inventario inicial QA");
  await openingCountForm.getByRole("button", { name: "Guardar conteo inicial", exact: true }).click();
  await expect(page.getByText("Conteo inicial guardado para 1 item.", { exact: true })).toBeVisible();

  const transferForm = page.locator("#stock-transfer-form");
  await transferForm.getByLabel("Item del traspaso").selectOption({ label: transferItemName });
  await transferForm.getByLabel("Ubicación de origen").selectOption({ label: locationName });
  await transferForm.getByLabel("Ubicación de destino").selectOption({ label: destinationLocationName });
  await transferForm.getByLabel("Cantidad").fill("3");
  await transferForm.getByLabel("Motivo").fill("Reposición de piso QA");
  await expect(transferForm.getByText("Resultado previsto:", { exact: false })).toContainText("7.00");
  await expect(transferForm.getByText("Resultado previsto:", { exact: false })).toContainText("3.00");
  await transferForm.getByRole("button", { name: "Registrar traspaso", exact: true }).click();
  await expect(page.getByText("Traspaso registrado.", { exact: true })).toBeVisible();

  const transferItemCard = page
    .locator("div.rounded-xl.border.border-slate-200.bg-white.p-4.shadow-sm")
    .filter({ hasText: transferItemName });
  const transferLocationBalances = transferItemCard.getByRole("list", {
    name: `Stock de ${transferItemName} por ubicación`, exact: true
  });
  await expect(transferItemCard).toContainText("10.00");
  await expect(transferLocationBalances).toContainText("7.00 unidad");
  await expect(transferLocationBalances).toContainText("3.00 unidad");

  // The same transfer flow is available on the task-based mobile tab.
  await page.setViewportSize({ width: 390, height: 844 });
  const transferTab = page.getByRole("tab", { name: "Traspaso", exact: true });
  await expect(transferTab).toBeVisible();
  await transferTab.click();
  await expect(transferForm).toBeVisible();
  await transferForm.getByLabel("Ubicación de origen").selectOption({ label: destinationLocationName });
  await transferForm.getByLabel("Ubicación de destino").selectOption({ label: locationName });
  await transferForm.getByLabel("Cantidad").fill("1");
  await transferForm.getByLabel("Motivo").fill("Retorno desde móvil QA");
  await transferForm.getByRole("button", { name: "Registrar traspaso", exact: true }).click();
  await expect(page.getByText("Traspaso registrado.", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Resumen", exact: true }).click();
  await expect(transferItemCard.getByRole("list", { name: `Stock de ${transferItemName} por ubicación`, exact: true }))
    .toContainText("8.00 unidad");
  await expect(transferItemCard.getByRole("list", { name: `Stock de ${transferItemName} por ubicación`, exact: true }))
    .toContainText("2.00 unidad");

  await page.getByRole("tab", { name: "Historial", exact: true }).click();
  await expect(movementHistory).toContainText(`Traspaso · salida · ${transferItemName}`);
  await expect(movementHistory).toContainText(`Traspaso · ingreso · ${transferItemName}`);

  await page.getByRole("tab", { name: "Carga inicial", exact: true }).click();
  await openingCountForm.getByLabel("Ubicación del conteo inicial").selectOption({ label: locationName });
  await expect(openingCountForm.getByLabel(`Conteo inicial ${transferItemName}`)).toBeDisabled();
});
