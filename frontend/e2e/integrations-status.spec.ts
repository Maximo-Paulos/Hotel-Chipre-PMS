import { expect, test, type Page } from "@playwright/test";

// Fase 8: "Estado de integraciones (Mercado Pago, OTAs, WhatsApp, etc. --
// mostrar claramente si estan configuradas o no)" and "Errores comprensibles
// cuando una integracion no esta configurada (nunca un error tecnico crudo)".
//
// The E2E backend runs with CONNECTIONS_ENABLED=false on purpose
// (playwright.config.ts) so a developer's real .env credentials can never
// reach a provider from a test. That makes two situations worth covering:
// the page in an environment where connections are switched off (real, no
// stubs), and the per-provider "not configured" path of an environment where
// they are on, modelled at the network boundary with the backend's own
// messages (app/services/integration_service.py).
const ownerEmail = process.env.E2E_OWNER_EMAIL || "owner@e2e.com";
const ownerPassword = process.env.E2E_OWNER_PASSWORD || "E2ePass1234!";

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(ownerEmail);
  await page.locator('input[type="password"]').fill(ownerPassword);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

function expectNoRawTechnicalError(text: string) {
  // A raw technical error would look like a stack trace, a JSON blob, an HTTP
  // status code or an environment variable name -- none of that belongs in
  // front of hotel staff.
  expect(text).not.toContain("Traceback");
  expect(text).not.toContain("{");
  expect(text).not.toMatch(/\b(403|500|503)\b/);
  expect(text).not.toMatch(/\b[A-Z]+_[A-Z_]+\b/);
}

test("with connections switched off in this environment the page says so in plain words", async ({ page }) => {
  await login(page);
  await page.goto("/settings/connections");

  // The title stays: failure used to replace the whole page with one line.
  await expect(page.getByRole("heading", { name: "Conexiones", exact: true })).toBeVisible();
  const notice = page.getByTestId("integrations-disabled");
  // No retry storm on a deterministic 403: the notice lands well inside the
  // default timeout instead of after ~7s of "Cargando".
  await expect(notice).toBeVisible({ timeout: 4_000 });
  await expect(notice).toContainText("deshabilitadas en este entorno");
  // The old message blamed the session, which could never be the cause.
  await expect(page.getByText(/Verifica la sesión/)).toHaveCount(0);
  expectNoRawTechnicalError(await notice.innerText());
});

test("owner sees clear not-connected status and a human error, not a raw technical one, for unconfigured providers", async ({
  page
}) => {
  await page.route("**/api/integrations", async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      json: {
        catalog: [
          { id: 901, provider: "gmail", display_name: "Gmail", auth_type: "oauth_code" },
          { id: 902, provider: "mercadopago", display_name: "MercadoPago", auth_type: "oauth_code" }
        ],
        connections: []
      }
    });
  });
  await page.route("**/api/integrations/902/connect", (route) =>
    route.fulfill({
      status: 400,
      contentType: "application/json",
      json: {
        detail:
          "OAuth de Mercado Pago no esta configurado en este entorno. Usa access_token manual o configura la app del PMS."
      }
    })
  );
  await page.route("**/api/integrations/901/connect", (route) =>
    route.fulfill({
      status: 400,
      contentType: "application/json",
      json: {
        detail:
          "OAuth de Gmail no esta configurado en este entorno. Faltan GOOGLE_OAUTH_CLIENT_ID y/o GOOGLE_OAUTH_CLIENT_SECRET en la app del PMS."
      }
    })
  );

  await login(page);
  await page.goto("/settings/connections");
  await expect(page.getByRole("heading", { name: "Conexiones", exact: true })).toBeVisible();

  const mercadopagoCard = page
    .locator("div.rounded-xl.border")
    .filter({ has: page.getByRole("heading", { name: "MercadoPago", exact: true }) });
  await expect(mercadopagoCard).toBeVisible();
  await expect(mercadopagoCard.getByText("No conectado", { exact: true })).toBeVisible();

  await mercadopagoCard.getByRole("button", { name: "Abrir autorización", exact: true }).click();
  const mercadopagoNotice = mercadopagoCard.locator("div.mt-3.rounded-lg.border").first();
  await expect(mercadopagoNotice).toContainText("OAuth de Mercado Pago no esta configurado en este entorno");
  const mercadopagoText = await mercadopagoNotice.innerText();
  expect(mercadopagoText).not.toContain("Traceback");
  expect(mercadopagoText).not.toContain("{");
  expect(mercadopagoText).not.toMatch(/\b500\b/);

  const gmailCard = page
    .locator("div.rounded-xl.border")
    .filter({ has: page.getByRole("heading", { name: "Gmail", exact: true }) });
  await expect(gmailCard).toBeVisible();
  await expect(gmailCard.getByText("No conectado", { exact: true })).toBeVisible();

  await gmailCard.getByRole("button", { name: "Conectar Gmail", exact: true }).click();
  const gmailNotice = gmailCard.locator("div.mt-3.rounded-lg.border").first();
  // The backend's Gmail message names environment variables; the page must
  // translate it for hotel staff instead of passing it through.
  await expect(gmailNotice).toContainText("Todavía falta configurar la app de Google");
  expectNoRawTechnicalError(await gmailNotice.innerText());
});
