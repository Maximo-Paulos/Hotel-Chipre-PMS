import { expect, test } from "@playwright/test";

const credentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

test("owner creates an explicit zero-tax policy before hotel quotes can operate", async ({ page }) => {
  test.skip(
    process.env.E2E_TAX_POLICY_SETUP !== "true",
    "Requires an isolated seed that deliberately omits the synthetic hotel's tax policy"
  );

  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });

  await page.goto("/settings/hotel");
  const policySection = page.getByRole("region", { name: "Política impositiva del hotel" });
  await expect(policySection.getByText("Todavía no hay una política activa.")).toBeVisible();

  await policySection.getByLabel("Código").fill("E2E-CERO");
  await policySection.getByLabel("Nombre").fill("Exención explícita de impuestos");
  await expect(policySection.getByLabel(/Aplicar IVA por defecto/)).not.toBeChecked();
  await expect(policySection.getByLabel("Tasa de IVA (%)")).toHaveValue("0");

  const createResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/commercial/tax-policies"
      && response.request().method() === "POST";
  });
  await policySection.getByRole("button", { name: "Crear política activa" }).click();
  const response = await createResponse;
  expect(response.status()).toBe(201);
  const policy = await response.json() as {
    apply_vat_by_default: boolean;
    vat_rate: number;
    is_active: boolean;
  };
  expect(policy.apply_vat_by_default).toBe(false);
  expect(policy.vat_rate).toBe(0);
  expect(policy.is_active).toBe(true);

  await expect(policySection.getByText("La política impositiva quedó guardada.")).toBeVisible();
  await expect(policySection.getByLabel("Nombre")).toHaveValue("Exención explícita de impuestos");

  await page.reload();
  const savedPolicySection = page.getByRole("region", { name: "Política impositiva del hotel" });
  await expect(savedPolicySection.getByLabel("Nombre")).toHaveValue("Exención explícita de impuestos");
  await expect(savedPolicySection.getByText("Todavía no hay una política activa.")).toHaveCount(0);
});
