import { expect, test, type Page } from "@playwright/test";

// Fase 8: "Estado de integraciones (Mercado Pago, OTAs, WhatsApp, etc. --
// mostrar claramente si estan configuradas o no)" and "Errores comprensibles
// cuando una integracion no esta configurada (nunca un error tecnico crudo)".
// This environment never carries real MercadoPago/PayPal OAuth app
// credentials (no real payments/OTAs per QA rules), so attempting to open
// authorization for those providers here always exercises the "not
// configured" path -- exactly the scenario the goal calls out.
const ownerEmail = process.env.E2E_OWNER_EMAIL || "owner@e2e.com";
const ownerPassword = process.env.E2E_OWNER_PASSWORD || "E2ePass1234!";

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(ownerEmail);
  await page.locator('input[type="password"]').fill(ownerPassword);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

test("owner sees clear not-connected status and a human error, not a raw technical one, for unconfigured providers", async ({
  page
}) => {
  await login(page);
  await page.goto("/settings/connections");
  await expect(page.getByRole("heading", { name: "Conexiones", exact: true })).toBeVisible();

  const mercadopagoCard = page
    .locator("div.rounded-xl.border")
    .filter({ has: page.getByRole("heading", { name: "MercadoPago", exact: true }) });
  await expect(mercadopagoCard).toBeVisible();
  await expect(mercadopagoCard.getByText("No conectado", { exact: true })).toBeVisible();

  await mercadopagoCard.getByRole("button", { name: "Abrir autorizacion", exact: true }).click();
  const mercadopagoNotice = mercadopagoCard.locator("div.mt-3.rounded-lg.border").first();
  await expect(mercadopagoNotice).toContainText("OAuth de Mercado Pago no esta configurado en este entorno");
  // A raw technical error would look like a stack trace / JSON blob / HTTP
  // status code -- none of that belongs in front of hotel staff.
  await expect(mercadopagoNotice).not.toContainText("Traceback");
  await expect(mercadopagoNotice).not.toContainText("{");
  await expect(mercadopagoNotice).not.toContainText("500");

  const gmailCard = page
    .locator("div.rounded-xl.border")
    .filter({ has: page.getByRole("heading", { name: "Gmail", exact: true }) });
  await expect(gmailCard).toBeVisible();
  await expect(gmailCard.getByText("No conectado", { exact: true })).toBeVisible();

  await gmailCard.getByRole("button", { name: "Conectar Gmail", exact: true }).click();
  const gmailNotice = gmailCard.locator("div.mt-3.rounded-lg.border").first();
  await expect(gmailNotice).toContainText("Todavia falta configurar la app OAuth de Google");
  await expect(gmailNotice).not.toContainText("Traceback");
});
