import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const backendURL = (process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040").replace(/\/$/, "");

const owner = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};
const receptionist = {
  email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
  password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!"
};

type ApiSession = {
  hotel_id: number;
  access_token: string;
  csrf_token?: string;
  user: { email: string };
};

async function readSession(request: APIRequestContext, credentials: { email: string; password: string }) {
  const response = await request.post(`${backendURL}/api/auth/login`, { data: credentials });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json() as Promise<ApiSession>;
}

function authHeaders(session: ApiSession) {
  return {
    "X-Hotel-Id": String(session.hotel_id),
    "X-User-Id": session.user.email,
    Authorization: `Bearer ${session.access_token}`,
    "X-CSRF-Token": String(session.csrf_token || ""),
    "Content-Type": "application/json"
  };
}

const localIsoDate = (offsetDays: number) => {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
};

test.skip(
  process.env.DOLARAPI_RATES_ENABLED !== "false",
  "La simulación de caída de DolarAPI se ejecuta en una corrida aislada con DolarAPI desactivada."
);

async function login(page: Page, credentials: { email: string; password: string }) {
  page.on("response", (response) => {
    const request = response.request();
    const url = new URL(response.url());
    if (url.pathname === "/api/auth/login") {
      console.info(`[manual-fx-login] ${request.method()} ${url.pathname} status=${response.status()}`);
    }
  });
  page.on("requestfailed", (request) => {
    const url = new URL(request.url());
    if (url.pathname === "/api/auth/login") {
      const error = (request.failure()?.errorText || "unknown").replace(/[\r\n\t]+/g, " ").slice(0, 120);
      console.info(`[manual-fx-login] ${request.method()} ${url.pathname} failed=${error}`);
    }
  });
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("authorized owner sets an outage FX amount and reception records that exact amount", async ({ page, request }) => {
  const suffix = `${Date.now()}`;
  const guestLastName = `QA FX Manual ${suffix}`;

  await login(page, owner);
  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();

  const reservationForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(reservationForm).toBeVisible();
  await reservationForm.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
  await reservationForm.getByPlaceholder("Nombre").fill("Huésped");
  await reservationForm.getByPlaceholder("Apellido").fill(guestLastName);
  await reservationForm.getByPlaceholder("Email").fill(`qa.fx.manual.${suffix}@example.test`);
  await reservationForm.getByPlaceholder("Teléfono").fill(`11${Date.now().toString().slice(-8)}55`);
  await reservationForm.getByLabel("Tipo de documento").selectOption("DNI");
  await reservationForm.getByPlaceholder("Documento").fill(`QA-FXM-${suffix}`);
  await reservationForm.getByRole("button", { name: "Crear Huésped y asignar ID" }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = reservationForm.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  await categorySelect.selectOption((await categoryOption.getAttribute("value"))!);
  await reservationForm.getByLabel("Check-in", { exact: true }).fill(localIsoDate(45));
  await reservationForm.getByLabel("Check-out", { exact: true }).fill(localIsoDate(46));
  await reservationForm.getByLabel("Monto total manual", { exact: true }).fill("55000");
  await reservationForm.locator("label").filter({ hasText: "Moneda" }).locator("select").selectOption("ARS");
  await reservationForm.getByPlaceholder("Explicá brevemente el acuerdo comercial").fill("Importe sintético para probar el respaldo manual FX");
  await reservationForm.getByTestId("manual-rate-adjustment-confirm").check();

  const reservationResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/reservations/" && response.request().method() === "POST";
  });
  await reservationForm.getByRole("button", { name: "Crear", exact: true }).click();
  const reservationResponse = await reservationResponsePromise;
  expect(reservationResponse.status()).toBe(201);
  const reservation = await reservationResponse.json() as { id: number; total_amount: number; currency_code: string };
  expect(reservation).toMatchObject({ total_amount: 55000, currency_code: "ARS" });

  const manualTotalConfirmation = page.locator("div.fixed").filter({ has: reservationForm });
  await expect(manualTotalConfirmation).toBeVisible();
  await manualTotalConfirmation.getByRole("heading", { name: "Reserva", exact: true })
    .locator("xpath=../..")
    .getByRole("button", { name: "Cerrar", exact: true }).click();

  const reservationRow = page.locator("table").filter({ hasText: "Código" }).locator("tbody tr").filter({ hasText: guestLastName });
  await expect(reservationRow).toHaveCount(1);
  await reservationRow.getByRole("button", { name: "Editar", exact: true }).click();
  const editModal = page.locator("div.fixed").filter({ hasText: "Pagos y balance" });
  const editForm = editModal.locator("form").filter({ hasText: "Pagos y balance" });
  await expect(editForm).toBeVisible();
  await editForm.locator("label").filter({ hasText: "Medio de pago" }).locator("select").selectOption("cash");
  await editForm.getByTestId("payment-tender-currency").selectOption("USD");
  await expect(editForm.getByTestId("payment-quote-error")).toBeVisible();
  await expect(editForm.getByTestId("manual-fx-quote-form")).toBeVisible();

  await editForm.getByRole("spinbutton", { name: "Monto del movimiento" }).fill("30");
  await editForm.getByTestId("manual-fx-reservation-amount").fill("55000");
  await editForm.getByTestId("manual-fx-reason").fill("API sin cotización vigente; monto aprobado para esta reserva");
  const approvedQuotePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/payment-surcharges/manual-fx-quote" && response.request().method() === "POST";
  });
  await editForm.getByTestId("manual-fx-quote-save").click();
  const approvedQuoteResponse = await approvedQuotePromise;
  expect(approvedQuoteResponse.status()).toBe(201);
  const approvedQuote = await approvedQuoteResponse.json() as {
    base_amount: number | string;
    applied_amount: number | string;
    currency_code: string;
    manual_fx_quote_id: number;
    manual_fx_reason: string;
  };
  expect(Number(approvedQuote.base_amount)).toBe(30);
  expect(Number(approvedQuote.applied_amount)).toBe(55000);
  expect(approvedQuote).toMatchObject({
    currency_code: "USD",
    manual_fx_reason: "API sin cotización vigente; monto aprobado para esta reserva"
  });
  expect(approvedQuote.manual_fx_quote_id).toBeGreaterThan(0);
  await expect(page.getByText("Importe manual autorizado para esta reserva. Ya puede registrarse el cobro con ese monto.", { exact: true })).toBeVisible();

  // The collection permission is independent from the FX amount approval.
  await page.context().clearCookies();
  await login(page, receptionist);
  const sessionsResponsePromise = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/cash-register/sessions" && response.request().method() === "GET"
  );
  await page.goto("/caja");
  await sessionsResponsePromise;
  const openingForm = page.locator("form").filter({ hasText: "Saldo inicial" }).filter({ hasText: "Abrir caja" });
  await openingForm.locator("label").filter({ hasText: "Moneda" }).locator("select").selectOption("USD");
  await openingForm.getByText("Saldo inicial", { exact: true }).locator("..").locator("input").fill("0");
  const openCashResponsePromise = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/cash-register/sessions" && response.request().method() === "POST"
  );
  await openingForm.getByRole("button", { name: "Abrir caja", exact: true }).click();
  const openCashResponse = await openCashResponsePromise;
  expect(openCashResponse.status()).toBe(201);
  await expect(page.getByText("Caja abierta.", { exact: true })).toBeVisible();

  await page.goto("/reservas");
  const receptionistSession = await readSession(request, receptionist);
  const unauthorizedApprovalResponse = await request.post(`${backendURL}/api/payment-surcharges/manual-fx-quote`, {
    headers: authHeaders(receptionistSession),
    data: {
      reservation_id: reservation.id,
      payment_method: "cash",
      currency_code: "USD",
      reservation_amount: 55000,
      tender_amount: 30,
      reason: "Attempted approval without permission"
    }
  });
  expect(unauthorizedApprovalResponse.status()).toBe(403);
  const cashierReservationRow = page.locator("table").filter({ hasText: "Código" }).locator("tbody tr").filter({ hasText: guestLastName });
  await expect(cashierReservationRow).toHaveCount(1);
  await cashierReservationRow.getByRole("button", { name: "Editar", exact: true }).click();
  const cashierModal = page.locator("div.fixed").filter({ hasText: "Pagos y balance" });
  const cashierForm = cashierModal.locator("form").filter({ hasText: "Pagos y balance" });
  await expect(cashierForm).toBeVisible();
  await cashierForm.locator("label").filter({ hasText: "Medio de pago" }).locator("select").selectOption("cash");
  await cashierForm.getByTestId("payment-tender-currency").selectOption("USD");
  await expect(cashierForm.getByTestId("payment-quote-error")).toBeVisible();
  await expect(cashierForm.getByTestId("manual-fx-quote-form")).toHaveCount(0);
  await expect(cashierForm.getByTestId("manual-fx-amount-must-match")).toHaveCount(0);
  await expect(cashierForm.getByTestId("payment-backend-quote")).toBeVisible();
  await cashierForm.getByTestId("reservation-payment-cash-received").fill("30");

  const paymentRequestPromise = page.waitForRequest((request) =>
    new URL(request.url()).pathname === "/api/payments" && request.method() === "POST"
  );
  const summaryResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === `/api/payments/summary/${reservation.id}` && response.request().method() === "GET" && response.status() === 200;
  });
  await cashierForm.getByRole("button", { name: "Pago total", exact: true }).click();
  const paymentRequest = await paymentRequestPromise;
  expect(paymentRequest.postDataJSON()).toMatchObject({
    reservation_id: reservation.id,
    amount: 30,
    payment_method: "cash",
    transaction_type: "full_payment",
    currency: "USD",
    manual_fx_quote_id: approvedQuote.manual_fx_quote_id
  });
  const summaryResponse = await summaryResponsePromise;
  const summary = await summaryResponse.json() as { total_amount: number; amount_paid: number; balance_due: number };
  expect(summary).toMatchObject({ total_amount: 55000, amount_paid: 55000, balance_due: 0 });
});
