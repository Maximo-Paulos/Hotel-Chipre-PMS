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

test("reservation count cards separate loading and error from a real zero", async ({ page }) => {
  await login(page);

  let releaseReservations: () => void = () => undefined;
  const stalledReservations = new Promise<void>((resolve) => {
    releaseReservations = resolve;
  });
  let intercepted = false;

  await page.route("**/api/reservations/**", async (route) => {
    const url = new URL(route.request().url());
    if (
      route.request().method() !== "GET" ||
      !["/api/reservations", "/api/reservations/"].includes(url.pathname)
    ) {
      return route.continue();
    }
    intercepted = true;
    await stalledReservations;
    return route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Temporary local test outage" })
    });
  });

  await page.goto("/reservas");
  const stats = [
    "reservation-stat-active",
    "reservation-stat-checkins",
    "reservation-stat-checkouts",
    "reservation-stat-cancelled"
  ];
  for (const testId of stats) {
    const card = page.getByTestId(testId);
    await expect(card.locator("p").nth(1)).toHaveText("…");
    await expect(card.getByRole("status")).toHaveText("Cargando reservas...");
    await expect(card.locator("p").nth(1)).not.toHaveText("0");
  }
  expect(intercepted).toBe(true);

  releaseReservations();
  for (const testId of stats) {
    const card = page.getByTestId(testId);
    await expect(card.locator("p").nth(1)).toHaveText("—");
    await expect(card.getByRole("alert")).toHaveText("No se pudieron cargar las reservas.");
  }
});
