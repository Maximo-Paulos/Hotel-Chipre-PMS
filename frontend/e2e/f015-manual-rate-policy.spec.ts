import { expect, test, type Page, type TestInfo } from "@playwright/test";

import { completeStepUpPrompt, loginAsStepUpOwner } from "./support/step-up-owner";

const manager = {
  email: process.env.E2E_MANAGER_EMAIL || "manager@e2e.com",
  password: process.env.E2E_MANAGER_PASSWORD || "E2eManager1234!"
};
const receptionist = {
  email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
  password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!"
};

const localIsoDate = (offsetDays: number) => {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
};

async function login(page: Page, credentials: { email: string; password: string }) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

async function clearBrowserSession(page: Page) {
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
  await page.context().clearCookies();
}

test("F-015 owner configures a bounded rate, manager records it with reason, reception cannot set it", async (
  { page },
  testInfo: TestInfo
) => {
  test.setTimeout(180_000);
  let lastTotpStep = -1;
  let policyNeedsClear = false;

  try {
    const ownerSession = await loginAsStepUpOwner(page, "rate-policy", testInfo.project.name);
    lastTotpStep = ownerSession.lastTotpStep;
    await page.goto("/settings/hotel");

    const minimumLimit = page.getByLabel("Ajuste mínimo (%)", { exact: true });
    const maximumLimit = page.getByLabel("Ajuste máximo (%)", { exact: true });
    await expect(minimumLimit).toBeVisible();

    const updatePolicy = async (minimum: string, maximum: string) => {
      await minimumLimit.fill(minimum);
      await maximumLimit.fill(maximum);
      const responsePromise = page.waitForResponse((response) => {
        const url = new URL(response.url());
        return url.pathname === "/api/config/"
          && response.request().method() === "PATCH"
          && response.status() === 200;
      });
      await page.getByRole("button", { name: "Guardar cambios", exact: true }).click();
      await expect(page.getByRole("dialog", { name: "Confirmá que sos vos" })).toBeVisible();
      lastTotpStep = await completeStepUpPrompt(page, lastTotpStep, ownerSession.auth.user.email);
      const response = await responsePromise;
      expect(response.status()).toBe(200);
      await expect(page.getByText("Cambios guardados.", { exact: true })).toBeVisible();
    };

    if ((await minimumLimit.inputValue()) !== "" || (await maximumLimit.inputValue()) !== "") {
      policyNeedsClear = true;
      await updatePolicy("", "");
      policyNeedsClear = false;
    }

    policyNeedsClear = true;
    await updatePolicy("-25", "10");

    await clearBrowserSession(page);
    await login(page, manager);
    await page.goto("/reservas");
    await page.getByRole("button", { name: "Crear reserva", exact: true }).click();

    const form = page.locator("form").filter({ hasText: "Datos de la reserva" });
    await expect(form).toBeVisible();
    await form.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
    const suffix = `${Date.now()}`;
    const guestLastName = `QA-F015 ${suffix}`;
    await form.getByPlaceholder("Nombre").fill("Huésped");
    await form.getByPlaceholder("Apellido").fill(guestLastName);
    await form.getByPlaceholder("Email").fill(`qa-f015-${suffix}@example.test`);
    await form.getByPlaceholder("Teléfono").fill("1112345678");
    await form.getByLabel("Tipo de documento").selectOption("DNI");
    await form.getByPlaceholder("Documento").fill(`QAF015-${suffix}`);
    await form.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
    await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

    const categorySelect = form.locator("label").filter({ hasText: "Categoría" }).locator("select");
    const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
    await expect(categoryOption).toHaveCount(1);
    await categorySelect.selectOption((await categoryOption.getAttribute("value"))!);
    await form.getByLabel("Check-in", { exact: true }).fill(localIsoDate(480));
    await form.getByLabel("Check-out", { exact: true }).fill(localIsoDate(482));

    const amount = form.getByLabel("Monto total manual", { exact: true });
    const reason = form.getByPlaceholder("Explicá brevemente el acuerdo comercial", { exact: true });
    await expect(amount).toBeEnabled({ timeout: 15_000 });
    await expect(form.getByText(/Rango permitido:/)).toBeVisible();
    await reason.fill("Descuento autorizado para estadía de dos noches");
    await amount.fill("149.99");
    await form.getByRole("button", { name: "Crear", exact: true }).click();
    await expect(page.getByTestId("reservation-submit-error")).toContainText("debe estar entre");

    await amount.fill("170");
    const createResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname === "/api/reservations/"
        && response.request().method() === "POST"
        && response.status() === 201;
    });
    await form.getByRole("button", { name: "Crear", exact: true }).click();
    const createResponse = await createResponsePromise;
    const savedReservation = await createResponse.json() as {
      total_amount: number;
      currency_code: string;
      manual_rate_reason: string;
    };
    expect(savedReservation.total_amount).toBe(170);
    expect(savedReservation.currency_code).toBe("ARS");
    expect(savedReservation.manual_rate_reason).toBe("Descuento autorizado para estadía de dos noches");
    await expect(form.getByRole("status")).toContainText("Reserva");
    await form.getByRole("button", { name: "Cerrar", exact: true }).click();

    const reservationRow = page
      .locator("table")
      .filter({ hasText: "Código" })
      .locator("tbody tr")
      .filter({ hasText: guestLastName });
    await expect(reservationRow).toHaveCount(1);
    await reservationRow.getByRole("button", { name: "Ficha", exact: true }).click();
    const manualRateAudit = page.locator("li").filter({ hasText: "Tarifa manual registrada:" });
    await expect(manualRateAudit).toHaveCount(1);
    await expect(manualRateAudit).toContainText("Descuento autorizado para estadía de dos noches");
    await page.getByRole("button", { name: "Cerrar", exact: true }).last().click();
    await reservationRow.getByRole("button", { name: "Cancelar", exact: true }).click();
    await expect(page.getByText("Reserva cancelada", { exact: true })).toBeVisible();

    await clearBrowserSession(page);
    await login(page, receptionist);
    await page.goto("/reservas");
    await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
    const receptionistForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
    await expect(receptionistForm).toBeVisible();
    await expect(receptionistForm.getByLabel("Monto total manual", { exact: true })).toHaveCount(0);
  } finally {
    if (policyNeedsClear && !page.isClosed()) {
      await clearBrowserSession(page);
      const cleanupOwner = await loginAsStepUpOwner(page, "rate-policy", testInfo.project.name);
      lastTotpStep = cleanupOwner.lastTotpStep;
      await page.goto("/settings/hotel");
      const minimumLimit = page.getByLabel("Ajuste mínimo (%)", { exact: true });
      const maximumLimit = page.getByLabel("Ajuste máximo (%)", { exact: true });
      await expect(minimumLimit).toBeVisible();
      if ((await minimumLimit.inputValue()) !== "" || (await maximumLimit.inputValue()) !== "") {
        await minimumLimit.fill("");
        await maximumLimit.fill("");
        const clearResponsePromise = page.waitForResponse((response) => {
          const url = new URL(response.url());
          return url.pathname === "/api/config/"
            && response.request().method() === "PATCH"
            && response.status() === 200;
        });
        await page.getByRole("button", { name: "Guardar cambios", exact: true }).click();
        await expect(page.getByRole("dialog", { name: "Confirmá que sos vos" })).toBeVisible();
        await completeStepUpPrompt(page, lastTotpStep, cleanupOwner.auth.user.email);
        const clearResponse = await clearResponsePromise;
        expect(clearResponse.status()).toBe(200);
        await expect(page.getByText("Cambios guardados.", { exact: true })).toBeVisible();
      }
    }
  }
});
