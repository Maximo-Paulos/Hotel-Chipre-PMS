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

test("trialing subscription with can_write enabled keeps reservation and room actions available", async ({ page }) => {
  await page.route("**/api/subscription/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        hotel_id: 1,
        status: "trialing",
        plan: "pro",
        room_limit: 40,
        staff_limit: 8,
        rooms_in_use: 30,
        can_write: true,
        trial_end_at: "2026-10-12T23:59:59-03:00"
      })
    });
  });

  await login(page);

  await page.goto("/reservas");
  await expect(page.getByRole("button", { name: "Crear reserva", exact: true })).toBeEnabled();

  await page.goto("/habitaciones");
  await expect(page.getByRole("combobox", { name: "Estado de habitación 101" })).toBeEnabled();
});
