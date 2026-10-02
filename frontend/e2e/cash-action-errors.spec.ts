import { expect, test, type Page } from "@playwright/test";

const receptionistCredentials = {
  email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
  password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!"
};

async function loginAsReceptionist(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(receptionistCredentials.email);
  await page.locator('input[type="password"]').fill(receptionistCredentials.password);
  const loginResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/auth/login" && response.request().method() === "POST"
  );
  await page.getByTestId("login-submit").click();
  expect((await loginResponse).ok()).toBeTruthy();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("cash close errors stay in the arqueo form until dismissed", async ({ page }) => {
  await loginAsReceptionist(page);
  const sessionsResponse = page.waitForResponse((response) =>
    response.url().includes("/api/cash-register/sessions") && response.request().method() === "GET"
  );
  await page.goto("/caja");
  await sessionsResponse;

  const openButton = page.getByRole("button", { name: "Abrir caja", exact: true });
  if (await openButton.isVisible().catch(() => false)) {
    const openingForm = page.locator("form").filter({ hasText: "Saldo inicial" }).filter({ hasText: "Abrir caja" });
    await openingForm.getByText("Saldo inicial", { exact: true }).locator("..").locator("input").fill("100");
    await openButton.click();
    await expect(page.getByText("Caja abierta.", { exact: true })).toBeVisible();
  }

  await page.route("**/api/cash-register/sessions/*/close", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Fallo simulado de arqueo" })
    });
  });

  const closeForm = page.locator("form").filter({ hasText: "Saldo esperado:" }).filter({ hasText: "Cerrar caja" });
  await closeForm.getByText("Saldo contado", { exact: true }).locator("..").locator("input").fill("100");
  await closeForm.getByRole("button", { name: "Cerrar caja", exact: true }).click();

  const actionError = closeForm.getByTestId("cash-action-error");
  await expect(actionError).toBeVisible();
  await expect(actionError).toContainText("Fallo simulado de arqueo");
  await expect(actionError).toBeVisible({ timeout: 2_000 });
  await actionError.getByRole("button", { name: "Cerrar error" }).click();
  await expect(actionError).toHaveCount(0);
});
