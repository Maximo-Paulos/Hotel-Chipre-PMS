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
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

function addDays(isoDate: string, days: number) {
  const [year, month, day] = isoDate.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day + days));
  return date.toISOString().slice(0, 10);
}

test("owner records effective dated company extra person rates without changing earlier entries", async ({ page }) => {
  const companyName = `QA Tarifa ${Date.now()}`;
  await login(page);
  await page.goto("/settings/companies");

  await page.getByRole("button", { name: "Nueva empresa", exact: true }).click();
  await page.getByLabel("Nombre legal").fill(`${companyName} SRL`);
  await page.getByLabel("Nombre comercial").fill(companyName);
  await page.getByRole("button", { name: "Guardar empresa", exact: true }).click();
  await expect(page.getByRole("heading", { name: companyName, exact: true })).toBeVisible();

  const effectiveDate = page.getByTestId("company-nightly-rate-effective-date");
  await expect(effectiveDate).toHaveValue(/^\d{4}-\d{2}-\d{2}$/);
  const today = await effectiveDate.inputValue();
  await page.getByTestId("company-nightly-rate-amount").fill("0");
  await page.getByTestId("company-nightly-rate-submit").click();
  await expect(page.getByText("Nueva tarifa registrada.", { exact: true })).toBeVisible();
  const history = page.getByTestId("company-nightly-rate-history");
  await expect(history.getByTestId("company-nightly-rate-row")).toHaveCount(1);
  await expect(history).toContainText("Sin cargo adicional");

  const futureDate = addDays(today, 7);
  await effectiveDate.fill(futureDate);
  await page.getByTestId("company-nightly-rate-amount").fill("1250.50");
  const [rateResponse] = await Promise.all([
    page.waitForResponse((response) =>
      response.url().includes("/nightly-rates") && response.request().method() === "POST"
    ),
    page.getByTestId("company-nightly-rate-submit").click()
  ]);
  expect(rateResponse.status()).toBe(201);
  expect(rateResponse.request().postDataJSON()).toEqual({ effective_from: futureDate, amount: 1250.5 });
  await expect(page.getByText("Nueva tarifa registrada.", { exact: true })).toBeVisible();
  await expect(history.getByTestId("company-nightly-rate-row")).toHaveCount(2);
  await expect(history).toContainText("1.250,50");
  await expect(page.getByText("no modifica cargos ya creados", { exact: false })).toBeVisible();
});
