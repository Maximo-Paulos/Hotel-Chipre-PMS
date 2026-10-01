import { expect, test } from "@playwright/test";

const owner = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

test("F-052: quick availability filters have distinct accessible labels", async ({ page }) => {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(owner.email);
  await page.locator('input[type="password"]').fill(owner.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard");
  await page.goto("/reservas");

  await expect(page.getByLabel("Categoría para disponibilidad")).toBeVisible();
  await expect(page.getByLabel("Check-in para disponibilidad")).toBeVisible();
  await expect(page.getByLabel("Check-out para disponibilidad")).toBeVisible();
});
