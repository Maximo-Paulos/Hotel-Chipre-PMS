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

test("analytics labels the last loaded report when a refresh fails and clears it on retry", async ({ page }) => {
  test.setTimeout(90_000);

  let shouldFailHomeRefresh = false;
  let failedRefreshAttempts = 0;
  const homeReport = {
    hotel_id: 1,
    date_from: "2026-07-01",
    date_to: "2026-07-31",
    generated_at: "2026-07-31T12:00:00Z",
    data_as_of: "2026-07-24T10:00:00Z",
    source_lag_seconds: 604800,
    data_source: "postgresql",
    data: { cards: [{ card_code: "qa_nights", label: "Noches de QA", value_count: 9 }] }
  };

  await page.route("**/api/analytics/home**", async (route) => {
    if (shouldFailHomeRefresh) {
      failedRefreshAttempts += 1;
      await route.fulfill({
        status: 408,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Request timed out" })
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(homeReport)
    });
  });
  await page.route("**/api/analytics/operations**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...homeReport, data: { cards: [] } })
    });
  });

  await login(page);
  await page.goto("/analytics");

  await expect(page.getByText("Noches de QA", { exact: true })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);

  await page.getByRole("link", { name: "Operación", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Operaciones", exact: true })).toBeVisible();

  // The analytics query becomes stale after 30 seconds. Returning to the page
  // remounts the same cached query and exercises the background refresh path.
  await page.waitForTimeout(31_000);
  shouldFailHomeRefresh = true;
  await page.getByRole("link", { name: "Volver", exact: true }).click();

  const staleReportStatus = page.locator('[role="status"]').filter({
    hasText: /Mostrando el último informe cargado el/
  });
  await expect(staleReportStatus).toBeVisible();
  await expect(staleReportStatus).toContainText(/\d/);
  await expect(page.getByText("Noches de QA", { exact: true })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("Request timed out");
  await expect.poll(() => failedRefreshAttempts).toBe(2);

  shouldFailHomeRefresh = false;
  await page.getByRole("alert").getByRole("button", { name: "Reintentar", exact: true }).click();

  await expect(page.locator('[role="status"]').filter({
    hasText: /Mostrando el último informe cargado el/
  })).toHaveCount(0);
  await expect(page.getByText("Noches de QA", { exact: true })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("room state event starts without a client timestamp and shows backend validation detail", async ({ page }) => {
  await page.route("**/api/room-state-events**", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([{
          id: 7,
          room_id: 999_999,
          event_type: "maintenance",
          reason_code: "inspection",
          reason_note: null,
          started_at: "2026-11-01T12:34:56Z",
          ended_at: null,
          created_by_user_id: 98273,
          closed_by_user_id: null
        }])
      });
      return;
    }

    const payload = route.request().postDataJSON();
    expect(payload.started_at).toBeNull();
    await route.fulfill({
      status: 400,
      contentType: "application/json",
      body: JSON.stringify({ detail: "started_at no puede ser futuro" })
    });
  });

  await login(page);
  await page.goto("/operacion/room-state-events");

  const eventHeading = page.getByRole("heading", { name: "Mantenimiento", exact: true });
  const existingEvent = eventHeading.locator("xpath=../../..");
  await expect(eventHeading).toBeVisible();
  await expect(existingEvent).toContainText("Inspección");
  await expect(existingEvent).toContainText("Usuario registrado");
  await expect(existingEvent).not.toContainText("98273");
  await expect(existingEvent).not.toContainText("2026-11-01T12:34:56Z");
  await expect(existingEvent).not.toContainText("maintenance");
  await expect(existingEvent).not.toContainText("inspection");

  const startInput = page.getByLabel("Inicio");
  await expect(startInput).toHaveValue("");
  const room = page.getByLabel("Habitación");
  await expect(room.locator("option").nth(1)).toBeAttached();
  await room.selectOption({ index: 1 });
  await page.getByRole("button", { name: "Crear evento", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("started_at no puede ser futuro");
});
