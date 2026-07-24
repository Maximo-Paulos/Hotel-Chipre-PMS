import { expect, test, type Page } from "@playwright/test";

const ownerEmail = process.env.E2E_OWNER_EMAIL || "owner@e2e.com";
const ownerPassword = process.env.E2E_OWNER_PASSWORD || "E2ePass1234!";

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(ownerEmail);
  await page.locator('input[type="password"]').fill(ownerPassword);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

test.describe("Responsive mobile smoke", () => {
  test("dashboard fits an iPhone viewport and exposes operational navigation", async ({ page }) => {
    await login(page);

    await expect(page.getByTestId("dashboard-mobile-reservations")).toBeVisible();
    await expect(page.locator('nav[aria-label="Navegación móvil"] a[href="/reservas"]')).toBeVisible();
    await expect(
      page.getByRole("option", {
        name: "Hotel Chipre E2E con un nombre operacionalmente largo (ID 1)",
        exact: true
      })
    ).toBeAttached();

    for (const [width, height] of [[375, 812], [390, 844], [430, 932]]) {
      await test.step(`viewport ${width}x${height}`, async () => {
        await page.setViewportSize({ width, height });
        const layout = await page.evaluate(() => ({
          viewportWidth: window.innerWidth,
          documentScrollWidth: document.documentElement.scrollWidth,
          bodyScrollWidth: document.body.scrollWidth
        }));

        expect(layout.viewportWidth).toBe(width);
        expect(layout.documentScrollWidth).toBeLessThanOrEqual(layout.viewportWidth);
        expect(layout.bodyScrollWidth).toBeLessThanOrEqual(layout.viewportWidth);
      });
    }
  });

  test("mobile navigation reaches reservations", async ({ page }) => {
    await login(page);

    const reservationsLink = page.locator('nav[aria-label="Navegación móvil"] a[href="/reservas"]');
    await reservationsLink.click();
    await expect(page).toHaveURL(/\/reservas$/);
    await expect(page.locator("main").getByRole("heading", { name: "Reservas", exact: true })).toBeVisible();
  });
});
