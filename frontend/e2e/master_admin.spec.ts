import { createHmac } from "node:crypto";

import { test, expect, type Page } from "@playwright/test";

const email = process.env.E2E_MASTER_EMAIL || "master-admin@e2e.com";
const password = process.env.E2E_MASTER_PASSWORD || "E2eMasterPass1234!";
const pin = process.env.E2E_MASTER_PIN || "123456";
// Seeded by scripts/seed_e2e_backend.py from playwright.config.ts: the panel
// refuses to operate without TOTP (TECH-0023).
const totpSecret = process.env.E2E_MASTER_ADMIN_TOTP_SECRET || "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP";

// RFC 6238 with pyotp's defaults (SHA-1, 30 s steps, 6 digits).
function totpAt(step: number): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const bits = [...totpSecret.replace(/=+$/, "")].map((char) => alphabet.indexOf(char).toString(2).padStart(5, "0")).join("");
  const key = Buffer.from(bits.match(/.{8}/g)!.map((byte) => parseInt(byte, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(step));
  const digest = createHmac("sha1", key).update(counter).digest();
  const offset = digest[digest.length - 1] & 0x0f;
  return String((digest.readUInt32BE(offset) & 0x7fffffff) % 1_000_000).padStart(6, "0");
}

async function login(page: Page) {
  await page.goto("/adminpmsmaster/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Contraseña").fill(password);
  await page.getByLabel("PIN del panel").fill(pin);
  await page.getByRole("button", { name: "Entrar al panel" }).click();

  const codeInput = page.getByLabel("Código MFA");
  const verify = page.getByRole("button", { name: "Verificar MFA" });
  const step = Math.floor(Date.now() / 30_000);
  await codeInput.fill(totpAt(step));
  await verify.click();

  // Each step is single-use (replay guard). When an earlier login already
  // spent this one, the server still accepts the next step.
  const rejected = page.getByText("Codigo MFA invalido o ya utilizado");
  await expect(page.getByText("Operación de plataforma").or(rejected)).toBeVisible({ timeout: 15_000 });
  if (await rejected.isVisible()) {
    await codeInput.fill(totpAt(step + 1));
    await verify.click();
  }
  await page.waitForURL("**/adminpmsmaster/dashboard", { timeout: 15_000 });
}

async function primaryNavigation(page: Page) {
  const mobileNavigation = page.getByRole("navigation", { name: "Navegación master móvil" });

  if (await mobileNavigation.isVisible()) {
    return mobileNavigation;
  }

  return page.locator("aside nav");
}

test.describe.serial("Master admin smoke", () => {
  test("login and open dashboard", async ({ page }) => {
    await login(page);
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
    await login(page);

    const navigation = await primaryNavigation(page);
    await navigation.getByRole("link", { name: "Billing Policy" }).click();
    await expect(page.getByText("Paywall central")).toBeVisible();

    await navigation.getByRole("link", { name: "Audit Log" }).click();
    await expect(page.getByText("Trazabilidad")).toBeVisible();
  });
});
