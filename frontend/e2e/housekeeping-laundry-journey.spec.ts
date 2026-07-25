import { expect, test, type Page } from "@playwright/test";

// Full laundry cycle for the housekeeping role: manager/owner creates the
// batch (housekeeping cannot -- POST /api/laundry/batches is manager+ only,
// already covered by role-journey.spec.ts), then housekeeping does the real
// daily work: list, add items, walk the batch through every status, and see
// it in the history/filtered list afterward.
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

test("housekeeping runs the laundry cycle on a batch created by the owner", async ({ page }) => {
  const suffix = Date.now().toString();

  await login(page, owner);
  await page.goto("/operacion/lavanderia");
  const createBatchForm = page.locator("form").filter({ hasText: "Crear lote" });
  await createBatchForm.getByLabel("Notas").fill(`QA housekeeping cycle ${suffix}`);
  await createBatchForm.getByRole("button", { name: "Crear lote", exact: true }).click();
  await expect(page.getByText("Lote de lavanderia creado.", { exact: true })).toBeVisible();
  await logout(page);

  await login(page, housekeeping);
  await expect(page.getByTestId("session-role")).toHaveText("Housekeeping");
  await page.goto("/operacion/lavanderia");

  const main = page.locator("main");
  // housekeeping never gets an inline "creado" toast for this batch (it wasn't
  // theirs), so locate it by the notes text instead of relying on freshness.
  const batchCard = main.getByRole("button").filter({ hasText: `QA housekeeping cycle ${suffix}` });
  await expect(batchCard).toBeVisible();
  await expect(main.getByRole("button", { name: "Crear lote" })).toHaveCount(0);
  await batchCard.click();

  const detail = main.locator("section").filter({ hasText: "Detalle" }).last();
  const itemForm = detail.locator("form");
  await expect(itemForm.getByLabel("Tipo de item")).toBeVisible();
  await itemForm.getByLabel("Tipo de item").fill(`QA sabanas ${suffix}`);
  await itemForm.getByLabel("Cantidad").fill("3");
  await itemForm.getByRole("button", { name: "Agregar item", exact: true }).click();
  await expect(page.getByText("Item agregado al lote.", { exact: true })).toBeVisible();
  await expect(detail).toContainText(`QA sabanas ${suffix}`);
  await expect(detail).toContainText("x3");

  await expect(batchCard).toContainText("Recolectado");
  for (const [nextLabel, confirmation] of [
    ["Marcar Enviado", "Enviado"],
    ["Marcar Recibido", "Recibido"],
    ["Marcar Cerrado", "Cerrado"]
  ] as const) {
    await batchCard.getByText(nextLabel, { exact: true }).click();
    await expect(page.getByText("Estado de lavanderia actualizado.", { exact: true })).toBeVisible();
    await expect(batchCard).toContainText(confirmation);
  }
  await expect(batchCard.getByText("Lote cerrado", { exact: true })).toBeVisible();

  // Historial: el filtro por estado sigue mostrando el lote ya cerrado.
  const statusFilter = main.locator("header").getByRole("combobox");
  await statusFilter.selectOption("closed");
  await expect(batchCard).toBeVisible();
});
