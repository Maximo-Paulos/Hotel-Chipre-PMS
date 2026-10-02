import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const credentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};
const backendURL = (process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040").replace(/\/$/, "");

type TestSession = {
  hotel_id: number;
  access_token: string;
  csrf_token?: string;
  user: { email: string };
};

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

async function readSession(request: APIRequestContext): Promise<TestSession> {
  const response = await request.post(`${backendURL}/api/auth/login`, { data: credentials });
  expect(response.ok()).toBeTruthy();
  return response.json() as Promise<TestSession>;
}

function authHeaders(session: TestSession) {
  return {
    "X-Hotel-Id": String(session.hotel_id),
    "X-User-Id": session.user.email,
    Authorization: `Bearer ${session.access_token}`,
    "X-CSRF-Token": String(session.csrf_token || ""),
    "Content-Type": "application/json"
  };
}

function localIsoDate(offsetDays: number) {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

test("company check-in records and applies a deferred extension without registering payment", async ({ page, request }) => {
  const session = await readSession(request);
  const headers = authHeaders(session);
  const suffix = Date.now().toString();

  const companyResponse = await request.post(`${backendURL}/api/companies`, {
    headers,
    data: {
      legal_name: `QA Empresa Diferida ${suffix} SRL`,
      display_name: `QA Empresa Diferida ${suffix}`,
      country_code: "AR",
      payment_deferred: true,
      base_price: 100
    }
  });
  expect(companyResponse.status()).toBe(201, await companyResponse.text());
  const company = await companyResponse.json() as { id: number };

  const guestResponse = await request.post(`${backendURL}/api/guests/`, {
    headers,
    data: { first_name: "Huésped QA", last_name: `Empresa ${suffix}` }
  });
  expect(guestResponse.status()).toBe(201, await guestResponse.text());
  const guest = await guestResponse.json() as { id: number };

  const categoriesResponse = await request.get(`${backendURL}/api/rooms/categories`, { headers });
  expect(categoriesResponse.ok()).toBeTruthy();
  const categories = await categoriesResponse.json() as Array<{ id: number; name: string }>;
  const category = categories.find((item) => item.name === "Standard E2E");
  expect(category).toBeTruthy();

  const checkIn = localIsoDate(0);
  const checkOut = localIsoDate(1);
  const quoteResponse = await request.get(`${backendURL}/api/bookings/price-quote`, {
    headers,
    params: {
      category_id: category!.id,
      check_in_date: checkIn,
      check_out_date: checkOut,
      guest_id: guest.id,
      company_id: company.id,
      occupancy: 1
    }
  });
  expect(quoteResponse.ok()).toBeTruthy();
  const quote = await quoteResponse.json() as {
    quote_token: string;
    company_billing_deferred: boolean;
    amounts_disclosed: boolean;
    total_amount: number | null;
    deposit_amount: number | null;
    breakdown: unknown[];
    promotions_applied: unknown[];
  };
  expect(quote.company_billing_deferred).toBe(true);
  expect(quote.amounts_disclosed).toBe(false);
  expect(quote.total_amount).toBeNull();
  expect(quote.deposit_amount).toBeNull();
  expect(quote.breakdown).toEqual([]);
  expect(quote.promotions_applied).toEqual([]);

  const reservationResponse = await request.post(`${backendURL}/api/reservations/`, {
    headers,
    data: {
      guest_id: guest.id,
      category_id: category!.id,
      company_id: company.id,
      check_in_date: checkIn,
      check_out_date: checkOut,
      num_adults: 1,
      num_children: 0,
      quote_token: quote.quote_token,
      reservation_comment: "QA de check-in corporativo"
    }
  });
  expect(reservationResponse.status()).toBe(201, await reservationResponse.text());
  const reservation = await reservationResponse.json() as {
    id: number;
    confirmation_code: string;
    check_in_date: string;
    check_out_date: string;
    total_amount: number | null;
    amount_paid: number | null;
    company_billing_deferred: boolean;
  };
  expect(reservation.company_billing_deferred).toBe(true);
  expect(reservation.total_amount).toBeNull();
  expect(reservation.amount_paid).toBeNull();

  const financialSummaryResponse = await request.get(`${backendURL}/api/payments/summary/${reservation.id}`, { headers });
  expect(financialSummaryResponse.ok()).toBeTruthy();
  const financialSummary = await financialSummaryResponse.json() as {
    company_billing_deferred: boolean;
    total_amount: number | null;
    deposit_required: number | null;
    amount_paid: number | null;
    balance_due: number | null;
    financial_reconciliation_gap: number | null;
  };
  expect(financialSummary.company_billing_deferred).toBe(true);
  expect(financialSummary.total_amount).toBeNull();
  expect(financialSummary.deposit_required).toBeNull();
  expect(financialSummary.amount_paid).toBeNull();
  expect(financialSummary.balance_due).toBeNull();
  expect(financialSummary.financial_reconciliation_gap).toBeNull();

  let releaseValidation!: () => void;
  let validationReached!: () => void;
  let validationAttempts = 0;
  const validationGate = new Promise<void>((resolve) => { releaseValidation = resolve; });
  const validationStarted = new Promise<void>((resolve) => { validationReached = resolve; });
  await page.route(`**/api/checkin/validate/${guest.id}`, async (route) => {
    validationAttempts += 1;
    validationReached();
    if (validationAttempts === 1) {
      await validationGate;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "temporary QA validation failure" }) });
      return;
    }
    await route.continue();
  });

  await login(page);
  await page.goto(`/dashboard?reserva=${reservation.id}`);
  const drawer = page.getByRole("dialog", { name: reservation.confirmation_code });
  await expect(drawer).toBeVisible();
  await validationStarted;

  const checkInButton = drawer.getByRole("button", { name: "Confirmar check-in" });
  await expect(checkInButton).toBeDisabled();
  releaseValidation();
  await expect(drawer.getByRole("button", { name: "Reintentar" })).toBeVisible();
  await expect(checkInButton).toBeDisabled();
  await drawer.getByRole("button", { name: "Reintentar" }).click();
  await expect(drawer.getByTestId("checkin-capture-form")).toBeVisible();
  await expect(checkInButton).toBeEnabled();

  const capture = drawer.getByTestId("checkin-capture-form");
  await capture.getByLabel("Tipo de documento").selectOption("DNI");
  await capture.getByLabel("Número de documento").fill(`QA-DNI-${suffix}`);
  await capture.getByLabel("Nacionalidad").fill("Argentina");
  await capture.getByLabel("País", { exact: true }).fill("Argentina");
  await capture.getByLabel("Lugar de nacimiento").fill("Rosario");
  await capture.getByLabel("País de nacimiento").fill("Argentina");
  await capture.getByLabel("Estado civil").fill("Soltero");
  await capture.getByLabel("Profesión").fill("QA");
  await capture.getByRole("checkbox").check();
  await checkInButton.click();
  await expect(drawer.getByText("Check-in registrado.", { exact: true })).toBeVisible();

  const extensionPanel = drawer.getByTestId("company-extension-request");
  await expect(extensionPanel).toContainText("No hay una extensión pendiente");
  const extensionNote = "La empresa pidió extender una noche; falta confirmación";
  await extensionPanel.getByLabel("Pedido o detalle pendiente").fill(extensionNote);
  await extensionPanel.getByRole("button", { name: "Registrar solicitud" }).click();
  await expect(extensionPanel).toContainText("Extensión solicitada, pendiente de confirmación");
  await expect(extensionPanel).toContainText(extensionNote);
  await expect(extensionPanel.getByRole("button", { name: "Quitar solicitud" })).toHaveCount(0);

  const afterRequest = await request.get(`${backendURL}/api/reservations/${reservation.id}`, { headers });
  expect(afterRequest.ok()).toBeTruthy();
  const updated = await afterRequest.json() as typeof reservation & {
    company_extension_request_pending: boolean;
    company_extension_request_note: string;
  };
  expect(updated.company_extension_request_pending).toBe(true);
  expect(updated.company_extension_request_note).toBe(extensionNote);
  expect(updated.check_in_date).toBe(reservation.check_in_date);
  expect(updated.check_out_date).toBe(reservation.check_out_date);
  expect(updated.total_amount).toBeNull();
  expect(updated.amount_paid).toBeNull();

  const extensionApplyPanel = drawer.getByTestId("company-extension-apply");
  await expect(extensionApplyPanel).toBeVisible();
  const extendedCheckoutDate = localIsoDate(2);
  await extensionApplyPanel.getByLabel("Nueva fecha de salida").fill(extendedCheckoutDate);

  const financialWrites: string[] = [];
  const onFinancialWrite = (requestEvent: import("@playwright/test").Request) => {
    if (
      ["POST", "PUT", "PATCH", "DELETE"].includes(requestEvent.method()) &&
      /\/api\/(?:payments?|payment-links|cash)(?:\/|$)/.test(new URL(requestEvent.url()).pathname)
    ) financialWrites.push(`${requestEvent.method()} ${new URL(requestEvent.url()).pathname}`);
  };
  page.on("request", onFinancialWrite);
  const writesBeforeExtension = financialWrites.length;
  const extensionResponsePromise = page.waitForResponse((response) =>
    response.url().endsWith(`/api/reservations/${reservation.id}/extend`) && response.request().method() === "POST"
  );
  await extensionApplyPanel.getByRole("button", { name: "Aplicar extensión" }).click();
  const confirmation = page.getByRole("alertdialog", { name: "Confirmar extensión de estadía" });
  await expect(confirmation).toBeVisible();
  await confirmation.getByRole("button", { name: "Confirmar extensión" }).click();
  const extensionResponse = await extensionResponsePromise;
  expect(extensionResponse.status()).toBe(200, await extensionResponse.text());
  const extensionResult = await extensionResponse.json() as {
    reservation: { check_out_date: string; total_amount: number | null; amount_paid: number | null; company_billing_deferred: boolean };
    extension_amount: number | string;
    transaction: null;
    payment_link: null;
  };
  expect(extensionResponse.request().postDataJSON()).toMatchObject({
    new_checkout_date: extendedCheckoutDate,
    pricing_mode: "current_rate",
    payment_action: "company_account"
  });
  expect(extensionResult.transaction).toBeNull();
  expect(extensionResult.payment_link).toBeNull();
  expect(Number(extensionResult.extension_amount)).toBe(0);
  expect(extensionResult.reservation.company_billing_deferred).toBe(true);
  expect(extensionResult.reservation.total_amount).toBeNull();
  expect(extensionResult.reservation.amount_paid).toBeNull();
  await expect(drawer.getByText("Extensión aplicada. El alojamiento se factura fuera del PMS.", { exact: true })).toBeVisible();
  expect(financialWrites.slice(writesBeforeExtension)).toEqual([]);
  page.off("request", onFinancialWrite);

  const afterExtensionResponse = await request.get(`${backendURL}/api/reservations/${reservation.id}`, { headers });
  expect(afterExtensionResponse.ok()).toBeTruthy();
  const afterExtension = await afterExtensionResponse.json() as typeof updated;
  expect(afterExtension.check_in_date).toBe(reservation.check_in_date);
  expect(afterExtension.check_out_date).toBe(extendedCheckoutDate);
  expect(afterExtension.total_amount).toBeNull();
  expect(afterExtension.amount_paid).toBeNull();
  expect(afterExtension.company_extension_request_pending).toBe(false);
  expect(afterExtension.company_extension_request_note).toBe(extensionNote);
  expect(extensionResult.reservation.check_out_date).toBe(extendedCheckoutDate);

  const updatedFinancialSummaryResponse = await request.get(`${backendURL}/api/payments/summary/${reservation.id}`, { headers });
  expect(updatedFinancialSummaryResponse.ok()).toBeTruthy();
  const updatedFinancialSummary = await updatedFinancialSummaryResponse.json() as typeof financialSummary;
  expect(updatedFinancialSummary.company_billing_deferred).toBe(true);
  expect(updatedFinancialSummary.total_amount).toBeNull();
  expect(updatedFinancialSummary.deposit_required).toBeNull();
  expect(updatedFinancialSummary.amount_paid).toBeNull();
  expect(updatedFinancialSummary.balance_due).toBeNull();
  expect(updatedFinancialSummary.financial_reconciliation_gap).toBeNull();
});
