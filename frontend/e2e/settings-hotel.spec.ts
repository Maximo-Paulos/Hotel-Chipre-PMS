import { expect, test, type Page, type TestInfo } from "@playwright/test";

import { completeStepUpPrompt, loginAsStepUpOwner } from "./support/step-up-owner";

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

test("owner can save an enabled transfer method without completing the category draft", async ({ page }) => {
  await login(page);
  await page.goto("/settings/hotel");

  const transferMethod = page.locator("label").filter({ hasText: "Transferencia" }).locator('input[type="checkbox"]');
  await expect(transferMethod).toHaveCount(1);
  await transferMethod.check();
  await page.getByLabel("Check-in desde").fill("14:00");
  await page.getByLabel("Check-out hasta").fill("10:00");

  await page.getByRole("button", { name: "Guardar cambios", exact: true }).click();
  await expect(page.getByText("Cambios guardados.", { exact: true })).toBeVisible();

  await page.reload();
  await expect(transferMethod).toBeChecked();
  await expect(page.getByLabel("Check-in desde")).toHaveValue("14:00");
  await expect(page.getByLabel("Check-out hasta")).toHaveValue("10:00");
});

test("owner can configure and persist a percentage rule for one night and one-night deposits for longer stays", async ({ page }) => {
  await login(page);
  await page.goto("/settings/hotel");

  const rules = page.getByTestId("settings-deposit-policy-rules");
  await expect(rules).toBeVisible();
  await rules.getByLabel("Límite de noches de regla 1").fill("1");
  await rules.getByLabel("Tipo de seña de regla 1").selectOption("percentage");
  await rules.getByLabel("Valor de seña de regla 1").fill("30");
  await rules.getByRole("button", { name: "Agregar rango de estadía" }).click();
  await expect(rules.getByText("Desde 2 noches")).toBeVisible();
  await rules.getByLabel("Tipo de seña de regla 2").selectOption("nights");
  await rules.getByLabel("Valor de seña de regla 2").fill("1");

  const confirmation = page.getByLabel("Confirmo que las reglas mostradas fueron definidas por este hotel.");
  if (!(await confirmation.isChecked())) await confirmation.check();
  await page.getByRole("button", { name: "Guardar cambios", exact: true }).click();
  await expect(page.getByText("Cambios guardados.", { exact: true })).toBeVisible();

  await page.reload();
  const savedRules = page.getByTestId("settings-deposit-policy-rules");
  await expect(savedRules.getByLabel("Límite de noches de regla 1")).toHaveValue("1");
  await expect(savedRules.getByLabel("Tipo de seña de regla 1")).toHaveValue("percentage");
  await expect(savedRules.getByLabel("Valor de seña de regla 1")).toHaveValue("30");
  await expect(savedRules.getByText("Desde 2 noches")).toBeVisible();
  await expect(savedRules.getByLabel("Tipo de seña de regla 2")).toHaveValue("nights");
  await expect(savedRules.getByLabel("Valor de seña de regla 2")).toHaveValue("1");
  await expect(confirmation).toBeChecked();
});

test("owner can configure and persist the FX market and side for each conversion direction", async ({ page }, testInfo: TestInfo) => {
  const ownerSession = await loginAsStepUpOwner(page, "rate-policy", testInfo.project.name);
  let lastTotpStep = ownerSession.lastTotpStep;
  let settingsSaved = false;

  try {
    await page.goto("/settings/hotel");

    const fxSettings = page.getByTestId("fx-direction-settings");
    const usdToArsMarket = fxSettings.getByLabel("Mercado al convertir de USD a ARS");
    const arsToUsdMarket = fxSettings.getByLabel("Mercado al convertir de ARS a USD");
    const usdToArs = fxSettings.getByLabel("Tipo al convertir de USD a ARS");
    const arsToUsd = fxSettings.getByLabel("Tipo al convertir de ARS a USD");

    await expect(usdToArsMarket).toHaveValue("oficial");
    await expect(arsToUsdMarket).toHaveValue("oficial");
    await expect(usdToArs).toBeVisible();
    await expect(arsToUsd).toBeVisible();
    await expect(usdToArs).toHaveValue("venta");
    await expect(arsToUsd).toHaveValue("venta");

    await usdToArsMarket.selectOption("blue");
    await arsToUsdMarket.selectOption("oficial");
    await usdToArs.selectOption("compra");
    await arsToUsd.selectOption("venta");
    const updateResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname === "/api/config/" && response.request().method() === "PATCH" && response.status() === 200;
    });
    await page.getByRole("button", { name: "Guardar cambios", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "Confirmá que sos vos" })).toBeVisible();
    lastTotpStep = await completeStepUpPrompt(page, lastTotpStep, ownerSession.auth.user.email);
    const updateResponse = await updateResponsePromise;
    expect(updateResponse.status()).toBe(200);
    settingsSaved = true;
    await expect(page.getByText("Cambios guardados.", { exact: true })).toBeVisible();

    await page.reload();
    const savedFxSettings = page.getByTestId("fx-direction-settings");
    await expect(savedFxSettings.getByLabel("Mercado al convertir de USD a ARS")).toHaveValue("blue");
    await expect(savedFxSettings.getByLabel("Mercado al convertir de ARS a USD")).toHaveValue("oficial");
    await expect(savedFxSettings.getByLabel("Tipo al convertir de USD a ARS")).toHaveValue("compra");
    await expect(savedFxSettings.getByLabel("Tipo al convertir de ARS a USD")).toHaveValue("venta");
  } finally {
    if (settingsSaved) {
      await page.goto("/settings/hotel");
      const fxSettings = page.getByTestId("fx-direction-settings");
      await fxSettings.getByLabel("Mercado al convertir de USD a ARS").selectOption("oficial");
      await fxSettings.getByLabel("Mercado al convertir de ARS a USD").selectOption("oficial");
      await fxSettings.getByLabel("Tipo al convertir de USD a ARS").selectOption("venta");
      await fxSettings.getByLabel("Tipo al convertir de ARS a USD").selectOption("venta");
      const restoreResponsePromise = page.waitForResponse((response) => {
        const url = new URL(response.url());
        return url.pathname === "/api/config/" && response.request().method() === "PATCH" && response.status() === 200;
      });
      await page.getByRole("button", { name: "Guardar cambios", exact: true }).click();
      await expect(page.getByRole("dialog", { name: "Confirmá que sos vos" })).toBeVisible();
      lastTotpStep = await completeStepUpPrompt(page, lastTotpStep, ownerSession.auth.user.email);
      await restoreResponsePromise;
    }
  }
});
