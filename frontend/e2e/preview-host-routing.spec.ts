import { expect, test } from "@playwright/test";

test("an unrecognized preview host stays local in dev instead of redirecting to production", async ({ page }) => {
  await page.goto("/login");

  // Wait long enough for the client-side host guard to run before checking
  // that an unrecognized dev host did not redirect to the public production host.
  await page.waitForTimeout(500);

  await expect(page).toHaveURL(/preview\.localhost:5173\/login$/);
  await expect(page.getByTestId("login-submit")).toBeVisible();
});
