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
  const pendingBalanceCheckout = localIsoDate(6);
  const nextSuggestedCheckout = localIsoDate(7);
  const blockedExtensionCheckout = localIsoDate(8);
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
  const previewRequestsByAction: string[] = [];
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
  await page.route("**/api/payment-surcharges", (route) => fulfillJson(route, []));
  await page.route(new RegExp(`/api/reservations/${reservationId}/extend-preview(?:\\?.*)?$`), async (route) => {
    previewRequests += 1;
    const url = new URL(route.request().url());
    const newCheckoutDate = url.searchParams.get("new_checkout_date") || "";
    const paymentAction = url.searchParams.get("payment_action") || "";
    previewRequestsByAction.push(paymentAction);
    const isBlocked = newCheckoutDate === blockedExtensionCheckout;
    const fingerprint = newCheckoutDate === extensionOneCheckout
      ? "a".repeat(64)
      : newCheckoutDate === extensionTwoCheckout
        ? "b".repeat(64)
        : "c".repeat(64);
    return fulfillJson(route, {
      reservation_id: reservationId,
      current_checkout_date: currentReservation.check_out_date,
      new_checkout_date: newCheckoutDate,
      client_version: currentReservation.version,
      extension_amount: 15000,
      currency_code: "ARS",
      impact_plan: {
        fingerprint,
        actions: [{
          action: isBlocked
            ? "blocked"
            : newCheckoutDate === extensionTwoCheckout
              ? "moved_superior"
              : "moved_equivalent",
          room_label: "Habitación 12",
          check_in_date: localIsoDate(4),
          check_out_date: localIsoDate(6),
          confirmation_code: "QA-FUTURE-EXT-9002",
          ...(isBlocked ? { reason_code: "future_reservation_has_payment" } : {})
        }]
      }
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
  await expect(confirmation).toContainText("Impacto en otras reservas");
  await expect(confirmation).toContainText("Habitación 12");
  await expect(confirmation).toContainText("Se moverá a una habitación equivalente");
  await expect(confirmation).toContainText("reserva QA-FUTURE-EXT-9002");
  await expect(confirmation).not.toContainText("Huésped Extensión E2E");
  expect(previewRequestsByAction[0]).toBe("individual");
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
    confirmed_impact_fingerprint: "a".repeat(64),
    payment_link: {
      reservation_id: reservationId,
      requested_amount: 15000,
      currency: "ARS",
      recipient_email: "extension-e2e@example.test"
    }
  });
  await expect(checkout).toHaveValue(extensionTwoCheckout);
  await expect(panel.getByTestId("individual-extension-payment-link")).toContainText(
    "Solicitud guardada localmente; no se puede pagar ni se envió al huésped."
  );
  expect(externalOrEmailWrites).toEqual([]);

  await panel.getByLabel("Cómo cobrar la extensión").selectOption("immediate_payment");
  await panel.getByLabel("Método de pago recibido").selectOption("cash");
  const thirdPreview = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith(`/api/reservations/${reservationId}/extend-preview`)
  );
  await panel.getByRole("button", { name: "Ver importe y confirmar" }).click();
  expect((await thirdPreview).ok()).toBeTruthy();
  expect(previewRequests).toBe(3);
  const cashTenderInput = panel.getByTestId("individual-extension-cash-received");
  const expectedCashAmount = Number(await cashTenderInput.getAttribute("placeholder"));
  await cashTenderInput.fill(String(expectedCashAmount + 15));
  await expect(panel.getByTestId("individual-extension-cash-received-change")).toContainText("15");
  await panel.getByTestId("individual-extension-cash-confirm").click();
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
    confirmed_impact_fingerprint: "b".repeat(64),
    immediate_payment: {
      reservation_id: reservationId,
      amount: 15000,
      payment_method: "cash",
      transaction_type: "balance_payment",
      currency: "ARS",
      cash_received_amount: expectedCashAmount + 15
    }
  });
  await expect(drawer.getByText("Extensión aplicada y pago presencial registrado.", { exact: true })).toBeVisible();
  expect(previewRequestsByAction).toEqual(["individual", "individual", "individual"]);

  await panel.getByLabel("Cómo cobrar la extensión").selectOption("pending_balance");
  await expect(panel.getByLabel("Correo para la solicitud de pago")).toHaveCount(0);
  await checkout.fill(pendingBalanceCheckout);
  const pendingBalancePreview = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith(`/api/reservations/${reservationId}/extend-preview`)
  );
  await panel.getByRole("button", { name: "Ver importe y confirmar" }).click();
  expect((await pendingBalancePreview).ok()).toBeTruthy();
  expect(previewRequests).toBe(4);
  const pendingBalanceConfirmation = page.getByRole("alertdialog", {
    name: "Confirmar extensión con saldo pendiente"
  });
  await expect(pendingBalanceConfirmation).toContainText(pendingBalanceCheckout);
  await expect(pendingBalanceConfirmation).toContainText("No se registra ni solicita un pago");
  const pendingBalanceExtensionResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith(`/api/reservations/${reservationId}/extend`) &&
    response.request().method() === "POST"
  );
  await pendingBalanceConfirmation.getByRole("button", { name: "Confirmar extensión" }).click();
  const pendingBalanceResult = await pendingBalanceExtensionResponse;
  expect(pendingBalanceResult.ok()).toBeTruthy();
  expect(extensionRequests[2]).toMatchObject({
    new_checkout_date: pendingBalanceCheckout,
    client_version: 6,
    pricing_mode: "current_rate",
    payment_action: "pending_balance",
    confirmed_impact_fingerprint: "c".repeat(64)
  });
  expect(extensionRequests[2]).not.toHaveProperty("payment_link");
  expect(extensionRequests[2]).not.toHaveProperty("immediate_payment");
  expect(Number(currentReservation.total_amount)).toBe(145000);
  expect(Number(currentReservation.amount_paid)).toBe(115000);
  await expect(drawer.getByText("Extensión aplicada. El saldo quedó pendiente de cobro.", { exact: true })).toBeVisible();
  await expect(checkout).toHaveValue(nextSuggestedCheckout);
  expect(externalOrEmailWrites).toEqual([]);

  await checkout.fill(blockedExtensionCheckout);
  await panel.getByLabel("Cómo cobrar la extensión").selectOption("pending_balance");
  const blockedPreview = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith(`/api/reservations/${reservationId}/extend-preview`)
  );
  await panel.getByRole("button", { name: "Ver importe y confirmar" }).click();
  expect((await blockedPreview).ok()).toBeTruthy();
  const blockedImpact = panel.getByTestId("individual-extension-impact-plan");
  await expect(blockedImpact).toContainText("requiere una resolución manual");
  await expect(blockedImpact).toContainText("Habitación 12");
  await expect(blockedImpact).toContainText("QA-FUTURE-EXT-9002");
  await expect(page.getByRole("alertdialog", { name: "Confirmar extensión con saldo pendiente" })).toHaveCount(0);
  expect(extensionRequests).toHaveLength(3);
  expect(externalOrEmailWrites).toEqual([]);
});

