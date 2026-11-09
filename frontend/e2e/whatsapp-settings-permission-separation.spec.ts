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

test("WhatsApp surfaces show coming soon and do not call disabled endpoints", async ({ page }) => {
  const blockedRequests: string[] = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (
      path.startsWith("/api/public/whatsapp") ||
      path.startsWith("/api/whatsapp") ||
      path === "/api/webhooks/meta/whatsapp"
    ) {
      blockedRequests.push(path);
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
  await login(page);
  await page.goto("/settings/connections");
  const whatsappCard = page.getByTestId("integration-card-whatsapp");
  await expect(whatsappCard).toBeVisible();
  await expect(whatsappCard.getByText("Próximamente")).toBeVisible();
  await expect(whatsappCard.getByRole("button")).toHaveCount(0);

  await whatsappCard.getByRole("link", { name: "Ver información" }).click();
  await expect(page).toHaveURL(/\/settings\/whatsapp$/);
  await expect(page.getByRole("heading", { name: "WhatsApp Business", exact: true })).toBeVisible();
  await expect(page.getByText("Próximamente")).toBeVisible();
  await expect(page.getByPlaceholder("WABA ID")).toHaveCount(0);

  await page.goto("/operacion/whatsapp");
  await expect(page.getByRole("heading", { name: "WhatsApp Business", exact: true })).toBeVisible();
  await expect(page.getByText("Próximamente")).toBeVisible();
  expect(blockedRequests).toEqual([]);
});
