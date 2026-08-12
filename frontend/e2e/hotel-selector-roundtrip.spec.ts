import { expect, test, type Page, type Route } from "@playwright/test";

const owner = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

const requestedHotelId = (route: Route) => route.request().headers()["x-hotel-id"];

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(owner.email);
  await page.locator('input[type="password"]').fill(owner.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("the hotel selector preserves the authorized list across a two-hotel round trip", async ({ page }) => {
  // Model the server-issued multi-hotel membership contract at the network
  // boundary. The regression is exercised entirely through the visible
  // selector; the test neither writes nor reads localStorage.
  await page.route("**/api/auth/login", async (route) => {
    const response = await route.fetch();
    const payload = (await response.json()) as Record<string, unknown>;
    await route.fulfill({ response, json: { ...payload, hotel_ids: [1, 2] } });
  });

  await page.route("**/api/config/", async (route) => {
    if (requestedHotelId(route) !== "2") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      json: { id: 2, hotel_name: "Hotel Dos E2E" }
    });
  });

  await page.route("**/api/permissions/effective", async (route) => {
    if (requestedHotelId(route) !== "2") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      json: {
        hotel_id: 2,
        role: "owner",
        permissions: ["permissions:manage", "reports:operational:view", "reports:financial:view"]
      }
    });
  });

  await page.route("**/api/onboarding/status", async (route) => {
    if (requestedHotelId(route) !== "2") {
      await route.continue();
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", json: { completed: true } });
  });

  await login(page);

  const selector = page.getByLabel("Hotel activo", { exact: true });
  await expect(selector).toBeEnabled();
  await expect(selector.locator("option")).toHaveCount(3);
  await expect(selector.locator('option[value="1"]')).toContainText("Hotel Chipre E2E");
  await expect(selector.locator('option[value="2"]')).toContainText("Hotel Dos E2E");

  await selector.selectOption("2");
  await page.getByRole("button", { name: "Aplicar", exact: true }).click();
  await expect(page.getByText("Hotel ID 2", { exact: true })).toBeVisible();
  await expect(selector).toHaveValue("2");
  await expect(selector.locator('option[value="1"]')).toBeAttached();
  await expect(selector.locator('option[value="2"]')).toBeAttached();

  await selector.selectOption("1");
  await page.getByRole("button", { name: "Aplicar", exact: true }).click();
  await expect(page.getByText("Hotel ID 1", { exact: true })).toBeVisible();
  await expect(selector).toHaveValue("1");
  await expect(selector.locator('option[value="1"]')).toBeAttached();
  await expect(selector.locator('option[value="2"]')).toBeAttached();
});
