import { expect, test } from "@playwright/test";

test("a preview host keeps the private login route instead of redirecting to production", async ({ page }) => {
  await page.goto("/login");

  // Wait long enough for the client-side host guard to run before checking
  // that the preview did not redirect to the public production host.
  await page.waitForTimeout(500);

  await expect(page).toHaveURL(/preview\.localhost:5173\/login$/);
  await expect(page.getByTestId("login-submit")).toBeVisible();
});
