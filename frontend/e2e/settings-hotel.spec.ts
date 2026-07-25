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

  await page.getByRole("button", { name: "Guardar cambios", exact: true }).click();
  await expect(page.getByText("Cambios guardados.", { exact: true })).toBeVisible();

  await page.reload();
  await expect(transferMethod).toBeChecked();
});
