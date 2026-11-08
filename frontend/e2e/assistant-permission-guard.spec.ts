import { expect, test, type Page } from "@playwright/test";

const managerCredentials = {
  email: process.env.E2E_MANAGER_EMAIL || "manager@e2e.com",
  password: process.env.E2E_MANAGER_PASSWORD || "E2eManager1234!"
};

async function loginAsManager(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(managerCredentials.email);
  await page.locator('input[type="password"]').fill(managerCredentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

test("manager without financial-report access sees the required permission before Gemma requests", async ({ page }) => {
  const gemmaRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/gemma/chat/")) {
      gemmaRequests.push(`${request.method()} ${url.pathname}`);
    }
  });

  await loginAsManager(page);
  await page.goto("/settings/assistant");

  const guard = page.getByTestId("assistant-permission-guard");
  await expect(guard).toBeVisible();
  await expect(guard.getByRole("alert")).toContainText("reports:financial:view");
  await expect(guard.getByRole("alert")).toContainText("settings:assistant:view");
  await expect(page.getByRole("textbox", { name: "Mensaje" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Verificar el estado del runtime" })).toHaveCount(0);
  expect(gemmaRequests).toEqual([]);
});

test("a Gemma 403 hides assistant controls and explains the required permissions", async ({ page }) => {
  const deniedGemmaRequests: string[] = [];

  await page.route("**/api/permissions/effective", async (route) => {
    const response = await route.fetch();
    if (!response.ok()) {
      await route.fulfill({ response });
      return;
    }
    const payload = await response.json() as { permissions?: string[] };
    const permissions = new Set([...(payload.permissions ?? []), "reports:financial:view"]);
    await route.fulfill({ response, json: { ...payload, permissions: Array.from(permissions) } });
  });

  await page.route("**/api/gemma/chat/**", async (route) => {
    deniedGemmaRequests.push(new URL(route.request().url()).pathname);
    await route.fulfill({
      status: 403,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Forbidden" })
    });
  });

  await loginAsManager(page);
  await page.goto("/settings/assistant");

  const guard = page.getByTestId("assistant-permission-guard");
  await expect(guard.getByRole("alert")).toContainText("reports:financial:view");
  await expect(guard.getByRole("alert")).toContainText("settings:assistant:view");
  await expect(guard.getByRole("alert")).toContainText("El servidor rechazó el acceso");
  await expect.poll(() => deniedGemmaRequests.length).toBeGreaterThan(0);
  await expect(page.getByRole("textbox", { name: "Mensaje" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Verificar el estado del runtime" })).toHaveCount(0);
});
