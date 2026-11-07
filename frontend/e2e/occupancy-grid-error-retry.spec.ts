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
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("planilla offers an explicit retry after a transient grid read failure", async ({ page }) => {
  let allowGridRequests = false;
  await login(page);
  await page.route("**/api/reservations/occupancy-grid**", async (route) => {
    if (!allowGridRequests) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Temporary QA service failure" })
      });
      return;
    }
    await route.continue();
  });

  await page.goto("/operacion/planilla");
  const retry = page.getByTestId("occupancy-grid-retry");
  await expect(retry).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("No se pudo cargar la planilla");

  allowGridRequests = true;
  await retry.click();
  await expect(page.getByTestId("occupancy-grid")).toBeVisible();
  await expect(retry).toHaveCount(0);
});
