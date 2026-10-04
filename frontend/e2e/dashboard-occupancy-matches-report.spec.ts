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

test("dashboard and reports show the same server occupancy value for the selected day", async ({ page }) => {
  const requestedDates: Array<{ start: string | null; end: string | null }> = [];
  await page.route("**/api/reports/occupancy**", async (route) => {
    const url = new URL(route.request().url());
    const startDate = url.searchParams.get("start_date");
    const endDate = url.searchParams.get("end_date");
    requestedDates.push({ start: startDate, end: endDate });
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        start_date: startDate,
        end_date: endDate,
        total_rooms: 13,
        average_occupancy: 7.7,
        daily: [{ date: startDate, occupied: 1, available: 12, rate: 7.7 }]
      })
    });
  });

  await login(page);
  const dashboardCard = page.getByTestId("dashboard-occupancy-card");
  await expect(dashboardCard).toContainText("7.7%");
  const dashboardDate = requestedDates.at(-1);
  expect(dashboardDate?.start).toBeTruthy();
  expect(dashboardDate?.end).toBe(dashboardDate?.start);

  await page.goto("/reportes");
  await expect(page.getByText("7.7%", { exact: true })).toBeVisible();
  const reportsDate = requestedDates.at(-1);
  expect(reportsDate).toEqual(dashboardDate);
});
