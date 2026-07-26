import { expect, test, type Page } from "@playwright/test";

// Bug: ReportsPage (and a few other "today" defaults) derived "today" from
// new Date().toISOString().slice(0, 10), which is UTC's calendar date, not
// the hotel's local one. Argentina (ART, UTC-3) crosses into UTC's next day
// at 21:00 local, so any operator viewing these pages between ~21:00 and
// 24:00 ART saw tomorrow's date pre-filled instead of today's -- see memory
// checkpoint 20260726-013608 and manager-reports-journey.spec.ts, which
// fails for real (not flaky) in that window every day.
//
// 2026-07-25 23:30 ART == 2026-07-26 02:30 UTC.
const lateNightArgentinaUtc = "2026-07-26T02:30:00Z";
const expectedHotelLocalDate = "2026-07-25";

const owner = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

test.use({ timezoneId: "America/Argentina/Buenos_Aires" });

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(owner.email);
  await page.locator('input[type="password"]').fill(owner.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("reports date defaults to the hotel's local today, not UTC's tomorrow, late at night", async ({ page }) => {
  await login(page);
  await page.clock.install({ time: new Date(lateNightArgentinaUtc) });

  await page.goto("/reportes");
  await expect(page.getByRole("heading", { name: "Reportes", exact: true })).toBeVisible();
  await expect(page.getByLabel("Fecha")).toHaveValue(expectedHotelLocalDate);
});

test("dashboard KPIs default to the hotel's local today, not UTC's tomorrow, late at night", async ({ page }) => {
  await login(page);
  await page.clock.install({ time: new Date(lateNightArgentinaUtc) });

  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Visión general", exact: true })).toBeVisible();
  await expect(page.getByTestId("dashboard-today-date")).toHaveText(expectedHotelLocalDate);
});
