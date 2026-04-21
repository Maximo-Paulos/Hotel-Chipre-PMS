import { test, expect, APIRequestContext } from "@playwright/test";

const apiBase = process.env.E2E_API_URL || "http://localhost:8000";
const email = "platform-admin@example.com";
const password = "Master123!";
const pin = process.env.E2E_MASTER_PIN || "1234";

async function bootstrapMasterAdmin(request: APIRequestContext) {
  const response = await request.post(`${apiBase}/api/auth/register`, {
    data: { email, password, role: "platform_admin" }
  });
  expect(response.ok()).toBeTruthy();
  const payload = await response.json();
  if (payload.requires_verification) {
    if (!payload.code) {
      test.skip(true, "Master admin bootstrap requires auto-verify or exposed auth codes in the test environment.");
    }
    const verify = await request.post(`${apiBase}/api/auth/verify-email`, {
      data: { email, code: payload.code }
    });
    expect(verify.ok()).toBeTruthy();
  }
}

test.describe.serial("Master admin smoke", () => {
  test.beforeAll(async ({ request }) => {
    await bootstrapMasterAdmin(request);
  });

  test("login and open dashboard", async ({ page }) => {
    await page.goto("/adminpmsmaster/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Contraseña").fill(password);
    await page.getByLabel("PIN del panel").fill(pin);
    await page.getByRole("button", { name: "Entrar al panel" }).click();

    await page.waitForURL("**/adminpmsmaster/dashboard", { timeout: 15_000 });
    await expect(page.getByText("Operación de plataforma")).toBeVisible();
    await expect(page.getByText("Policy actual")).toBeVisible();
  });

  test("navigate to billing and audit sections", async ({ page }) => {
    await page.goto("/adminpmsmaster/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Contraseña").fill(password);
    await page.getByLabel("PIN del panel").fill(pin);
    await page.getByRole("button", { name: "Entrar al panel" }).click();
    await page.waitForURL("**/adminpmsmaster/dashboard", { timeout: 15_000 });

    await page.getByRole("link", { name: "Billing Policy" }).click();
    await expect(page.getByText("Paywall central")).toBeVisible();

    await page.getByRole("link", { name: "Audit Log" }).click();
    await expect(page.getByText("Trazabilidad")).toBeVisible();
  });
});

