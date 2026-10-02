import { expect, test, type Page, type Route } from "@playwright/test";

const ownerEmail = process.env.E2E_OWNER_EMAIL || "owner@e2e.com";
const ownerPassword = process.env.E2E_OWNER_PASSWORD || "E2ePass1234!";

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(ownerEmail);
  await page.locator('input[type="password"]').fill(ownerPassword);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

test("dashboard separates loading, error, and empty states for reservations and activity", async ({ page }) => {
  let releaseRequests: () => void = () => undefined;
  const stalledRequests = new Promise<void>((resolve) => {
    releaseRequests = resolve;
  });
  let allowRecovery = false;
  const stalledKeys = new Set<string>();

  await page.route("http://127.0.0.1:8040/api/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const key = url.searchParams.get("upcoming_only") === "true"
      ? "upcoming"
      : url.searchParams.has("from_date")
        ? "activity"
        : null;
    if (!key) return route.continue();
    stalledKeys.add(key);

    if (!allowRecovery) {
      await stalledRequests;
      return route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Temporary local test outage" })
      });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  await login(page);
  await expect(page.getByTestId("dashboard-upcoming-loading")).toBeVisible();
  await expect(page.getByTestId("dashboard-activity-loading")).toBeVisible();
  expect([...stalledKeys].sort()).toEqual(["activity", "upcoming"]);
  releaseRequests();

  await expect(page.getByTestId("dashboard-upcoming-error")).toBeVisible();
  await expect(page.getByTestId("dashboard-activity-error")).toBeVisible();
  await expect(page.getByTestId("dashboard-upcoming-empty")).toHaveCount(0);
  await expect(page.getByTestId("dashboard-activity-empty")).toHaveCount(0);

  allowRecovery = true;
  await page.getByTestId("dashboard-upcoming-error").getByRole("button", { name: "Reintentar" }).click();
  await page.getByTestId("dashboard-activity-error").getByRole("button", { name: "Reintentar" }).click();
  await expect(page.getByTestId("dashboard-upcoming-empty")).toBeVisible();
  await expect(page.getByTestId("dashboard-activity-empty")).toBeVisible();
});
