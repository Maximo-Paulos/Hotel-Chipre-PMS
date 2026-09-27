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

test("WhatsApp settings preserves tenant context and avoids inbox conversation polling", async ({ page }) => {
  let conversationRequests = 0;
  let documentLoads = 0;
  page.on("load", () => {
    documentLoads += 1;
  });
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/whatsapp/conversations")) {
      conversationRequests += 1;
    }
  });
  await page.route("**/api/integrations", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      json: {
        catalog: [
          {
            id: 1,
            provider: "whatsapp",
            display_name: "WhatsApp Business",
            auth_type: "bearer_token",
            scopes: null,
            doc_url: null,
          },
        ],
        connections: [],
      },
    });
  });
  await page.route("**/api/whatsapp/channel", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      json: { status: "ready", channel: null },
    });
  });

  await login(page);
  await page.goto("/settings/connections");
  await expect(page.getByRole("heading", { name: "Conexiones", exact: true })).toBeVisible();
  const whatsappCard = page.getByTestId("integration-card-whatsapp");
  await expect(whatsappCard).toBeVisible();
  await expect(whatsappCard.getByRole("button")).toHaveCount(0);
  const connectionPageLoadCount = documentLoads;
  const channelResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/whatsapp/channel"
  );
  await page.getByRole("link", { name: "Abrir configuración de WhatsApp" }).click();
  await expect(page).toHaveURL(/\/settings\/whatsapp$/);
  await expect(page.getByRole("heading", { name: "WhatsApp Business", exact: true })).toBeVisible();
  await channelResponse;
  await page.waitForTimeout(16_000);
  expect(conversationRequests).toBe(0);
  expect(documentLoads).toBe(connectionPageLoadCount);
});
