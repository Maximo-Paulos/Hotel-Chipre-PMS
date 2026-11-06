import { expect, test, type Page } from "@playwright/test";

import { completeStepUpPrompt, loginAsStepUpOwner } from "./support/step-up-owner";

// B1: ReservationDetailDrawer + global access (header search, "Reserva
// rápida", and the ?reserva=<id> deep link). Covers opening the drawer from
// three different entry points and verifies it shows the real state,
// guest, and financials of a reservation created in this test.

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

test("owner opens the reservation drawer from the dashboard, global search, and a deep link", async ({ page }, testInfo) => {
  await page.route("**/api/payment-surcharges", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: "[]"
  }));
  const suffix = Date.now().toString();
  const guestLastName = `DrawerQA-${suffix}`;
  const ownerSession = await loginAsStepUpOwner(page, "cash-business", testInfo.project.name);
  const lastTotpStep = ownerSession.lastTotpStep;
  // The dashboard lists real upcoming arrivals: check-in from today on, not
  // yet checked in, soonest first, five at most (upcomingOnly on
  // GET /api/reservations). So this reservation has to be a near arrival.
  // Tomorrow rather than today: earlier specs in the same run fill today's
  // two "Standard E2E" rooms, and it still sorts ahead of every later
  // fixture date. The room is left to auto-assignment, and the test cancels
  // the reservation at the end so reruns against a reused server
  // (E2E_REUSE_SERVER) don't pile up arrivals on that date.
  const localIsoDate = (offsetDays: number) => {
    const value = new Date();
    value.setDate(value.getDate() + offsetDays);
    const pad = (part: number) => String(part).padStart(2, "0");
    return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
  };
  const checkIn = localIsoDate(1);
  const checkOut = localIsoDate(3);

  // Cash and a manually verified in-person card/bank operation complete at
  // this collection point; gateway links are handled by their separate flow.
  // Cash requires an open register, so open one first (idempotent: another
  // spec may have already left this hotel's register open).
  const sessionsResponse = page.waitForResponse(
    (response) => response.url().includes("/api/cash-register/sessions") && response.request().method() === "GET"
  );
  await page.goto("/caja");
  await sessionsResponse;
  const openingForm = page.locator("form").filter({ hasText: "Saldo inicial" }).filter({ hasText: "Abrir caja" });
  const openButton = openingForm.getByRole("button", { name: "Abrir caja", exact: true });
  if (await openButton.isVisible().catch(() => false)) {
    const openResponse = page.waitForResponse(
      (response) => response.url().includes("/api/cash-register/sessions") && response.request().method() === "POST"
    );
    await openButton.click();
    await openResponse;
  }

  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();

  const form = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(form).toBeVisible();
  await form.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
  await form.getByPlaceholder("Nombre").fill("Huésped");
  await form.getByPlaceholder("Apellido").fill(guestLastName);
  await form.getByPlaceholder("Email").fill(`${guestLastName.toLowerCase()}@example.test`);
  await form.getByPlaceholder("Teléfono").fill(`11${Date.now().toString().slice(-8)}${Math.floor(Math.random() * 100).toString().padStart(2, "0")}`);
  await form.getByLabel("Tipo de documento").selectOption("DNI");
  await form.getByPlaceholder("Documento").fill(`DRAWER-${suffix}`);
  await form.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = form.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  const categoryValue = await categoryOption.getAttribute("value");
  await categorySelect.selectOption(categoryValue!);

  await form.getByLabel("Check-in", { exact: true }).fill(checkIn);
  await form.getByLabel("Check-out", { exact: true }).fill(checkOut);
  await expect(form.getByRole("button", { name: "Crear", exact: true })).toBeEnabled();

  const [createResponse] = await Promise.all([
    page.waitForResponse((res) => res.url().includes("/api/reservations/") && res.request().method() === "POST"),
    form.getByRole("button", { name: "Crear", exact: true }).click()
  ]);
  await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();
  const created = await createResponse.json();
  const reservationId: number = created.id;
  const confirmationCode: string = created.confirmation_code;
  expect(reservationId).toBeGreaterThan(0);
  let allowFinancialSummaryToRecover = false;
  let holdFinancialSummaryRefresh = false;
  let failPaymentQuoteResponses = 0;
  let signalPaymentSummaryRefreshStarted: (() => void) | null = null;
  let releasePaymentSummaryRefresh: (() => void) | null = null;
  let paymentSummaryRefreshStarted: Promise<void> = Promise.resolve();
  await page.route("**/api/payment-surcharges/quote", async (route) => {
    if (failPaymentQuoteResponses <= 0) {
      await route.continue();
      return;
    }
    failPaymentQuoteResponses -= 1;
    await route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({ detail: "No balance remains for a new payment quote" })
    });
  });
  await page.route(`**/api/payments/summary/${reservationId}`, async (route) => {
    if (holdFinancialSummaryRefresh) {
      signalPaymentSummaryRefreshStarted?.();
      await new Promise<void>((resolve) => {
        releasePaymentSummaryRefresh = resolve;
      });
      await route.continue();
      return;
    }
    if (allowFinancialSummaryToRecover) {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Temporary financial summary failure" })
    });
  });

  // 1) Open from the dashboard.
  await page.goto("/dashboard");
  await page.getByRole("button", { name: confirmationCode }).click();

  const drawer = page.getByRole("dialog", { name: confirmationCode });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByText("Pendiente", { exact: true })).toBeVisible();
  const financialSummaryError = drawer.getByTestId("reservation-drawer-financial-summary-error");
  await expect(financialSummaryError).toBeVisible();
  allowFinancialSummaryToRecover = true;
  const summaryRetryResponse = page.waitForResponse(
    (response) => response.url().includes(`/api/payments/summary/${reservationId}`) && response.status() === 200
  );
  await financialSummaryError.getByRole("button", { name: "Reintentar", exact: true }).click();
  await summaryRetryResponse;
  await expect(financialSummaryError).toHaveCount(0);
  // B6.2 pending-action titles can now also contain the guest's full name
  // (e.g. "Cobrar saldo pendiente a Huésped ..."), so scope this assertion to
  // the drawer's own guest-name field instead of a substring search over the
  // whole dialog.
  await expect(drawer.getByTestId("drawer-guest-name")).toHaveText(`Huésped ${guestLastName}`);
  await expect(drawer).toContainText(guestLastName);
  await expect(drawer.getByText("Sin acompañantes cargados.", { exact: true })).toBeVisible();
  const drawerPaymentMethod = drawer.getByLabel("Método de pago");
  await expect(drawerPaymentMethod.locator('option[value="mercado_pago"]')).toHaveCount(0);
  await drawerPaymentMethod.selectOption("credit_card");
  await expect(drawer.getByLabel("Cupón verificado del posnet")).toBeVisible();
  await drawerPaymentMethod.selectOption("cash");
  const balanceBeforePayment = await drawer.getByTestId("drawer-balance-due").innerText();
  expect(balanceBeforePayment).toMatch(/\d/);
  expect(balanceBeforePayment).not.toMatch(/^\D*0[.,]00\D*$/);

  // Cobrar seña en el momento, directly from the drawer.
  await drawer.getByLabel("Importe a cobrar").fill("100");
  const cashReceivedInput = drawer.getByTestId("reservation-drawer-cash-received");
  let cashPaymentRequestCount = 0;
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/payments" && request.method() === "POST") {
      cashPaymentRequestCount += 1;
    }
  });
  await cashReceivedInput.fill("99");
  await drawer.getByRole("button", { name: "Registrar cobro", exact: true }).click();
  await expect(
    drawer.getByRole("alert").filter({ hasText: "El efectivo entregado debe cubrir al menos" })
  ).toContainText("El efectivo entregado debe cubrir al menos");
  expect(cashPaymentRequestCount).toBe(0);
  await cashReceivedInput.fill("120");
  await expect(drawer.getByTestId("reservation-drawer-cash-received-change")).toContainText("20");
  const paymentRequest = page.waitForRequest((request) =>
    new URL(request.url()).pathname === "/api/payments" && request.method() === "POST"
  );
  const paymentResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/payments" && response.request().method() === "POST"
  );
  const postPaymentQuoteFailure = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/payment-surcharges/quote" &&
    response.request().method() === "POST" && response.status() === 409
  );
  // Hold the balance refresh after the committed payment. The first quote
  // failure belongs to the stale balance; a second failure after refresh
  // must remain actionable.
  paymentSummaryRefreshStarted = new Promise<void>((resolve) => {
    signalPaymentSummaryRefreshStarted = resolve;
  });
  holdFinancialSummaryRefresh = true;
  failPaymentQuoteResponses = 2;
  await drawer.getByRole("button", { name: "Registrar cobro", exact: true }).click();
  const [paymentRequestResult, paymentResponseResult, postPaymentQuoteFailureResult] = await Promise.all([
    paymentRequest,
    paymentResponse,
    postPaymentQuoteFailure
  ]);
  expect(paymentResponseResult.status()).toBe(201);
  expect(postPaymentQuoteFailureResult.status()).toBe(409);
  expect(paymentRequestResult.postDataJSON()).toMatchObject({
    payment_method: "cash",
    amount: 100,
    cash_received_amount: 120
  });
  expect(cashPaymentRequestCount).toBe(1);
  await expect(drawer.getByText("Pago registrado.", { exact: true })).toBeVisible();
  await paymentSummaryRefreshStarted;
  await expect(drawer.getByTestId("reservation-drawer-payment-quote-error")).toHaveCount(0);
  const refreshedPaymentQuoteFailure = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/payment-surcharges/quote" &&
    response.request().method() === "POST" && response.status() === 409
  );
  const paymentSummaryRetry = page.waitForResponse(
    (response) => response.url().includes(`/api/payments/summary/${reservationId}`) && response.status() === 200
  );
  holdFinancialSummaryRefresh = false;
  releasePaymentSummaryRefresh?.();
  await paymentSummaryRetry;
  await refreshedPaymentQuoteFailure;
  await expect(drawer.getByTestId("reservation-drawer-payment-quote-error")).toBeVisible();
  await drawer.getByTestId("reservation-drawer-payment-quote-retry").click();
  await expect(drawer.getByTestId("reservation-drawer-payment-quote-error")).toHaveCount(0);

  await page.getByRole("button", { name: "Cerrar detalle de reserva" }).click();
  await expect(drawer).not.toBeVisible();
  await expect(page).toHaveURL(/\/dashboard$/);

  // 2) Open from the global header search.
  await page.getByRole("searchbox", { name: "Buscar reserva" }).fill(guestLastName);
  const searchResult = page.getByTestId("reservation-search-results").getByRole("button", { name: new RegExp(confirmationCode) });
  await expect(searchResult).toBeVisible();
  await searchResult.click();

  await expect(drawer).toBeVisible();
  await expect(drawer).toContainText(confirmationCode);
  await expect(page).toHaveURL(new RegExp(`reserva=${reservationId}`));
  // The payment summary refetches after the mutation invalidates it, so
  // poll instead of reading innerText() once (which can race the refetch).
  await expect(drawer.getByTestId("drawer-balance-due")).not.toHaveText(balanceBeforePayment);
  // The reservation itself must also be refreshed before the drawer is
  // considered current; the payment changes its status from Pendiente to
  // Seña without a full page reload.
  await expect(drawer.getByText("Seña", { exact: true })).toBeVisible();

  const deepLinkUrl = page.url();
  await page.getByRole("button", { name: "Cerrar detalle de reserva" }).click();
  await expect(drawer).not.toBeVisible();

  // 3) Deep link: loading ?reserva=<id> directly opens the drawer.
  await page.goto(deepLinkUrl);
  await expect(drawer).toBeVisible();
  await expect(drawer).toContainText(confirmationCode);
  await expect(drawer.getByText("Seña", { exact: true })).toBeVisible();

  // Settle the remaining synthetic balance and verify the zero-balance quote
  // state does not stay in the disabled query's loading placeholder.
  const parseSpanishAmount = (value: string) => Number(
    value.replace(/[^\d,.-]/g, "").replace(/\./g, "").replace(",", ".")
  );
  const balanceText = await drawer.getByTestId("drawer-balance-due").innerText();
  const remainingBalance = parseSpanishAmount(balanceText);
  expect(remainingBalance).toBeGreaterThan(0);
  await drawer.getByLabel("Método de pago").selectOption("bank_transfer");
  await drawer.getByLabel(/Referencia de transferencia/i).fill(`QA-FULL-${suffix}`);
  const fullBalanceQuoteResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/payment-surcharges/quote" &&
    response.request().method() === "POST" && response.status() === 200
  );
  await drawer.getByLabel("Importe a cobrar").fill(remainingBalance.toFixed(2));
  await fullBalanceQuoteResponse;
  await expect(drawer.getByTestId("payment-backend-quote")).toBeVisible();
  const finalPaymentResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/payments" && response.request().method() === "POST"
  );
  const zeroBalanceSummaryResponse = page.waitForResponse((response) =>
    response.url().includes(`/api/payments/summary/${reservationId}`) &&
    response.request().method() === "GET" && response.status() === 200
  );
  await drawer.getByRole("button", { name: "Registrar cobro", exact: true }).click();
  const finalPaymentResult = await finalPaymentResponse;
  expect(finalPaymentResult.status()).toBe(201);
  expect(finalPaymentResult.request().postDataJSON()).toMatchObject({
    payment_method: "bank_transfer",
    amount: remainingBalance
  });
  await zeroBalanceSummaryResponse;
  await expect.poll(async () => parseSpanishAmount(await drawer.getByTestId("drawer-balance-due").innerText())).toBe(0);
  await expect(drawer.getByTestId("reservation-drawer-payment-quote-no-balance")).toContainText("No hay saldo pendiente para cotizar.");
  await expect(drawer.getByText("Consultando la cotización del cobro…", { exact: true })).toHaveCount(0);

  const nonzeroQuoteResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/payment-surcharges/quote" &&
    response.request().method() === "POST" && response.status() === 409
  );
  await drawer.getByLabel("Importe a cobrar").fill("1");
  await nonzeroQuoteResponse;
  await expect(drawer.getByTestId("reservation-drawer-payment-quote-no-balance")).toHaveCount(0);
  await expect(drawer.getByTestId("reservation-drawer-payment-quote-error")).toBeVisible();
  await expect(drawer.getByText("Consultando la cotización del cobro…", { exact: true })).toHaveCount(0);

  // Cleanup: free tomorrow's room and dashboard slot for the next run.
  await drawer.getByRole("button", { name: "Cancelar", exact: true }).click();
  await completeStepUpPrompt(page, lastTotpStep, ownerSession.auth.user.email);
  await expect(drawer.getByText("Reserva cancelada.", { exact: true })).toBeVisible();
});

