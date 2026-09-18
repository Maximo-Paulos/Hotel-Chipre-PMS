import { expect, test } from "@playwright/test";

// Owner request: show/hide password toggle on the login page, and the
// Google sign-in button follows the explicitly configured E2E client id.
test("password visibility toggle switches the input type", async ({ page }) => {
  await page.goto("/login");
  const passwordInput = page.locator('input[type="password"]');
  await expect(passwordInput).toBeVisible();
  await passwordInput.fill("some-secret-value");

  const toggle = page.getByTestId("toggle-password-visibility");
  await toggle.click();
  await expect(page.locator('input[type="text"]')).toHaveValue("some-secret-value");
  await expect(page.locator('input[type="password"]')).toHaveCount(0);

  await toggle.click();
  await expect(page.locator('input[type="password"]')).toHaveValue("some-secret-value");
});

test("MFA login explains where to get the code and that no email is sent", async ({ page }) => {
  await page.route("**/api/auth/login", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ requires_mfa: true, mfa_token: "synthetic-mfa", expires_in: 300 })
  }));

  await page.goto("/login");
  await page.locator('input[type="email"]').fill("mfa-user@example.com");
  await page.locator('input[type="password"]').fill("test-password");
  await page.getByTestId("login-submit").click();

  await expect(page.getByText(/Esta cuenta tiene activada la verificación en dos pasos/)).toBeVisible();
  await expect(page.getByText(/app autenticadora que vinculaste/)).toBeVisible();
  await expect(page.getByText(/No te llegará por email/)).toBeVisible();
  await expect(page.getByLabel("Código de la app autenticadora o de recuperación")).toBeVisible();
});

test("Google sign-in button follows the configured E2E client id", async ({ page }) => {
  await page.route("**/api/auth/providers", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      google: {
        enabled: Boolean(process.env.E2E_GOOGLE_CLIENT_ID),
        client_id: process.env.E2E_GOOGLE_CLIENT_ID || null,
        self_signup_enabled: Boolean(process.env.E2E_GOOGLE_CLIENT_ID),
        allowed_domains: []
      }
    })
  }));
  if (process.env.E2E_GOOGLE_CLIENT_ID) {
    await page.route("https://accounts.google.com/gsi/client", (route) => route.fulfill({
      status: 200,
      contentType: "application/javascript",
      body: "window.google={accounts:{id:{initialize:function(){},renderButton:function(parent){var button=document.createElement('button');button.textContent='Continue with Google';parent.appendChild(button);}}}};"
    }));
  }
  await page.goto("/login");
  const button = page.getByTestId("google-signin-button");
  if (process.env.E2E_GOOGLE_CLIENT_ID) await expect(button).toBeVisible();
  else await expect(button).toHaveCount(0);
});
