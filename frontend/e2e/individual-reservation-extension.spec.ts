import { expect, test, type Page, type Route } from "@playwright/test";

const credentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

const reservationId = 9001;

function localIsoDate(offsetDays: number) {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("individual extension quotes before confirmation and supports payment requests or received payments", async ({ page }) => {
  const initialCheckout = localIsoDate(3);
  const extensionOneCheckout = localIsoDate(4);
  const extensionTwoCheckout = localIsoDate(5);
  let currentReservation: Record<string, unknown> = {
    id: reservationId,
    confirmation_code: "E2E-EXT-9001",
    guest_id: 91,
    guest: { id: 91, first_name: "Huésped", last_name: "Extensión E2E" },
    room_id: null,
    category_id: 1,
    category_name: "Standard E2E",
    company_id: null,
    group_id: null,
    check_in_date: localIsoDate(1),
    check_out_date: initialCheckout,
    total_amount: 100000,
    amount_paid: 100000,
    deposit_amount: 0,
    status: "checked_in",
    source: "direct",
    external_id: null,
    source_provider_code: null,
    num_adults: 1,
    num_children: 0,
    currency_code: "ARS",
    allocation_status: "allocated",
    settlement_status: "settled",
    payment_collection_model: "hotel_collect",
    version: 4
  };
  let previewRequests = 0;
  const extensionRequests: Array<Record<string, unknown>> = [];
  const externalOrEmailWrites: string[] = [];

  const reservationForResponse = () => ({ ...currentReservation });
  const financialSummary = () => {
    const total = Number(currentReservation.total_amount);
    const paid = Number(currentReservation.amount_paid);
    return {
      reservation_id: reservationId,
      confirmation_code: currentReservation.confirmation_code,
      status: currentReservation.status,
      currency_code: "ARS",
      total_amount: total,
      deposit_required: 0,
      amount_paid: paid,
      hotel_received_amount: paid,
      ota_prepaid_amount: 0,
      balance_due: Math.max(0, total - paid),
      operational_total_amount: total,
      operational_balance_due: Math.max(0, total - paid),
      billing_adjustment_total: 0,
      payment_collection_model: "hotel_collect",
      settlement_status: "settled",
      has_financial_reconciliation_gap: false,
      financial_reconciliation_gap: null,
      transactions: [],
      billing_adjustments: [],
      completed_payments: paid > 0 ? 1 : 0
    };
  };
  const operationsSummary = () => ({
    reservation_id: reservationId,
    confirmation_code: currentReservation.confirmation_code,
    status: currentReservation.status,
    source: "direct",
    source_provider_code: null,
    allocation_status: "allocated",
    requires_manual_review: false,
    payment_collection_model: "hotel_collect",
    settlement_status: "settled",
    pending_action_count: 0,
    pending_actions: [],
    financial_summary: financialSummary(),
    ota_link: null,
    open_adjustments: [],
    latest_room_move: null
  });

  await page.route(new RegExp(`/api/reservations/${reservationId}$`), async (route) => {
    if (route.request().method() === "GET") return fulfillJson(route, reservationForResponse());
    return route.continue();
  });
  await page.route(new RegExp(`/api/reservations/${reservationId}/operations-summary$`), (route) =>
    fulfillJson(route, operationsSummary())
  );
  await page.route(new RegExp(`/api/payments/summary/${reservationId}$`), (route) =>
    fulfillJson(route, financialSummary())
  );
  await page.route(new RegExp(`/api/reservations/${reservationId}/extend-preview(?:\\?.*)?$`), async (route) => {
    previewRequests += 1;
    const url = new URL(route.request().url());
    return fulfillJson(route, {
      reservation_id: reservationId,
      current_checkout_date: currentReservation.check_out_date,
      new_checkout_date: url.searchParams.get("new_checkout_date"),
      client_version: currentReservation.version,
      extension_amount: 15000,
      currency_code: "ARS"
    });
  });
  await page.route(new RegExp(`/api/reservations/${reservationId}/extend$`), async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const payload = route.request().postDataJSON() as Record<string, unknown>;
    extensionRequests.push(payload);
    const paymentAction = payload.payment_action;
    currentReservation = {
      ...currentReservation,
      check_out_date: payload.new_checkout_date,
      total_amount: Number(currentReservation.total_amount) + 15000,
      amount_paid: Number(currentReservation.amount_paid) + (paymentAction === "immediate_payment" ? 15000 : 0),
      version: Number(currentReservation.version) + 1
    };
    return fulfillJson(route, {
      reservation: reservationForResponse(),
      extension_amount: 15000,
      transaction: paymentAction === "immediate_payment" ? {
        id: 7001,
        amount: 15000,
        currency: "ARS",
        method: "bank_transfer",
        type: "balance_payment",
        status: "completed",
        manual_reference: "QA-TRANSFER-001",
        created_at: new Date().toISOString()
      } : null,
      payment_link: paymentAction === "payment_link" ? {
        id: 7002,
        reservation_id: reservationId,
        provider: "local",
        link_code: "local-e2e-link",
        requested_amount: 15000,
        collected_amount: 0,
        currency: "ARS",
        recipient_email: "extension-e2e@example.test",
        status: "pending",
        execution_mode: "local_only",
        payable: false,
        external_checkout_url: null,
        created_at: new Date().toISOString()
      } : null
    });
  });
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      new RegExp("/api/(?:payments?|payment-links|reservations/" + reservationId + "/communications)$").test(
        new URL(request.url()).pathname
      )
    ) externalOrEmailWrites.push(`${request.method()} ${new URL(request.url()).pathname}`);
  });

  await login(page);
  await page.goto(`/dashboard?reserva=${reservationId}`);
  const drawer = page.getByRole("dialog", { name: "E2E-EXT-9001" });
  await expect(drawer).toBeVisible();
  const panel = drawer.getByTestId("individual-extension");
  await expect(panel).toBeVisible();

  const checkout = panel.getByLabel("Nueva fecha de salida");
  await expect(checkout).toHaveValue(extensionOneCheckout);
  await panel.getByRole("button", { name: "Ver importe y confirmar" }).click();
  await expect(drawer.getByText("Ingresá un correo válido para la solicitud de pago.", { exact: true })).toBeVisible();
  expect(previewRequests).toBe(0);
  expect(extensionRequests).toHaveLength(0);

  await panel.getByLabel("Correo para la solicitud de pago").fill("extension-e2e@example.test");
  const firstPreview = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith(`/api/reservations/${reservationId}/extend-preview`)
  );
  await panel.getByRole("button", { name: "Ver importe y confirmar" }).click();
  expect((await firstPreview).ok()).toBeTruthy();
  const confirmation = page.getByRole("alertdialog", { name: "Confirmar extensión y cobro" });
  await expect(confirmation).toContainText(extensionOneCheckout);
  await expect(confirmation).toContainText("15.000");
  await confirmation.getByRole("button", { name: "Volver" }).click();
  await expect(confirmation).toHaveCount(0);
  expect(extensionRequests).toHaveLength(0);
  expect(externalOrEmailWrites).toEqual([]);

  const secondPreview = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith(`/api/reservations/${reservationId}/extend-preview`)
  );
  await panel.getByRole("button", { name: "Ver importe y confirmar" }).click();
  expect((await secondPreview).ok()).toBeTruthy();
  const linkExtensionResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith(`/api/reservations/${reservationId}/extend`) &&
    response.request().method() === "POST"
  );
  await page.getByRole("alertdialog", { name: "Confirmar extensión y cobro" })
    .getByRole("button", { name: "Confirmar extensión" }).click();
  const linkResult = await linkExtensionResponse;
  expect(linkResult.ok()).toBeTruthy();
  expect(extensionRequests[0]).toMatchObject({
    new_checkout_date: extensionOneCheckout,
    client_version: 4,
    pricing_mode: "current_rate",
    payment_action: "payment_link",
    payment_link: {
      reservation_id: reservationId,
      requested_amount: 15000,
      currency: "ARS",
      recipient_email: "extension-e2e@example.test"
    }
  });
  await expect(panel.getByTestId("individual-extension-payment-link")).toContainText(
    "Solicitud guardada localmente; no se puede pagar ni se envió al huésped."
  );
  expect(externalOrEmailWrites).toEqual([]);

  await expect(checkout).toHaveValue(extensionTwoCheckout);
  await panel.getByLabel("Cómo cobrar la extensión").selectOption("immediate_payment");
  await panel.getByLabel("Método de pago recibido").selectOption("bank_transfer");
  await panel.getByRole("button", { name: "Ver importe y confirmar" }).click();
  await expect(drawer.getByText("Ingresá el cupón o número de operación del pago recibido.", { exact: true })).toBeVisible();
  expect(previewRequests).toBe(2);

  await panel.getByLabel("Cupón u operación de referencia").fill("QA-TRANSFER-001");
  const thirdPreview = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith(`/api/reservations/${reservationId}/extend-preview`)
  );
  await panel.getByRole("button", { name: "Ver importe y confirmar" }).click();
  expect((await thirdPreview).ok()).toBeTruthy();
  const immediateExtensionResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith(`/api/reservations/${reservationId}/extend`) &&
    response.request().method() === "POST"
  );
  await page.getByRole("alertdialog", { name: "Confirmar extensión y cobro" })
    .getByRole("button", { name: "Confirmar extensión" }).click();
  expect((await immediateExtensionResponse).ok()).toBeTruthy();
  expect(extensionRequests[1]).toMatchObject({
    new_checkout_date: extensionTwoCheckout,
    client_version: 5,
    pricing_mode: "current_rate",
    payment_action: "immediate_payment",
    immediate_payment: {
      reservation_id: reservationId,
      amount: 15000,
      payment_method: "bank_transfer",
      transaction_type: "balance_payment",
      currency: "ARS",
      manual_reference: "QA-TRANSFER-001"
    }
  });
  await expect(drawer.getByText("Extensión aplicada y pago presencial registrado.", { exact: true })).toBeVisible();
  expect(extensionRequests).toHaveLength(2);
  expect(externalOrEmailWrites).toEqual([]);
});
