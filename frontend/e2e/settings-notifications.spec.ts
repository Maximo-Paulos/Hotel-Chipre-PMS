import { expect, test, type Page } from "@playwright/test";

const ownerCredentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};
const receptionistCredentials = {
  email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
  password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!"
};

async function login(page: Page, credentials: { email: string; password: string }) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

test.describe("Notification center", () => {
  test("owner sees push card, per-event preferences and the owner-only daily report section", async ({ page }) => {
    await login(page, ownerCredentials);
    await page.goto("/settings/notifications");

    await expect(page.getByRole("heading", { name: "Notificaciones", exact: true })).toBeVisible();

    // Push card: VAPID public key isn't configured in the E2E env, so this is
    // the deterministic branch regardless of browser Push API support.
    await expect(page.getByText("Las notificaciones push no están configuradas para este hotel todavía.")).toBeVisible();

    // Preferences: default row plus at least one known event type.
    await expect(page.getByText("Predeterminado (todas las alertas)", { exact: true })).toBeVisible();
    const reservationRow = page.locator("div").filter({ hasText: "Reserva creada" }).last();
    await expect(reservationRow.getByRole("checkbox").first()).toBeVisible();

    // Owner/co-owner-only section is visible for the owner.
    await expect(page.getByRole("heading", { name: "Reporte diario (solo dueño/co-dueño)", exact: true })).toBeVisible();
    await expect(page.getByText("Enviar reporte diario", { exact: true })).toBeVisible();
  });

  test("toggling a preference persists after reload", async ({ page }) => {
    await login(page, ownerCredentials);
    await page.goto("/settings/notifications");

    const defaultRow = page.locator("div.rounded-lg", { hasText: "Predeterminado (todas las alertas)" }).first();
    const emailToggle = defaultRow.getByLabel("Email", { exact: true });
    const wasChecked = await emailToggle.isChecked();
    await emailToggle.click();
    await expect(emailToggle).toBeChecked({ checked: !wasChecked });

    await page.reload();
    const defaultRowAfterReload = page.locator("div.rounded-lg", { hasText: "Predeterminado (todas las alertas)" }).first();
    await expect(defaultRowAfterReload.getByLabel("Email", { exact: true })).toBeChecked({ checked: !wasChecked });

    // Restore original state so this test is idempotent across reruns.
    await defaultRowAfterReload.getByLabel("Email", { exact: true }).click();
    await expect(defaultRowAfterReload.getByLabel("Email", { exact: true })).toBeChecked({ checked: wasChecked });
  });

  test("receptionist does not see the owner-only daily report section", async ({ page }) => {
    await login(page, receptionistCredentials);
    await page.goto("/settings/notifications");

    await expect(page.getByRole("heading", { name: "Notificaciones", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Reporte diario (solo dueño/co-dueño)" })).toHaveCount(0);
  });

  test("alerts bell opens the notification panel without horizontal overflow, mobile and desktop", async ({ page }) => {
    await login(page, ownerCredentials);

    for (const [width, height] of [
      [375, 812],
      [1280, 800]
    ] as const) {
      await test.step(`viewport ${width}x${height}`, async () => {
        await page.setViewportSize({ width, height });
        const bell = width < 768 ? page.getByTestId("mobile-alerts-button") : page.getByRole("button", { name: /Ver alertas/ });
        await bell.first().click();
        await expect(page.getByRole("dialog", { name: "Alertas" })).toBeVisible();
        // Never both a load error and the empty/list state at once.
        await expect(page.getByText("No se pudieron cargar las alertas.", { exact: true })).toHaveCount(0);

        const layout = await page.evaluate(() => ({
          viewportWidth: window.innerWidth,
          documentScrollWidth: document.documentElement.scrollWidth
        }));
        expect(layout.documentScrollWidth).toBeLessThanOrEqual(layout.viewportWidth);

        await page.getByLabel("Cerrar alertas", { exact: true }).click();
        await expect(page.getByRole("dialog", { name: "Alertas" })).toBeHidden();
      });
    }
  });
});
