import { expect, test, type Page } from "@playwright/test";

const credentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

test("owner can save an enabled transfer method without completing the category draft", async ({ page }) => {
  await login(page);
  await page.goto("/settings/hotel");

  const transferMethod = page.locator("label").filter({ hasText: "Transferencia" }).locator('input[type="checkbox"]');
  await expect(transferMethod).toHaveCount(1);
  await transferMethod.check();
  await page.getByLabel("Check-in desde").fill("14:00");
  await page.getByLabel("Check-out hasta").fill("10:00");

  await page.getByRole("button", { name: "Guardar cambios", exact: true }).click();
  await expect(page.getByText("Cambios guardados.", { exact: true })).toBeVisible();

  await page.reload();
  await expect(transferMethod).toBeChecked();
  await expect(page.getByLabel("Check-in desde")).toHaveValue("14:00");
  await expect(page.getByLabel("Check-out hasta")).toHaveValue("10:00");
});

test("owner can configure and persist a percentage rule for one night and one-night deposits for longer stays", async ({ page }) => {
  await login(page);
  await page.goto("/settings/hotel");

  const rules = page.getByTestId("settings-deposit-policy-rules");
  await expect(rules).toBeVisible();
  await rules.getByLabel("Límite de noches de regla 1").fill("1");
  await rules.getByLabel("Tipo de seña de regla 1").selectOption("percentage");
  await rules.getByLabel("Valor de seña de regla 1").fill("30");
  await rules.getByRole("button", { name: "Agregar rango de estadía" }).click();
  await expect(rules.getByText("Desde 2 noches")).toBeVisible();
  await rules.getByLabel("Tipo de seña de regla 2").selectOption("nights");
  await rules.getByLabel("Valor de seña de regla 2").fill("1");

  const confirmation = page.getByLabel("Confirmo que las reglas mostradas fueron definidas por este hotel.");
  if (!(await confirmation.isChecked())) await confirmation.check();
  await page.getByRole("button", { name: "Guardar cambios", exact: true }).click();
  await expect(page.getByText("Cambios guardados.", { exact: true })).toBeVisible();

  await page.reload();
  const savedRules = page.getByTestId("settings-deposit-policy-rules");
  await expect(savedRules.getByLabel("Límite de noches de regla 1")).toHaveValue("1");
  await expect(savedRules.getByLabel("Tipo de seña de regla 1")).toHaveValue("percentage");
  await expect(savedRules.getByLabel("Valor de seña de regla 1")).toHaveValue("30");
  await expect(savedRules.getByText("Desde 2 noches")).toBeVisible();
  await expect(savedRules.getByLabel("Tipo de seña de regla 2")).toHaveValue("nights");
  await expect(savedRules.getByLabel("Valor de seña de regla 2")).toHaveValue("1");
  await expect(confirmation).toBeChecked();
});
