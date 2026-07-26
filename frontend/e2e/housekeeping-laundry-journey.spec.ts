import { expect, test, type Page } from "@playwright/test";

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

async function login(page: Page, credentials: { email: string; password: string }) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

async function logout(page: Page) {
  await page.getByTestId("logout-btn").click();
  await page.waitForURL("**/login");
}

test("housekeeping sends a laundry remito on a vendor set up by the owner", async ({ page }) => {
  const suffix = Date.now().toString();
  const vendorName = `QA HK Lavadero ${suffix}`;
  const locationName = `QA HK Deposito ${suffix}`;
  const itemName = `QA HK Toallas ${suffix}`;

  await login(page, owner);

  await page.goto("/operacion/stock");
  const locationForm = page.locator("form").filter({ hasText: "Nueva ubicacion" });
  await locationForm.getByLabel("Nombre").fill(locationName);
  await locationForm.getByRole("button", { name: "Crear ubicacion", exact: true }).click();
  await expect(page.getByText("Ubicacion creada.", { exact: true })).toBeVisible();

  const itemForm = page.locator("form").filter({ hasText: "Alta de stock" });
  await itemForm.getByLabel("Nombre").fill(itemName);
  await itemForm.getByRole("button", { name: "Crear item", exact: true }).click();
  await expect(page.getByRole("heading", { name: itemName, exact: true })).toBeVisible();

  await page.getByRole("button", { name: `Registrar ingreso de ${itemName}`, exact: true }).click();
  const movementForm = page.locator("#stock-movement-form");
  await movementForm.getByText("Opciones avanzadas", { exact: true }).click();
  await movementForm.getByLabel("Ubicacion").selectOption({ label: locationName });
  await movementForm.getByLabel("Cantidad").fill("8");
  await movementForm.getByLabel("Motivo").fill("Stock inicial QA housekeeping");
  await movementForm.getByRole("button", { name: "Registrar Ingreso", exact: true }).click();
  await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();

  await page.goto("/operacion/lavanderia");
  const vendorForm = page.locator("form").filter({ hasText: "Nuevo lavadero" });
  await vendorForm.getByLabel("Nombre").fill(vendorName);
  await vendorForm.getByRole("button", { name: "Crear lavadero", exact: true }).click();
  await expect(page.getByText(`Lavadero "${vendorName}" creado.`, { exact: true })).toBeVisible();
  await logout(page);

  await login(page, housekeeping);
  await expect(page.getByTestId("session-role")).toHaveText("Housekeeping");
  await page.goto("/operacion/lavanderia");

  const main = page.locator("main");
  await expect(main.getByRole("heading", { name: "Lavanderia", exact: true })).toBeVisible();
  // housekeeping never sees the vendor/pricing admin panel at all -- it's
  // gated by laundry:manage_vendors, not just the "Crear lavadero" button.
  await expect(main.getByRole("button", { name: "Crear lavadero" })).toHaveCount(0);
  await expect(main.getByText("Lavaderos y precios", { exact: false })).toHaveCount(0);

  const remitoForm = main.locator("form").filter({ hasText: "Nuevo remito" });
  await remitoForm.getByRole("button", { name: "Salida (se lleva sucia)", exact: true }).click();
  await remitoForm.getByLabel("Lavadero").selectOption({ label: vendorName });
  await remitoForm.getByLabel("Ubicación casa (origen/destino en el hotel)").selectOption({ label: locationName });
  await remitoForm.getByLabel("N° de remito (papel)").fill(`R-HK-${suffix}`);
  const remitoLineForm = remitoForm.locator("div").filter({ hasText: "Líneas" }).last();
  await remitoLineForm.getByLabel("Ítem").selectOption({ label: itemName });
  await remitoLineForm.getByLabel("Cant.").fill("5");
  await remitoLineForm.getByRole("button", { name: "Agregar línea", exact: true }).click();
  await expect(remitoForm).toContainText(`${itemName} × 5`);
  await remitoForm.getByRole("button", { name: "Guardar remito", exact: true }).click();
  // No price was set for this vendor/item (out of scope for a permission
  // test), so the success message also carries the "sin precio" warning --
  // assert the guardado fragment is present, not the whole string.
  await expect(page.getByText(`Remito R-HK-${suffix} guardado.`, { exact: false })).toBeVisible();

  const vendorBalance = main
    .locator("div.rounded-lg.border.border-slate-200.bg-slate-50.p-3")
    .filter({ hasText: vendorName });
  await expect(vendorBalance).toContainText(itemName);
  await expect(vendorBalance).toContainText("5");
});
