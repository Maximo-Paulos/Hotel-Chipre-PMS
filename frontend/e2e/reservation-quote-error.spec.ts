import { expect, test, type Page } from "@playwright/test";

const ownerEmail = process.env.E2E_OWNER_EMAIL || "owner@e2e.com";
const ownerPassword = process.env.E2E_OWNER_PASSWORD || "E2ePass1234!";

const localIsoDate = (offsetDays: number) => {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
};

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(ownerEmail);
  await page.locator('input[type="password"]').fill(ownerPassword);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

test("reservation quote failure explains why confirmation is blocked", async ({ page }) => {
  await page.route("**/api/rooms/categories**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: 999,
          name: "QA Quote Error",
          code: "QERR",
          base_price_per_night: 100,
          max_occupancy: 2
        }
      ])
    });
  });
  await page.route("**/api/bookings/price-quote**", async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Quote service unavailable" })
    });
  });

  await login(page);
  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();

  const reservationForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  const categorySelect = reservationForm.locator("label").filter({ hasText: "Categoría" }).locator("select");
  await categorySelect.selectOption("999");
  await reservationForm.locator("label").filter({ hasText: "Check-in" }).locator('input[type="date"]').fill(localIsoDate(1));
  await reservationForm.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]').fill(localIsoDate(2));

  const quoteAlert = reservationForm.getByRole("alert");
  await expect(quoteAlert).toContainText("No se pudo calcular la cotización");
  await expect(quoteAlert.getByRole("button", { name: "Reintentar", exact: true })).toBeVisible();
  await expect(reservationForm.getByText("Total no disponible", { exact: true })).toBeVisible();
  await expect(reservationForm.getByRole("button", { name: "Crear", exact: true })).toBeDisabled();
});
