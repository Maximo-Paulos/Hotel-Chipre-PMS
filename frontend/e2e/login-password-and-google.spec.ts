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

test("Google sign-in button follows the configured E2E client id", async ({ page }) => {
  if (process.env.E2E_GOOGLE_CLIENT_ID) {
    await page.route("https://accounts.google.com/gsi/client", (route) => route.fulfill({
      status: 200,
      contentType: "application/javascript",
      body: "window.google={accounts:{id:{initialize:function(){},renderButton:function(parent){parent.appendChild(document.createElement('button'));}}}};"
    }));
  }
  await page.goto("/login");
  const button = page.getByTestId("google-signin-button");
  if (process.env.E2E_GOOGLE_CLIENT_ID) await expect(button).toBeVisible();
  else await expect(button).toHaveCount(0);
});
