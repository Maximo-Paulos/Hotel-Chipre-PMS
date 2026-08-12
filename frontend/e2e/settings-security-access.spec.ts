import { expect, test, type Page } from "@playwright/test";

const owner = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(owner.email);
  await page.locator('input[type="password"]').fill(owner.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("owner can invite reception and revoke every current session from the security surface", async ({ page }) => {
  await login(page);

  await page.goto("/settings/users");
  await expect(page.getByRole("heading", { name: "Usuarios y roles", exact: true })).toBeVisible();
  const invitationRole = page.getByLabel("Rol de invitación");
  await expect(invitationRole.locator('option[value="receptionist"]')).toHaveText("Recepción");

  await page.goto("/settings/security");
  await expect(page.getByRole("heading", { name: "Seguridad", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Resumen de seguridad" })).toBeVisible();
  await expect(page.getByText("Miembros activos", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Eventos recientes", exact: true })).toBeVisible();
  await expect(page.getByText(/Pendiente: controles de tiempo de sesión/)).toHaveCount(0);

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("security-revoke-all").click();
  await page.waitForURL("**/login?sessions=revoked", { timeout: 20_000 });
  await expect(page.getByTestId("login-submit")).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("hotel-pms-session"))).toBeNull();
});
