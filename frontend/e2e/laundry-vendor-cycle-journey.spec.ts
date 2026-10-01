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

function nextIsoDay(value: string) {
  const nextDay = new Date(`${value}T12:00:00.000Z`);
  nextDay.setUTCDate(nextDay.getUTCDate() + 1);
  return nextDay.toISOString().slice(0, 10);
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
  await expect(page.getByText("Ubicación de lavandería creada.", { exact: true })).toBeVisible();

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
  const historicalEffectiveFrom = await priceForm.getByLabel("Vigente desde").inputValue();

  // Combined entry: one row per item with a Retiro (sale sucia) and an
  // Entrego (vuelve limpia) quantity side by side, mirroring the vendor's
  // paper remito -- see LaundryPage.tsx's "Nuevo remito" form.
  const remitoForm = page.locator("form").filter({ hasText: "Nuevo remito" });

  // --- Remito de salida: 6 sabanas + 4 toallas, total estimado 6*150 + 4*250 = 1900 ---
  await remitoForm.getByLabel("Lavadero").selectOption({ label: vendorName });
  await remitoForm.getByLabel("Ubicación casa (origen/destino en el hotel)").selectOption({ label: locationName });
  // Keep the first outbound remito tied to the original price's effective
  // date, so the later future-price change has a stable historical baseline.
  await remitoForm.getByLabel("Fecha").fill(historicalEffectiveFrom);
  await remitoForm.getByLabel("N° de remito (papel)").fill(`R-OUT-${suffix}`);
  await remitoForm.getByLabel(`Retiro ${sheetsName}`, { exact: true }).fill("6");
  await remitoForm.getByLabel(`Retiro ${towelsName}`, { exact: true }).fill("4");
  await expect(remitoForm.getByText(/Total estimado \(retiro\):\s*\$\s*1\.?900/)).toBeVisible();

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
  await remitoForm.getByLabel("N° de remito (papel)").fill(`R-IN-${suffix}`);
  await remitoForm.getByLabel(`Entrego ${sheetsName}`, { exact: true }).fill("3");
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
  await remitoForm.getByLabel("N° de remito (papel)").fill(`R-FAIL-${suffix}`);
  await remitoForm.getByLabel(`Retiro ${towelsName}`, { exact: true }).fill("999");
  await remitoForm.getByRole("button", { name: "Guardar remito", exact: true }).click();
  await expect(remitoForm.getByRole("alert")).toContainText("Not enough");
  await expect(remitoForm.getByRole("alert")).toContainText(towelsName);
  // No exitoso: el remito invalido no queda en el historial.
  await expect(page.getByText(`Remito R-FAIL-${suffix} guardado.`, { exact: true })).toHaveCount(0);

  // F-048: a price change starts on its configured date. Keep both effective
  // rows visible, preview the future price for a remito dated tomorrow, then
  // return to the historical date and confirm the original price still wins.
  // The spend report below also verifies that the already-saved remito keeps
  // its frozen unit-price snapshot after this new row is added.
  const futureEffectiveFrom = nextIsoDay(historicalEffectiveFrom);
  await priceForm.getByLabel("Ítem").selectOption({ label: sheetsName });
  await priceForm.getByLabel("Precio por unidad").fill("175");
  await priceForm.getByLabel("Vigente desde").fill(futureEffectiveFrom);
  await priceForm.getByRole("button", { name: "Guardar precio", exact: true }).click();
  await expect(page.getByText("Precio guardado.", { exact: true })).toBeVisible();

  const priceHistory = page.getByText(`Precios de ${vendorName}`, { exact: true }).locator("..").getByRole("list");
  const sheetPriceRows = priceHistory.getByRole("listitem").filter({ hasText: sheetsName });
  await expect(sheetPriceRows).toHaveCount(2);
  await expect(sheetPriceRows.filter({ hasText: `desde ${historicalEffectiveFrom}` })).toContainText(/\$\s*150/);
  await expect(sheetPriceRows.filter({ hasText: `desde ${futureEffectiveFrom}` })).toContainText(/\$\s*175/);

  await remitoForm.getByLabel("Fecha").fill(futureEffectiveFrom);
  await remitoForm.getByLabel(`Retiro ${sheetsName}`, { exact: true }).fill("1");
  await remitoForm.getByLabel(`Retiro ${towelsName}`, { exact: true }).fill("0");
  await expect(remitoForm.getByText(/Total estimado \(retiro\):\s*\$\s*175/)).toBeVisible();

  await remitoForm.getByLabel("Fecha").fill(historicalEffectiveFrom);
  await expect(remitoForm.getByText(/Total estimado \(retiro\):\s*\$\s*150/)).toBeVisible();

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
