import { expect, test } from "@playwright/test";

// Owner request: show/hide password toggle on the login page, and the
// Google sign-in button must stay hidden until VITE_GOOGLE_CLIENT_ID is
// configured for the build (not set in this local E2E build).
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

test("Google sign-in button does not render without VITE_GOOGLE_CLIENT_ID", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByTestId("google-signin-button")).toHaveCount(0);
});
