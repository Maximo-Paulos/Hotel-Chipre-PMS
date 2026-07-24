import { test, expect } from "@playwright/test";

const email = process.env.E2E_MASTER_EMAIL || "master-admin@e2e.com";
const password = process.env.E2E_MASTER_PASSWORD || "E2eMasterPass1234!";
const pin = process.env.E2E_MASTER_PIN || "123456";

async function primaryNavigation(page: import("@playwright/test").Page) {
  const mobileNavigation = page.getByRole("navigation", { name: "Navegación master móvil" });

  if (await mobileNavigation.isVisible()) {
    return mobileNavigation;
  }

  return page.locator("aside nav");
}

test.describe.serial("Master admin smoke", () => {
  test("login and open dashboard", async ({ page }) => {
    await page.goto("/adminpmsmaster/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Contraseña").fill(password);
    await page.getByLabel("PIN del panel").fill(pin);
    await page.getByRole("button", { name: "Entrar al panel" }).click();

    await page.waitForURL("**/adminpmsmaster/dashboard", { timeout: 15_000 });
    await expect(page.getByText("Operación de plataforma")).toBeVisible();
    await expect(page.getByText("Policy actual")).toBeVisible();

    const viewportWidth = await page.evaluate(() => window.innerWidth);
    if (viewportWidth < 768) {
      await expect(page.getByRole("navigation", { name: "Navegación master móvil" })).toBeVisible();
      const pageWidth = await page.evaluate(() => document.documentElement.scrollWidth);
      expect(pageWidth).toBeLessThanOrEqual(viewportWidth);
    }
  });

  test("navigate to billing and audit sections", async ({ page }) => {
    await page.goto("/adminpmsmaster/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Contraseña").fill(password);
    await page.getByLabel("PIN del panel").fill(pin);
    await page.getByRole("button", { name: "Entrar al panel" }).click();
    await page.waitForURL("**/adminpmsmaster/dashboard", { timeout: 15_000 });

    const navigation = await primaryNavigation(page);
    await navigation.getByRole("link", { name: "Billing Policy" }).click();
    await expect(page.getByText("Paywall central")).toBeVisible();

    await navigation.getByRole("link", { name: "Audit Log" }).click();
    await expect(page.getByText("Trazabilidad")).toBeVisible();
  });
});
