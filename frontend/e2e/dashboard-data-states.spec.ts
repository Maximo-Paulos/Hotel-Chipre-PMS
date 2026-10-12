import { expect, test, type Page, type Route } from "@playwright/test";

const ownerEmail = process.env.E2E_OWNER_EMAIL || "owner@e2e.com";
const ownerPassword = process.env.E2E_OWNER_PASSWORD || "E2ePass1234!";
const backendURL = (process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040").replace(/\/$/, "");

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
  const recoveredKeys = new Set<string>();

  await page.route(`${backendURL}/api/**`, async (route: Route) => {
    const url = new URL(route.request().url());
    const key = url.searchParams.get("upcoming_only") === "true"
      ? "upcoming"
      : url.searchParams.has("from_date")
        ? "activity"
        : url.pathname.endsWith("/reservations/actions/pending")
          ? "pending"
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
    recoveredKeys.add(key);
    return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  await login(page);
  await expect(page.getByTestId("dashboard-upcoming-loading")).toBeVisible();
  await expect(page.getByTestId("dashboard-activity-loading")).toBeVisible();
  await expect(page.getByTestId("dashboard-pending-actions-loading")).toBeVisible();
  const pendingActionsCard = page.getByTestId("dashboard-pending-actions-card");
  await expect(pendingActionsCard.locator(".numeric")).toHaveText("…");
  await expect(pendingActionsCard).toContainText("Consultando acciones pendientes...");
  await expect(pendingActionsCard).not.toContainText("Sin críticas");
  expect([...stalledKeys].sort()).toEqual(["activity", "pending", "upcoming"]);
  releaseRequests();

  await expect(page.getByTestId("dashboard-upcoming-error")).toBeVisible();
  await expect(page.getByTestId("dashboard-activity-error")).toBeVisible();
  await expect(page.getByTestId("dashboard-pending-actions-error")).toBeVisible();
  await expect(page.getByTestId("dashboard-upcoming-empty")).toHaveCount(0);
  await expect(page.getByTestId("dashboard-activity-empty")).toHaveCount(0);
  await expect(page.getByTestId("dashboard-pending-actions-empty")).toHaveCount(0);

  allowRecovery = true;
  await page.getByTestId("dashboard-upcoming-error").getByRole("button", { name: "Reintentar" }).click();
  await page.getByTestId("dashboard-activity-error").getByRole("button", { name: "Reintentar" }).click();
  const pendingActionsEmpty = page.getByTestId("dashboard-pending-actions-empty");
  if (!(await pendingActionsEmpty.isVisible().catch(() => false))) {
    try {
      await page.getByTestId("dashboard-pending-actions-error").getByRole("button", { name: "Reintentar" }).click({ timeout: 10_000 });
    } catch (error) {
      // A realtime recovery may replace the error card while Playwright is
      // resolving the click. Accept that race only if the successful empty
      // state appears; the recovery request is asserted below either way.
      await expect(pendingActionsEmpty).toBeVisible({ timeout: 5_000 }).catch(() => {
        throw error;
      });
    }
  }
  await expect(page.getByTestId("dashboard-upcoming-empty")).toBeVisible();
  await expect(page.getByTestId("dashboard-activity-empty")).toBeVisible();
  await expect(pendingActionsEmpty).toBeVisible();
  await expect.poll(() => [...recoveredKeys].sort()).toEqual(["activity", "pending", "upcoming"]);
});
