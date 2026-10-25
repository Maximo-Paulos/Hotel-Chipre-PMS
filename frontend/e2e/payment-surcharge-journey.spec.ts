import { expect, test, type Page } from "@playwright/test";

const credentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

const localIsoDate = (offsetDays: number) => {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
};

const parseMoney = (value: string) =>
  Number(value.replace(/[^\d,.-]/g, "").replace(/\./g, "").replace(",", "."));

async function login(page: Page) {
  const isLoginOrPreflight = (method: string, urlValue: string) => {
    const url = new URL(urlValue);
    return url.pathname.replace(/\/+$/, "") === "/api/auth/login"
      && (method === "POST" || method === "OPTIONS");
  };
  page.on("request", (request) => {
    if (!isLoginOrPreflight(request.method(), request.url())) return;
    const path = new URL(request.url()).pathname;
    console.info(`[e2e-login] request method=${request.method()} path=${path}`);
  });
  page.on("response", (response) => {
    const request = response.request();
    if (!isLoginOrPreflight(request.method(), response.url())) return;
    const path = new URL(response.url()).pathname;
    console.info(`[e2e-login] response method=${request.method()} path=${path} status=${response.status()}`);
  });
  page.on("requestfailed", (request) => {
    if (!isLoginOrPreflight(request.method(), request.url())) return;
    const path = new URL(request.url()).pathname;
    const errorText = (request.failure()?.errorText || "unknown")
      .replace(/https?:\/\/[^\s]+/g, "[url]")
      .replace(/[\r\n\t]+/g, " ")
      .slice(0, 160);
    console.info(`[e2e-login] failed method=${request.method()} path=${path} error=${errorText}`);
  });

  await page.goto("/login");
  await page.getByLabel("Email").fill(credentials.email);
  await page.locator("#login-password").fill(credentials.password);
  const loginResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname.replace(/\/+$/, "") === "/api/auth/login" && response.request().method() === "POST";
  }, { timeout: 15_000 });
  await page.getByTestId("login-submit").click();
  const loginResponse = await loginResponsePromise;
  expect(loginResponse.status(), "Owner login API response").toBe(200);
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

async function readStat(form: ReturnType<Page["locator"]>, label: string) {
  const value = await form.getByText(label, { exact: true }).locator("xpath=following-sibling::p[1]").innerText();
  return parseMoney(value);
}

test.use({ trace: "off", screenshot: "off", video: "off" });

