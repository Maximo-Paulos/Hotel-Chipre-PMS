import { expect, test } from "@playwright/test";

test.use({ screenshot: "off", video: "off", trace: "off" });

test("F-027: first access is primary and existing-account sign-in is collapsed", async ({ page }) => {
  await page.route("**/api/auth/session/refresh", (route) =>
    route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "No active session" }) })
  );
  await page.route("**/api/auth/providers", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ google: { enabled: false, client_id: null, self_signup_enabled: false, allowed_domains: [] } })
    })
  );
  await page.route("**/api/invitations/preview", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        email: "new-staff@example.test",
        role: "co_owner",
        hotel_name: "Hotel de prueba",
        inviter_email: "owner@example.test"
      })
    })
  );

  await page.goto("/invitations/accept#token=synthetic-invitation-token");

  const newPassword = page.getByLabel("Contraseña nueva");
  await expect(newPassword).toBeVisible();
  await expect(page.getByRole("heading", { name: "Primer acceso", exact: true })).toBeVisible();
  await expect(page.getByText("Rol:").locator("..")).toContainText("Copropietario");

  const existingAccount = page.locator("details").filter({ hasText: "Ya tenés una cuenta" });
  await expect(existingAccount).toBeVisible();
  await expect(existingAccount.getByLabel("Contraseña actual")).toBeHidden();
  await existingAccount.locator("summary").click();
  await expect(existingAccount.getByLabel("Contraseña actual")).toBeVisible();
});
