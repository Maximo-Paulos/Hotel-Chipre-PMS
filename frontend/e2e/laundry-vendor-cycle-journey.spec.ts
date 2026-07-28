import { expect, test, type Page } from "@playwright/test";

// D2 (Via D lavanderia): full outsourced-laundry cycle -- vendor + price
// catalog, an outbound remito (dirty linen leaves the hotel), the vendor
// balance reflecting it, a partial inbound remito (some of it comes back
// clean) dropping the vendor balance and raising the house's own stock back
// up, and the insufficient-stock guard on an oversized outbound remito
// surfacing the backend's real message instead of a generic failure. See
// app/services/laundry_vendor_service.py::create_remito for the two
// StockMovements-per-line transfer this exercises end to end.
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

test("owner runs the full vendor/remito cycle: pricing, outbound, partial inbound, and an insufficient-stock rejection", async ({
  page
}) => {
  const suffix = Date.now().toString();
  const vendorName = `QA Cycle Lavadero ${suffix}`;
  const locationName = `QA Cycle Deposito ${suffix}`;
  const sheetsName = `QA Cycle Sabanas ${suffix}`;
  const towelsName = `QA Cycle Toallas ${suffix}`;

  await login(page);

  // D (stock/lavanderia separation, split real): ropa blanca vive en su
  // propia tabla/API (linen_items/linen_locations/linen_movements) --
  // alta de item, ubicacion y carga de stock inicial se hacen todas desde
  // LaundryPage, StockPage ya no puede targetear un item de linen.
  await page.goto("/operacion/lavanderia");
  const linenItemForm = page.locator("form").filter({ hasText: "Nuevo tipo de ropa blanca" });
  for (const itemName of [sheetsName, towelsName]) {
    await linenItemForm.getByLabel("Nombre").fill(itemName);
    await linenItemForm.getByRole("button", { name: "Crear tipo de ropa blanca", exact: true }).click();
    await expect(page.getByText("Tipo de ropa blanca creado.", { exact: true })).toBeVisible();
  }

  // --- Stock inicial: dos items, 10 unidades de cada uno en la ubicacion casa ---
  const linenLocationForm = page.locator("form").filter({ hasText: "Nueva ubicación" });
  await linenLocationForm.getByLabel("Nombre").fill(locationName);
  await linenLocationForm.getByRole("button", { name: "Crear ubicación", exact: true }).click();
  await expect(page.getByText("Ubicacion de lavanderia creada.", { exact: true })).toBeVisible();

  const linenMovementForm = page.locator("form").filter({ hasText: "Registrar movimiento" });
  for (const itemName of [sheetsName, towelsName]) {
    await linenMovementForm.getByLabel("Ítem").selectOption({ label: itemName });
    await linenMovementForm.getByLabel("Ubicación").selectOption({ label: locationName });
    await linenMovementForm.getByRole("button", { name: "Ingreso", exact: true }).click();
    await linenMovementForm.getByLabel("Cantidad").fill("10");
    await linenMovementForm.getByLabel("Motivo").fill("Stock inicial QA cycle");
    await linenMovementForm.getByRole("button", { name: "Registrar movimiento", exact: true }).click();
    await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();
  }

  // --- Alta de lavadero + precio para los dos items ---
  await page.goto("/operacion/lavanderia");
  const vendorForm = page.locator("form").filter({ hasText: "Nuevo lavadero" });
  await vendorForm.getByLabel("Nombre").fill(vendorName);
  await vendorForm.getByRole("button", { name: "Crear lavadero", exact: true }).click();
  await expect(page.getByText(`Lavadero "${vendorName}" creado.`, { exact: true })).toBeVisible();

  const priceForm = page.locator("form").filter({ hasText: "Guardar precio" });
  for (const [itemName, price] of [
    [sheetsName, "150"],
    [towelsName, "250"]
  ]) {
    await priceForm.getByLabel("Ítem").selectOption({ label: itemName });
    await priceForm.getByLabel("Precio por unidad").fill(price);
    await priceForm.getByRole("button", { name: "Guardar precio", exact: true }).click();
    await expect(page.getByText("Precio guardado.", { exact: true })).toBeVisible();
  }

  const remitoForm = page.locator("form").filter({ hasText: "Nuevo remito" });
  const remitoLineForm = remitoForm.locator("div").filter({ hasText: "Líneas" }).last();

  // --- Remito de salida: 6 sabanas + 4 toallas, total estimado 6*150 + 4*250 = 1900 ---
  await remitoForm.getByRole("button", { name: "Salida (se lleva sucia)", exact: true }).click();
  await remitoForm.getByLabel("Lavadero").selectOption({ label: vendorName });
  await remitoForm.getByLabel("Ubicación casa (origen/destino en el hotel)").selectOption({ label: locationName });
  await remitoForm.getByLabel("N° de remito (papel)").fill(`R-OUT-${suffix}`);

  await remitoLineForm.getByLabel("Ítem").selectOption({ label: sheetsName });
  await remitoLineForm.getByLabel("Cant.").fill("6");
  await remitoLineForm.getByRole("button", { name: "Agregar línea", exact: true }).click();
  await remitoLineForm.getByLabel("Ítem").selectOption({ label: towelsName });
  await remitoLineForm.getByLabel("Cant.").fill("4");
  await remitoLineForm.getByRole("button", { name: "Agregar línea", exact: true }).click();
  await expect(remitoForm.getByText(/Total estimado:\s*\$\s*1\.?900/)).toBeVisible();

  await remitoForm.getByRole("button", { name: "Guardar remito", exact: true }).click();
  await expect(page.getByText(`Remito R-OUT-${suffix} guardado.`, { exact: true })).toBeVisible();

  const vendorBalance = page
    .getByRole("region", { name: "Qué está en cada lavadero ahora", exact: true })
    .locator("div.rounded-lg.border.border-slate-200.bg-slate-50.p-3")
    .filter({ hasText: vendorName });
  await expect(vendorBalance).toContainText(sheetsName);
  await expect(vendorBalance).toContainText("6");
  await expect(vendorBalance).toContainText(towelsName);
  await expect(vendorBalance).toContainText("4");

  // --- Remito de entrada parcial: vuelven 3 de las 6 sabanas ---
  await remitoForm.getByRole("button", { name: "Entrada (trae limpia)", exact: true }).click();
  await remitoForm.getByLabel("N° de remito (papel)").fill(`R-IN-${suffix}`);
  await remitoLineForm.getByLabel("Ítem").selectOption({ label: sheetsName });
  await remitoLineForm.getByLabel("Cant.").fill("3");
  await remitoLineForm.getByRole("button", { name: "Agregar línea", exact: true }).click();
  await remitoForm.getByRole("button", { name: "Guardar remito", exact: true }).click();
  await expect(page.getByText(`Remito R-IN-${suffix} guardado.`, { exact: true })).toBeVisible();

  // Balance del lavadero: sabanas bajan de 6 a 3, toallas siguen en 4.
  await expect(vendorBalance).toContainText("3");
  await expect(vendorBalance).toContainText(towelsName);
  await expect(vendorBalance).toContainText("4");

  // Stock de casa: arranco en 10, salieron 6 (quedan 4), volvieron 3 (quedan 7).
  const houseStockPanel = page.getByRole("region", { name: "Limpio disponible en el hotel", exact: true });
  await houseStockPanel.getByLabel("Ubicación").selectOption({ label: locationName });
  const sheetsRow = houseStockPanel.locator("li").filter({ hasText: sheetsName });
  await expect(sheetsRow).toContainText("7");

  // --- Intento de remito de salida mayor al disponible: rechazo con mensaje claro ---
  await remitoForm.getByRole("button", { name: "Salida (se lleva sucia)", exact: true }).click();
  await remitoForm.getByLabel("N° de remito (papel)").fill(`R-FAIL-${suffix}`);
  await remitoLineForm.getByLabel("Ítem").selectOption({ label: towelsName });
  await remitoLineForm.getByLabel("Cant.").fill("999");
  await remitoLineForm.getByRole("button", { name: "Agregar línea", exact: true }).click();
  await remitoForm.getByRole("button", { name: "Guardar remito", exact: true }).click();
  await expect(remitoForm.getByRole("alert")).toContainText("Not enough");
  await expect(remitoForm.getByRole("alert")).toContainText(towelsName);
  // No exitoso: el remito invalido no queda en el historial.
  await expect(page.getByText(`Remito R-FAIL-${suffix} guardado.`, { exact: true })).toHaveCount(0);

  // --- D3: reporte de gasto del mes actual cubre el remito de salida (6
  // sabanas * 150 + 4 toallas * 250 = 1900) y no el remito de entrada (no
  // se factura) ni el intento fallido (nunca se creo). El total global de la
  // seccion suma todos los lavaderos del hotel (puede incluir otros vendors
  // de otros specs corriendo sobre la misma DB), asi que se valida el total
  // y el desglose *de este vendor* -- vendor_spend() ya esta aislado por
  // vendor_id en el backend -- en vez del total agregado de la pagina.
  const spendSection = page.locator("section").filter({ hasText: "Gasto de lavadero por período" });
  await spendSection.getByRole("button", { name: "Mes actual", exact: true }).click();
  const vendorSpendCard = spendSection.locator("div.rounded-lg.border.border-slate-200.bg-slate-50.p-3").filter({
    hasText: vendorName
  });
  await expect(vendorSpendCard.getByText(/\$\s*1\.?900/)).toBeVisible();
  await expect(vendorSpendCard).toContainText(`${sheetsName} × 6`);
  await expect(vendorSpendCard.getByText(/\$\s*900/)).toBeVisible();
  await expect(vendorSpendCard).toContainText(`${towelsName} × 4`);
  await expect(vendorSpendCard.getByText(/\$\s*1\.?000/)).toBeVisible();
});
