import { expect, test, type Page } from "@playwright/test";

const receptionist = {
  email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
  password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!"
};

test.use({ timezoneId: "America/Argentina/Buenos_Aires" });

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(receptionist.email);
  await page.locator('input[type="password"]').fill(receptionist.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("guest stay history keeps date-only dates on the correct calendar day in Argentina", async ({ page }) => {
  await login(page);
  await page.route("**/api/guests/*/quick-profile", async (route) => {
    const response = await route.fetch();
    const profile = await response.json();
    profile.last_stays = [
      {
        reservation_id: 98011,
        confirmation_code: "QA-DATE-ONLY",
        status: "checked_out",
        check_in_date: "2026-11-09",
        check_out_date: "2026-11-10"
      }
    ];
    await route.fulfill({ response, json: profile });
  });

  await page.goto("/huespedes");
  await expect(page.getByRole("heading", { name: "Ficha de huéspedes", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Huesped E2E", exact: true })).toBeVisible();

  const staysSection = page.getByRole("heading", { name: "Últimas estadías", exact: true }).locator("xpath=ancestor::section[1]");
  await expect(staysSection).toContainText("QA-DATE-ONLY · Check-out");
  await expect(staysSection).toContainText("09/11/2026");
  await expect(staysSection).toContainText("10/11/2026");
  await expect(staysSection).not.toContainText("08/11/2026");
});
