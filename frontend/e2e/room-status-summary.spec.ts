import { expect, test } from "@playwright/test";

test.use({ locale: "es-AR" });

test("room inventory summary includes every operational room status", async ({ page }) => {
  const email = process.env.E2E_OWNER_EMAIL || "owner@e2e.com";
  const password = process.env.E2E_OWNER_PASSWORD || "E2ePass1234!";

  await page.goto("/login");
  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });

  await page.route("**/api/rooms/", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(["available", "occupied", "cleaning", "maintenance", "blocked"].map((status, index) => ({
      id: index + 1,
      room_number: String(index + 1),
      floor: 1,
      category_id: 1,
      status,
      housekeeping_status: "clean",
      is_active: true,
      allocation_priority_channel_groups: [],
      allocation_priority_company_ids: []
    })))
  }));

  await page.goto("/habitaciones");
  await expect(page.getByText(
    "Inventario en vivo con estados operativos: libre, ocupada, en limpieza, en mantenimiento y bloqueada.",
    { exact: true }
  )).toBeVisible();
  const summary = page.getByTestId("room-status-summary");
  await expect(summary.getByText("Libres", { exact: true }).locator("..")).toContainText("1");
  await expect(summary.getByText("Ocupadas", { exact: true }).locator("..")).toContainText("1");
  await expect(summary.getByText("En limpieza", { exact: true }).locator("..")).toContainText("1");
  await expect(summary.getByText("Mantenimiento", { exact: true }).locator("..")).toContainText("1");
  await expect(summary.getByText("Bloqueadas", { exact: true }).locator("..")).toContainText("1");
});
