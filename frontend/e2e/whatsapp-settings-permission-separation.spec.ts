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

test("WhatsApp settings loads channel status without polling inbox conversations", async ({ page }) => {
  let conversationRequests = 0;
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/whatsapp/conversations") {
      conversationRequests += 1;
    }
  });
  await page.route("**/api/whatsapp/channel", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      json: { status: "ready", channel: null },
    });
  });

  await login(page);
  const channelResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/whatsapp/channel"
  );
  await page.goto("/settings/whatsapp");
  await expect(page.getByRole("heading", { name: "WhatsApp Business", exact: true })).toBeVisible();
  await channelResponse;
  await page.waitForTimeout(250);
  expect(conversationRequests).toBe(0);
});