test("an authenticated second context sees a committed payment through realtime events", async ({ page, browser }) => {
  test.skip(process.env.REALTIME_E2E !== "true", "Requires REALTIME_E2E=true and a realtime-capable preview");

  const suffix = Date.now().toString();
  const guestLastName = `RealtimeQA-${suffix}`;
  const salt = Number(suffix.slice(-4));
  const pastIsoDate = (daysAgo: number) => {
    const value = new Date();
    value.setDate(value.getDate() - daysAgo);
    const pad = (part: number) => String(part).padStart(2, "0");
    return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
  };

  await login(page);
  const sessionsResponse = page.waitForResponse(
    (response) => response.url().includes("/api/cash-register/sessions") && response.request().method() === "GET"
  );
  await page.goto("/caja");
  await sessionsResponse;
  const openingForm = page.locator("form").filter({ hasText: "Saldo inicial" }).filter({ hasText: "Abrir caja" });
  const openButton = openingForm.getByRole("button", { name: "Abrir caja", exact: true });
  if (await openButton.isVisible().catch(() => false)) {
    const openResponse = page.waitForResponse(
      (response) => response.url().includes("/api/cash-register/sessions") && response.request().method() === "POST"
    );
    await openButton.click();
    await openResponse;
  }

  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  const form = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await form.getByLabel("Check-in", { exact: true }).fill(pastIsoDate(5000 + salt));
  await form.getByLabel("Check-out", { exact: true }).fill(pastIsoDate(4998 + salt));
  await form.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
  await form.getByPlaceholder("Nombre").fill("Huésped");
  await form.getByPlaceholder("Apellido").fill(guestLastName);
  await form.getByPlaceholder("Email").fill(`${guestLastName.toLowerCase()}@example.test`);
  await form.getByPlaceholder("Teléfono").fill(`11${Date.now().toString().slice(-8)}${Math.floor(Math.random() * 100).toString().padStart(2, "0")}`);
  await form.getByLabel("Tipo de documento").selectOption("DNI");
  await form.getByPlaceholder("Documento").fill(`REALTIME-${suffix}`);
  await form.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = form.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await categorySelect.selectOption((await categoryOption.getAttribute("value"))!);
  const roomSelect = form.locator("label").filter({ hasText: "Habitación (opcional)" }).locator("select");
  const roomOption = roomSelect.locator("option").filter({ hasText: "101" });
  await expect(roomOption).toHaveCount(1);
  await roomSelect.selectOption((await roomOption.getAttribute("value"))!);
  const [createResponse] = await Promise.all([
    page.waitForResponse((response) => response.url().includes("/api/reservations/") && response.request().method() === "POST"),
    form.getByRole("button", { name: "Crear", exact: true }).click()
  ]);
  await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();
  const created = await createResponse.json();
  const reservationId: number = created.id;
  const confirmationCode: string = created.confirmation_code;

  await page.goto(`/dashboard?reserva=${reservationId}`);
  const firstDrawer = page.getByRole("dialog", { name: confirmationCode });
  await expect(firstDrawer).toBeVisible();
  const balanceBeforePayment = await firstDrawer.getByTestId("drawer-balance-due").innerText();

  const secondContext = await browser.newContext();
  const secondPage = await secondContext.newPage();
  try {
    await login(secondPage);
    await secondPage.goto(`/dashboard?reserva=${reservationId}`);
    const secondDrawer = secondPage.getByRole("dialog", { name: confirmationCode });
    await expect(secondDrawer).toBeVisible();
    await secondDrawer.getByLabel("Importe a cobrar").fill("100");
    await secondDrawer.getByRole("button", { name: "Registrar cobro", exact: true }).click();
    await expect(secondDrawer.getByText("Pago registrado.", { exact: true })).toBeVisible();

    // Different browser contexts do not share BroadcastChannel/localStorage;
    // this assertion therefore verifies the server event stream path.
    await expect(firstDrawer.getByTestId("drawer-balance-due")).not.toHaveText(balanceBeforePayment);
    await expect(firstDrawer.getByText("Seña", { exact: true })).toBeVisible();
  } finally {
    await secondContext.close();
  }
});