test("owner records a 3% credit-card surcharge separately from a 100000 ARS reservation", async ({ page }) => {
  const suffix = `${Date.now()}`;
  const guestLastName = `QA Recargo ${suffix}`;

  await login(page);

  // Configure the hotel's real payment rule through Settings, then reload to
  // prove the UI reads the saved value back from the API.
  await page.goto("/settings/hotel");
  const creditCardMethod = page.locator("label").filter({ hasText: "Tarjeta de crédito" }).locator('input[type="checkbox"]');
  if (!(await creditCardMethod.isChecked())) {
    await creditCardMethod.check();
    const hotelConfigResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname === "/api/config/" && response.request().method() === "PATCH";
    });
    await page.getByRole("button", { name: "Guardar cambios", exact: true }).click();
    const hotelConfigResponse = await hotelConfigResponsePromise;
    expect(hotelConfigResponse.status()).toBe(200);
    await expect(page.getByText("Cambios guardados.", { exact: true })).toBeVisible();
    await page.reload();
    await expect(creditCardMethod).toBeChecked();
  }

  const surchargeCard = page.getByRole("heading", { name: "Recargos por medio de pago" }).locator("xpath=../..");
  await expect(surchargeCard.getByRole("button", { name: "Agregar recargo", exact: true })).toBeEnabled();
  await surchargeCard.getByRole("combobox", { name: "Medio", exact: true }).selectOption("credit_card");
  await surchargeCard.getByRole("combobox", { name: "Tipo", exact: true }).selectOption("percentage");
  await surchargeCard.getByRole("spinbutton", { name: "Porcentaje", exact: true }).fill("3");

  const surchargeResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/payment-surcharges" && response.request().method() === "POST";
  });
  await surchargeCard.getByRole("button", { name: "Agregar recargo", exact: true }).click();
  const surchargeResponse = await surchargeResponsePromise;
  expect(surchargeResponse.status()).toBe(201);
  const createdSurcharge = await surchargeResponse.json() as {
    payment_method: string;
    surcharge_type: string;
    amount: string | number;
    is_active: boolean;
  };
  expect(createdSurcharge).toMatchObject({
    payment_method: "credit_card",
    surcharge_type: "percentage",
    is_active: true
  });
  expect(Number(createdSurcharge.amount)).toBe(3);
  await expect(surchargeCard.getByText(/Tarjeta de crédito:\s*3%/)).toBeVisible();

  await page.reload();
  const savedSurchargeCard = page.getByRole("heading", { name: "Recargos por medio de pago" }).locator("xpath=../..");
  await expect(savedSurchargeCard.getByText(/Tarjeta de crédito:\s*3%/)).toBeVisible();

  // Create a synthetic reservation with an explicitly recorded ARS 100000
  // manual total so the payment journey exercises the requested exact amount.
  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  const reservationForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(reservationForm).toBeVisible();
  await reservationForm.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
  await reservationForm.getByPlaceholder("Nombre").fill("Huésped");
  await reservationForm.getByPlaceholder("Apellido").fill(guestLastName);
  await reservationForm.getByPlaceholder("Email").fill(`qa.surcharge.${suffix}@example.test`);
  await reservationForm.getByPlaceholder("Teléfono").fill(`11${Date.now().toString().slice(-8)}55`);
  await reservationForm.getByLabel("Tipo de documento").selectOption("DNI");
  await reservationForm.getByPlaceholder("Documento").fill(`QA-PSC-${suffix}`);
  await reservationForm.getByRole("button", { name: "Crear Huésped y asignar ID" }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = reservationForm.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  await categorySelect.selectOption((await categoryOption.getAttribute("value"))!);
  await reservationForm.getByLabel("Check-in", { exact: true }).fill(localIsoDate(45));
  await reservationForm.getByLabel("Check-out", { exact: true }).fill(localIsoDate(46));
  await reservationForm.getByLabel("Monto total manual", { exact: true }).fill("100000");
  await reservationForm.locator("label").filter({ hasText: "Moneda" }).locator("select").selectOption("ARS");
  await reservationForm.getByPlaceholder("Explicá brevemente el acuerdo comercial").fill("Importe base sintético para validar recargo de tarjeta");
  await expect(reservationForm.getByTestId("manual-rate-adjustment-confirm")).toBeVisible();
  await reservationForm.getByTestId("manual-rate-adjustment-confirm").check();

  const reservationResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/reservations/" && response.request().method() === "POST";
  });
  await reservationForm.getByRole("button", { name: "Crear", exact: true }).click();
  const reservationResponse = await reservationResponsePromise;
  expect(reservationResponse.status()).toBe(201);
  const reservation = await reservationResponse.json() as { id: number; total_amount: number; currency_code: string };
  expect(reservation).toMatchObject({ total_amount: 100000, currency_code: "ARS" });
  await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();

  // Manual-total creation intentionally leaves its confirmation form open so
  // the operator can review the saved currency snapshot. Close that overlay
  // before interacting with the reservation table underneath it.
  const manualTotalConfirmation = page.locator("div.fixed").filter({ has: reservationForm });
  await expect(manualTotalConfirmation).toBeVisible();
  const manualTotalHeader = manualTotalConfirmation
    .getByRole("heading", { name: "Reserva", exact: true })
    .locator("xpath=../..");
  await manualTotalHeader.getByRole("button", { name: "Cerrar", exact: true }).click();
  await expect(manualTotalConfirmation).not.toBeVisible();

  const reservationTable = page.locator("table").filter({ hasText: "Código" });
  const reservationRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await expect(reservationRow).toHaveCount(1);
  await reservationRow.getByRole("button", { name: "Editar", exact: true }).click();

  const editModal = page.locator("div.fixed").filter({ hasText: "Pagos y balance" });
  const editForm = editModal.locator("form").filter({ hasText: "Pagos y balance" });
  await expect(editForm).toBeVisible();
  await expect.poll(() => readStat(editForm, "Total")).toBe(100000);
  const quoteRequestPromise = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname === "/api/payment-surcharges/quote" && request.method() === "POST";
  });
  await editForm.locator("label").filter({ hasText: "Medio de pago" }).locator("select").selectOption("credit_card");
  const quoteRequest = await quoteRequestPromise;
  expect(quoteRequest.postDataJSON()).toMatchObject({
    reservation_id: reservation.id,
    payment_method: "credit_card",
    currency_code: "ARS"
  });
  const cardCouponInput = editForm
    .locator("label")
    .filter({ hasText: "Cupón verificado del posnet" })
    .locator("input[type='text']");
  await expect(cardCouponInput).toBeVisible();
  await cardCouponInput.fill(`QA-POS-${suffix}`);

  const quoteSummary = editForm.getByTestId("payment-backend-quote");
  await expect(quoteSummary).toContainText("100.000");
  await expect(quoteSummary).toContainText("3.000");
  await expect(quoteSummary).toContainText("103.000");

  const paymentRequestPromise = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname === "/api/payments" && request.method() === "POST";
  });
  const paymentSummaryResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === `/api/payments/summary/${reservation.id}`
      && response.request().method() === "GET"
      && response.status() === 200;
  });
  await editForm.getByRole("button", { name: "Pago total", exact: true }).click();

  const paymentRequest = await paymentRequestPromise;
  expect(paymentRequest.postDataJSON()).toMatchObject({
    reservation_id: reservation.id,
    amount: 100000,
    payment_method: "credit_card",
    transaction_type: "full_payment",
    currency: "ARS",
    manual_reference: `QA-POS-${suffix}`,
    payment_quote_token: expect.any(String)
  });
  expect((paymentRequest.postDataJSON() as { payment_quote_token?: string }).payment_quote_token?.length ?? 0).toBeGreaterThan(0);

  const paymentSummaryResponse = await paymentSummaryResponsePromise;
  const paymentSummary = await paymentSummaryResponse.json() as {
    total_amount: number;
    amount_paid: number;
    transactions: Array<{ amount: number; fee_amount: number; gross_amount: number; method: string; status: string }>;
  };
  expect(paymentSummary.total_amount).toBe(100000);
  expect(paymentSummary.amount_paid).toBe(100000);
  expect(paymentSummary.transactions).toHaveLength(1);
  expect(paymentSummary.transactions[0]).toMatchObject({
    amount: 100000,
    fee_amount: 3000,
    gross_amount: 103000,
    method: "credit_card",
    status: "completed"
  });

  await expect.poll(() => readStat(editForm, "Pagado")).toBe(100000);
  await expect.poll(() => readStat(editForm, "Saldo")).toBe(0);
  const transactionRow = editForm.locator("li").filter({ hasText: "credit_card" });
  await expect(transactionRow).toHaveCount(1);
  await expect(transactionRow).toContainText("recargo");
  await expect(transactionRow).toContainText("3.000");
  await expect(transactionRow).toContainText("103.000");
});
