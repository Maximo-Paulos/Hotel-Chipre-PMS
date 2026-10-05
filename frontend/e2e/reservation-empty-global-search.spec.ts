import { expect, test, type Page } from "@playwright/test";

const credentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

test("empty global reservation search does not fetch the full reservations list", async ({ page }) => {
  const listRequests: string[] = [];
  page.on("request", (request) => {
    if (request.method() !== "GET") return;
    try {
      const url = new URL(request.url());
      if (url.pathname === "/api/reservations/") listRequests.push(url.href);
    } catch {
      // Ignore non-URL requests.
    }
  });

  await login(page);
  await expect(page.getByRole("heading", { name: "Visión general" })).toBeVisible();

  const reservationsResponse = page.waitForResponse((response) => {
    if (response.request().method() !== "GET") return false;
    const url = new URL(response.url());
    return url.pathname === "/api/reservations/" && url.searchParams.get("order") === "check_in";
  });
  await page.goto("/reservas");
  await reservationsResponse;
  await expect(page.getByRole("heading", { name: "Reservas", exact: true })).toBeVisible();

  expect(listRequests.length).toBeGreaterThan(0);
  expect(listRequests.some((value) => {
    const params = new URL(value).searchParams;
    return params.get("limit") === "200" &&
      params.get("order") === "check_in" &&
      !params.has("from_date") &&
      !params.has("to_date");
  })).toBe(true);
  expect(listRequests.some((value) => new URL(value).search === "")).toBe(false);
});