test("a fully-paid direct stay can be extended with pending balance and no email or payment request", async ({ page }) => {
  const paidReservationId = 9002;
  const checkoutDate = localIsoDate(2);
  const extendedCheckoutDate = localIsoDate(3);
  const confirmationCode = "E2E-EXT-PAID-9002";
  const extensionAmount = 60000;
  let currentReservation: Record<string, unknown> = {
    id: paidReservationId,
    confirmation_code: confirmationCode,
    guest_id: 92,
    guest: { id: 92, first_name: "Huésped", last_name: "Saldo Pendiente E2E" },
    room_id: 3,
    category_id: 1,
    category_name: "Standard E2E",
    company_id: null,
    group_id: null,
    check_in_date: localIsoDate(0),
    check_out_date: checkoutDate,
    total_amount: 120000,
    amount_paid: 120000,
    deposit_amount: 0,
    status: "fully_paid",
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
  const extensionRequests: Array<Record<string, unknown>> = [];
  const externalPaymentWrites: string[] = [];
  const cashReadsAfterExtension: string[] = [];
  let extensionCommitted = false;
  let failReservationReadAfterExtension = false;
  let failOperationsReadAfterExtension = false;
  let reservationReadsAfterExtension = 0;
  let operationsReadsAfterExtension = 0;
  const financialSummary = () => ({
    reservation_id: paidReservationId,
    confirmation_code: confirmationCode,
    status: currentReservation.status,
    currency_code: "ARS",
    total_amount: currentReservation.total_amount,
    deposit_required: 0,
    amount_paid: currentReservation.amount_paid,
    hotel_received_amount: currentReservation.amount_paid,
    ota_prepaid_amount: 0,
    balance_due: Math.max(0, Number(currentReservation.total_amount) - Number(currentReservation.amount_paid)),
    operational_total_amount: currentReservation.total_amount,
    operational_balance_due: Math.max(0, Number(currentReservation.total_amount) - Number(currentReservation.amount_paid)),
    billing_adjustment_total: 0,
    payment_collection_model: "hotel_collect",
    settlement_status: "settled",
    has_financial_reconciliation_gap: false,
    financial_reconciliation_gap: null,
    transactions: [],
    billing_adjustments: [],
    completed_payments: 1
  });
  const operationsSummary = () => ({
    reservation_id: paidReservationId,
    confirmation_code: confirmationCode,
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

  await page.route(new RegExp(`/api/reservations/${paidReservationId}$`), (route) => {
    if (route.request().method() !== "GET") return route.continue();
    if (extensionCommitted) {
      reservationReadsAfterExtension += 1;
      if (failReservationReadAfterExtension) {
        failReservationReadAfterExtension = false;
        return fulfillJson(route, { detail: "temporary database pool exhaustion" }, 503);
      }
    }
    return fulfillJson(route, { ...currentReservation });
  });
  await page.route(new RegExp(`/api/reservations/${paidReservationId}/operations-summary$`), (route) => {
    if (extensionCommitted) {
      operationsReadsAfterExtension += 1;
      if (failOperationsReadAfterExtension) {
        failOperationsReadAfterExtension = false;
        return fulfillJson(route, { detail: "temporary database pool exhaustion" }, 503);
      }
    }
    return fulfillJson(route, operationsSummary());
  });
  await page.route(new RegExp(`/api/payments/summary/${paidReservationId}$`), (route) =>
    fulfillJson(route, financialSummary())
  );
  await page.route("**/api/payment-surcharges", (route) => fulfillJson(route, []));
  await page.route(new RegExp(`/api/reservations/${paidReservationId}/extend-preview(?:\\?.*)?$`), (route) => {
    const url = new URL(route.request().url());
    const newCheckoutDate = url.searchParams.get("new_checkout_date") || "";
    return fulfillJson(route, {
      reservation_id: paidReservationId,
      current_checkout_date: currentReservation.check_out_date,
      new_checkout_date: newCheckoutDate,
      client_version: currentReservation.version,
      extension_amount: extensionAmount,
      currency_code: "ARS",
      impact_plan: { fingerprint: "d".repeat(64), actions: [] }
    });
  });
  await page.route(new RegExp(`/api/reservations/${paidReservationId}/extend$`), async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const payload = route.request().postDataJSON() as Record<string, unknown>;
    extensionRequests.push(payload);
    currentReservation = {
      ...currentReservation,
      check_out_date: payload.new_checkout_date,
      total_amount: Number(currentReservation.total_amount) + extensionAmount,
      status: "pending",
      version: Number(currentReservation.version) + 1
    };
    extensionCommitted = true;
    failReservationReadAfterExtension = true;
    failOperationsReadAfterExtension = true;
    return fulfillJson(route, {
      reservation: { ...currentReservation },
      extension_amount: extensionAmount,
      transaction: null,
      payment_link: null
    });
  });
  page.on("request", (request) => {
    const pathname = new URL(request.url()).pathname;
    if (extensionCommitted && request.method() === "GET" && pathname.startsWith("/api/cash-register/")) {
      cashReadsAfterExtension.push(pathname);
    }
    if (request.method() !== "POST") return;
    if (/\/api\/(?:payments?|payment-links)(?:\/|$)/.test(pathname)) {
      externalPaymentWrites.push(pathname);
    }
  });

  await login(page);
  await page.goto(`/dashboard?reserva=${paidReservationId}`);
  const drawer = page.getByRole("dialog", { name: confirmationCode });
  await expect(drawer).toBeVisible();
  const panel = drawer.getByTestId("individual-extension");
  await expect(panel).toBeVisible();
  await panel.getByLabel("Cómo cobrar la extensión").selectOption("pending_balance");
  await expect(panel.getByLabel("Correo para la solicitud de pago")).toHaveCount(0);
  await panel.getByLabel("Nueva fecha de salida").fill(extendedCheckoutDate);

  const previewResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith(`/api/reservations/${paidReservationId}/extend-preview`)
  );
  await panel.getByRole("button", { name: "Ver importe y confirmar" }).click();
  expect((await previewResponse).ok()).toBeTruthy();
  const confirmation = page.getByRole("alertdialog", {
    name: "Confirmar extensión con saldo pendiente"
  });
  await expect(confirmation).toContainText(extendedCheckoutDate);
  await expect(confirmation).toContainText("60.000");
  await expect(confirmation).toContainText("No se registra ni solicita un pago");

  const reservationReconciled = page.waitForResponse((response) =>
    new URL(response.url()).pathname === `/api/reservations/${paidReservationId}` &&
    response.request().method() === "GET" &&
    response.status() === 200
  );
  const operationsReconciled = page.waitForResponse((response) =>
    new URL(response.url()).pathname === `/api/reservations/${paidReservationId}/operations-summary` &&
    response.status() === 200
  );
  const extensionResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith(`/api/reservations/${paidReservationId}/extend`) &&
    response.request().method() === "POST"
  );
  await confirmation.getByRole("button", { name: "Confirmar extensión" }).click();
  const result = await extensionResponse;
  expect(result.ok()).toBeTruthy();
  await Promise.all([reservationReconciled, operationsReconciled]);
  expect(extensionRequests).toHaveLength(1);
  expect(extensionRequests[0]).toMatchObject({
    new_checkout_date: extendedCheckoutDate,
    client_version: 4,
    pricing_mode: "current_rate",
    payment_action: "pending_balance"
  });
  expect(extensionRequests[0]).not.toHaveProperty("payment_link");
  expect(extensionRequests[0]).not.toHaveProperty("immediate_payment");
  expect(extensionRequests[0]).not.toHaveProperty("email");
  expect(Number(currentReservation.total_amount)).toBe(180000);
  expect(Number(currentReservation.amount_paid)).toBe(120000);
  expect(externalPaymentWrites).toEqual([]);
  expect(cashReadsAfterExtension).toEqual([]);
  await expect(drawer.getByText("Extensión aplicada. El saldo quedó pendiente de cobro.", { exact: true })).toBeVisible();
  await expect(drawer.getByTestId("reservation-drawer-load-error")).toHaveCount(0);
  await expect(drawer.getByTestId("reservation-drawer-operations-error")).toHaveCount(0);
  expect(reservationReadsAfterExtension).toBeGreaterThanOrEqual(2);
  expect(operationsReadsAfterExtension).toBeGreaterThanOrEqual(2);
  await expect(drawer.getByTestId("reservation-drawer-operational-total")).toContainText("180.000");
  await expect(drawer.getByTestId("drawer-balance-due")).toContainText("60.000");
});
