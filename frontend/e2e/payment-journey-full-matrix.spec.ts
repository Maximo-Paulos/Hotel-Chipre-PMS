import { expect, test, type Page, type Response } from "@playwright/test";

import { completeStepUpPrompt, loginAsStepUpOwner } from "./support/step-up-owner";

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const localizedName = (spanish: string, english: string) =>
  new RegExp(`^(?:${escapeRegExp(spanish)}|${escapeRegExp(english)})$`, "i");
const localizedText = (spanish: string, english: string) =>
  new RegExp(`(?:${escapeRegExp(spanish)}|${escapeRegExp(english)})`, "i");

// Fase 4 (Fase master): full payments/balance journey, real backend, real UI.
// Standard E2E category prices at $100/night (see manager-reports-journey.spec.ts),
// so a deterministic 3-night reservation totals $300. The configured deposit
// policy is shared with other journeys, so payment assertions use the amount
// shown by the reservation instead of assuming a global policy value.
const owner = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

// Minimal valid 2x2 PNGs used as transfer-proof image uploads. Payment proofs
// are deduplicated by hotel + content sha256 (see submit_transfer_proof), so
// each test that submits a proof needs a visually distinct image or the
// second submission is rejected as "ya fue presentado" even across different
// reservations.
const TINY_PNG_BASE64_RED =
  "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8z8DAwMDAxMDAwMDAAAANHQEDasKb6QAAAABJRU5ErkJggg==";
const TINY_PNG_BASE64_BLUE =
  "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGNkYPjPwMDAxMDAwMDAAAALHwEDmIWXfgAAAABJRU5ErkJggg==";

const localIsoDate = (offsetDays: number) => {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
};

function parseMoney(text: string) {
  return Number(text.replace(/[^0-9,.-]/g, "").replace(/\./g, "").replace(",", "."));
}

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(owner.email);
  await page.locator('input[type="password"]').fill(owner.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

async function ensureCashSessionOpen(page: Page, currencyCode = "ARS") {
  const completedCashGetPaths = new Set<string>();
  const recordCashGetResponse = (response: Response) => {
    if (response.request().method() !== "GET") return;
    const url = new URL(response.url());
    if (url.pathname.startsWith("/api/cash-register/")) {
      completedCashGetPaths.add(`${url.pathname}${url.search}`);
    }
  };
  page.on("response", recordCashGetResponse);
  try {
    await page.goto("/caja");
    await expect.poll(() => [...completedCashGetPaths].some((path) => {
      const pathname = path.split("?", 1)[0];
      return pathname === "/api/cash-register/sessions";
    })).toBe(true);
    await expect.poll(() => completedCashGetPaths.has("/api/cash-register/close-reports/pending")).toBe(true);

    const openingForm = page
      .locator("form")
      .filter({ hasText: localizedText("Saldo inicial", "Opening balance") })
      .filter({ hasText: localizedText("Abrir caja", "Open cash register") });
    const currencySelect = openingForm
      .locator("label")
      .filter({ hasText: localizedText("Moneda", "Currency") })
      .locator("select");
    const latestReportPath = `/api/cash-register/close-reports/latest?currency=${encodeURIComponent(currencyCode)}`;
    await currencySelect.selectOption(currencyCode);
    await expect.poll(() => completedCashGetPaths.has(latestReportPath)).toBe(true);

    const openButton = openingForm.getByRole("button", { name: localizedName("Abrir caja", "Open cash register") });
    const alreadyOpenButton = openingForm.getByRole("button", {
      name: localizedName("Ya hay una caja abierta", "Cash register already open")
    });
    await expect.poll(async () => {
      if (await alreadyOpenButton.isVisible()) return "already-open";
      if (await openButton.isEnabled()) return "openable";
      return "loading";
    }).not.toBe("loading");
    if (await alreadyOpenButton.isVisible()) {
      await expect(alreadyOpenButton).toBeDisabled();
    } else {
      await expect(openButton).toBeEnabled();
      await openingForm.getByText(localizedName("Saldo inicial", "Opening balance")).locator("..").locator("input").fill("0");
      await openButton.click();
      await expect(page.getByText(localizedName("Caja abierta.", "Cash register opened."))).toBeVisible();
    }
  } finally {
    page.off("response", recordCashGetResponse);
  }
}

async function createReservation(page: Page, guestLastName: string, suffix: string, offsetIn: number, offsetOut: number) {
  await page.goto("/reservas");
  await page.getByRole("button", { name: /^(?:Crear reserva|Create reservation)$/i }).click();
  const reservationForm = page.locator("form").filter({ hasText: localizedText("Datos de la reserva", "Reservation details") });
  await expect(reservationForm).toBeVisible();

  await reservationForm
    .getByRole("button", { name: localizedName("¿No lo encontrás? Crear huésped nuevo", "Can't find them? Create a new guest") })
    .click();
  await reservationForm.getByPlaceholder(localizedName("Nombre", "First name")).fill("Huésped");
  await reservationForm.getByPlaceholder(localizedName("Apellido", "Last name")).fill(guestLastName);
  await reservationForm.getByPlaceholder(localizedName("Email", "Email")).fill(`qa.pay.${suffix}@example.test`);
  await reservationForm.getByPlaceholder(localizedName("Teléfono", "Phone")).fill(`11${Date.now().toString().slice(-8)}${Math.floor(Math.random() * 100).toString().padStart(2, "0")}`);
  await reservationForm.getByLabel(localizedName("Tipo de documento", "Document type")).selectOption("DNI");
  await reservationForm.getByPlaceholder(localizedName("Documento", "Document")).fill(`QA-PAY-${suffix}`);
  await reservationForm.getByRole("button", { name: localizedName("Crear Huésped y asignar ID", "Create guest and assign ID") }).click();
  await expect(page.getByText(localizedName("Huésped creado y asignado", "Guest created and assigned"))).toBeVisible();

  const categorySelect = reservationForm.locator("label").filter({ hasText: localizedText("Categoría", "Category") }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  await categorySelect.selectOption((await categoryOption.getAttribute("value"))!);
  await reservationForm.getByLabel(localizedName("Check-in", "Check-in")).fill(localIsoDate(offsetIn));
  await reservationForm.getByLabel(localizedName("Check-out", "Check-out")).fill(localIsoDate(offsetOut));

  const createButton = reservationForm.getByRole("button", { name: localizedName("Crear", "Create") });
  await expect(createButton).toBeEnabled();
  const createResponsePromise = page.waitForResponse((response) =>
    response.url().includes("/api/reservations/") && response.request().method() === "POST" && response.status() === 201
  );
  await createButton.click();
  const created = await createResponsePromise.then((response) => response.json()) as {
    id: number;
    confirmation_code: string;
  };
  await expect(page.getByText(localizedName("Reserva creada", "Reservation created"))).toBeVisible();

  const reservationTable = page.locator("table").filter({ hasText: localizedText("Código", "Code") });
  const reservationRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await expect(reservationRow).toHaveCount(1);
  return { reservationTable, reservationRow, reservationId: created.id, confirmationCode: created.confirmation_code };
}

async function openPaymentsPanel(row: ReturnType<Page["locator"]>, page: Page) {
  await row.getByRole("button", { name: localizedName("Editar", "Edit") }).click();
  const editModal = page.locator("div.fixed").filter({ hasText: localizedText("Pagos y balance", "Payments and balance") });
  const editForm = editModal.locator("form").filter({ hasText: localizedText("Pagos y balance", "Payments and balance") });
  await expect(editForm).toBeVisible();
  await expect(editForm.getByText(localizedName("Cargando resumen...", "Loading summary..."))).toHaveCount(0);
  return { editModal, editForm };
}

async function readStat(editForm: ReturnType<Page["locator"]>, label: RegExp) {
  const value = await editForm
    .locator("p.text-xs.text-slate-500", { hasText: label })
    .locator("xpath=following-sibling::p[1]")
    .innerText();
  return parseMoney(value);
}

// The first journey enters a synthetic step-up code. Disable persisted browser
// artifacts for this financial test file so failures cannot retain that code.
test.use({ trace: "off", screenshot: "off", video: "off" });
test.describe.configure({ mode: "serial" });

test("owner pays deposit in cash, blocks an overpayment, settles the rest by approved bank transfer with a different method", async ({
  page
}, testInfo) => {
  test.skip(process.env.REALTIME_E2E !== "true", "El recorrido verifica el ticket de colaboración con realtime activo.");
  const suffix = `${Date.now()}a`;
  const guestLastName = `QA-Pay-Mix ${suffix}`;

  const ownerSession = await loginAsStepUpOwner(page, "cash", testInfo.project.name);
  const lastTotpStep = ownerSession.lastTotpStep;
  await ensureCashSessionOpen(page);

  const { reservationTable, reservationRow } = await createReservation(page, guestLastName, suffix, 60, 63);
  const collaborationTicketResources: Array<{ resource_type?: unknown; resource_id?: unknown; stage: string }> = [];
  const collaborationSocketCloses: Array<{ stage: string }> = [];
  let collaborationSocketConnections = 0;
  let collaborationStage = "open editor";
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname === "/api/collaboration/tickets" && request.method() === "POST") {
      const payload = request.postDataJSON() as { resource_type?: unknown; resource_id?: unknown };
      collaborationTicketResources.push({ resource_type: payload.resource_type, resource_id: payload.resource_id, stage: collaborationStage });
    }
  });
  page.on("websocket", (socket) => {
    if (new URL(socket.url()).pathname !== "/api/collaboration/ws") return;
    collaborationSocketConnections += 1;
    socket.on("close", () => collaborationSocketCloses.push({ stage: collaborationStage }));
  });
  const { editModal, editForm } = await openPaymentsPanel(reservationRow, page);
  await expect.poll(() => collaborationTicketResources.length).toBeGreaterThan(0);
  // One mounted reservation editor needs one short-lived editing ticket. A
  // duplicate here repeats permission/resource SQL and opens a ghost socket.
  await page.waitForTimeout(250);
  expect(collaborationTicketResources, `ticket resources requested: ${JSON.stringify(collaborationTicketResources)}`).toHaveLength(1);

  const total = await readStat(editForm, localizedText("Total", "Total"));
  expect(total).toBe(300);
  const depositRequired = await readStat(editForm, localizedText("Seña requerida", "Deposit required"));
  expect(depositRequired).toBeGreaterThan(0);
  expect(depositRequired).toBeLessThan(total);
  const balanceAfterDeposit = Number((total - depositRequired).toFixed(2));

  // 1) Seña manual en efectivo.
  collaborationStage = "cash deposit";
  const cashReceivedInput = editForm.getByTestId("reservation-payment-cash-received");
  await expect(cashReceivedInput).toBeVisible();
  const cashTipToggle = editForm.getByTestId("reservation-payment-cash-received-tip-toggle");
  await expect(cashTipToggle).not.toBeChecked();
  const expectedCashTender = Number(await cashReceivedInput.getAttribute("placeholder"));
  expect(Number.isFinite(expectedCashTender)).toBe(true);
  await cashReceivedInput.fill((expectedCashTender + 25).toFixed(2));
  await expect(editForm.getByTestId("reservation-payment-cash-received-change")).toContainText("25");
  const cashDepositRequest = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname === "/api/payments" && request.method() === "POST";
  });
  await editForm.getByRole("button", { name: localizedText("Registrar Seña", "Register deposit") }).click();
  const cashDepositPayload = await cashDepositRequest.then((request) => request.postDataJSON()) as {
    cash_received_amount: number;
    cash_tip_amount?: number;
  };
  expect(cashDepositPayload.cash_received_amount).toBeCloseTo(expectedCashTender + 25, 2);
  expect(cashDepositPayload.cash_tip_amount).toBeUndefined();
  await expect(page.getByText(localizedName("Se registró la Seña", "Deposit registered"))).toBeVisible();
  await expect.poll(() => readStat(editForm, localizedText("Pagado", "Paid"))).toBe(depositRequired);
  await expect.poll(() => readStat(editForm, localizedText("Saldo", "Balance"))).toBe(balanceAfterDeposit);

  // 12) Intento de sobrepago: pedir más que el saldo pendiente debe rechazarse
  // client-side, sin llegar a cobrar nada de más.
  let overchargePaymentPosts = 0;
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/payments" && request.method() === "POST") {
      overchargePaymentPosts += 1;
    }
  });
  await editForm.getByLabel(/Monto del movimiento|Monto a cobrar|Cash movement amount|Amount to collect/i).fill("999999");
  await expect(editForm.getByTestId("payment-amount-balance-error")).toContainText(
    localizedText("Ingresá un importe positivo que no supere el saldo pendiente.", "Enter a positive amount that does not exceed the pending balance.")
  );
  await expect(editForm.getByRole("button", { name: localizedName("Cobro parcial", "Partial payment") })).toBeDisabled();
  await expect(page.getByText(localizedName("Ingresá un importe positivo que no supere el saldo pendiente.", "Enter a positive amount that does not exceed the pending balance."))).toBeVisible();
  expect(overchargePaymentPosts).toBe(0);
  expect(await readStat(editForm, localizedText("Pagado", "Paid"))).toBe(depositRequired);

  // 9) Saldo final con un método DISTINTO al de la seña: transferencia + comprobante.
  await editForm.locator("label").filter({ hasText: localizedText("Medio de pago", "Payment method") }).locator("select").selectOption("bank_transfer");
  await editForm.getByLabel(/Monto del movimiento|Monto a cobrar|Cash movement amount|Amount to collect/i).fill(balanceAfterDeposit.toFixed(2));
  await editForm.getByLabel(localizedName("Imagen del comprobante", "Proof image")).setInputFiles({
    name: "comprobante.png",
    mimeType: "image/png",
    buffer: Buffer.from(TINY_PNG_BASE64_RED, "base64")
  });
  collaborationStage = "submit transfer proof";
  await editForm.getByRole("button", { name: localizedName("Enviar comprobante", "Send proof") }).click();
  await expect(page.getByText(localizedName("Comprobante enviado para aprobación", "Proof sent for approval"))).toBeVisible();
  // Bank transfer does not touch the balance until approved.
  expect(await readStat(editForm, localizedText("Pagado", "Paid"))).toBe(depositRequired);
  await expect(editForm.getByText(localizedText("· pendiente", "· pending"))).toBeVisible();

  // 4) Aprobación del comprobante -> ahora sí se aplica al saldo, con el método
  // distinto al de la seña (transferencia vs. la seña en efectivo).
  collaborationStage = "approve transfer proof";
  await editForm.getByRole("button", { name: localizedName("Aprobar", "Approve") }).click();
  await expect(page.getByText(localizedName("Comprobante aprobado", "Proof approved"))).toBeVisible();
  await expect.poll(() => readStat(editForm, localizedText("Pagado", "Paid"))).toBe(300);
  await expect.poll(() => readStat(editForm, localizedText("Saldo", "Balance"))).toBe(0);
  await expect(editForm.getByText(localizedText("Aprobado", "Approved"))).toBeVisible();

  // 10) Reembolso: devolución parcial en efectivo sobre lo cobrado.
  await editForm.locator("label").filter({ hasText: localizedText("Medio de pago", "Payment method") }).locator("select").selectOption("cash");
  await editForm.getByLabel(/Monto del movimiento|Monto a cobrar|Cash movement amount|Amount to collect/i).fill("50");
  await editForm.getByLabel(localizedName("Motivo de la devolución", "Refund reason")).fill("Ajuste de prueba E2E");
  page.once("dialog", (dialog) => dialog.accept());
  collaborationStage = "refund";
  await editForm.getByRole("button", { name: localizedName("Registrar devolución", "Register refund") }).click();
  await completeStepUpPrompt(page, lastTotpStep, ownerSession.auth.user.email);
  await expect(page.getByText(localizedName("Devolución registrada", "Refund registered"))).toBeVisible();
  await expect.poll(() => readStat(editForm, localizedText("Pagado", "Paid"))).toBe(250);
  await expect.poll(() => readStat(editForm, localizedText("Saldo", "Balance"))).toBe(50);

  // Refund beyond what was actually paid must be rejected client-side too, never
  // leaving a negative balance/paid amount.
  await editForm.getByLabel(/Monto del movimiento|Monto a cobrar|Cash movement amount|Amount to collect/i).fill("999999");
  await editForm.getByLabel(localizedName("Motivo de la devolución", "Refund reason")).fill("Intento de sobre-devolución E2E");
  await editForm.getByRole("button", { name: localizedName("Registrar devolución", "Register refund") }).click();
  await expect(page.getByText(localizedName("Ingresá un importe positivo que no supere el total pagado.", "Enter a positive amount that does not exceed the total paid."))).toBeVisible();
  expect(await readStat(editForm, localizedText("Pagado", "Paid"))).toBe(250);

  expect(
    collaborationTicketResources,
    `an open editor should not reissue tickets during unrelated payment actions; tickets: ${JSON.stringify(collaborationTicketResources)}; socket closes: ${JSON.stringify(collaborationSocketCloses)}`
  ).toHaveLength(1);
  expect(
    collaborationSocketConnections,
    `an open editor should retain one collaboration socket; socket closes: ${JSON.stringify(collaborationSocketCloses)}`
  ).toBe(1);
  await editModal.getByRole("button", { name: localizedName("Cerrar", "Close") }).click();
  void reservationTable;
});

test("owner registers the entered deposit amount with confirmation and keeps the deposit transaction type", async ({ page }) => {
  const suffix = `${Date.now()}deposit`;
  const guestLastName = `QA-Pay-Deposit-Amount ${suffix}`;

  await login(page);
  await ensureCashSessionOpen(page);
  const { reservationRow } = await createReservation(page, guestLastName, suffix, 68, 71);
  const { editForm } = await openPaymentsPanel(reservationRow, page);
  const total = await readStat(editForm, localizedText("Total", "Total"));
  expect(total).toBe(300);
  const depositRequired = await readStat(editForm, localizedText("Seña requerida", "Deposit required"));
  expect(depositRequired).toBeGreaterThan(2);
  const enteredDeposit = Math.min(51, Math.floor(depositRequired / 2));
  const remainingDeposit = Number((depositRequired - enteredDeposit).toFixed(2));
  const remainingBalance = Number((total - depositRequired).toFixed(2));

  const amountInput = editForm.getByLabel(/Monto del movimiento|Monto a cobrar|Cash movement amount|Amount to collect/i);
  const depositButton = editForm.getByRole("button", { name: localizedText("Registrar Seña", "Register deposit") });
  await expect.poll(async () => parseMoney(await depositButton.innerText())).toBe(depositRequired);
  await amountInput.fill(String(enteredDeposit));
  await expect.poll(async () => parseMoney(await depositButton.innerText())).toBe(enteredDeposit);

  const paymentRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname === "/api/payments" && request.method() === "POST") {
      paymentRequests.push(request.url());
    }
  });
  let confirmationMessage = "";
  page.once("dialog", async (dialog) => {
    confirmationMessage = dialog.message();
    await dialog.accept();
  });
  const manualDepositRequest = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname === "/api/payments" && request.method() === "POST";
  });
  await depositButton.click();
  const manualDepositPayload = manualDepositRequest.then((request) => request.postDataJSON()) as Promise<{
    amount: number;
    transaction_type: string;
  }>;
  const registeredDeposit = await manualDepositPayload;
  expect(registeredDeposit.amount).toBe(enteredDeposit);
  expect(registeredDeposit.transaction_type).toBe("deposit");
  const confirmedAmounts = [...confirmationMessage.matchAll(/\d[\d.,]*/g)].map(([value]) => parseMoney(value));
  expect(confirmedAmounts).toContain(depositRequired);
  expect(confirmedAmounts).toContain(enteredDeposit);
  await expect(page.getByText(localizedName("Se registró la Seña", "Deposit registered"))).toBeVisible();
  await expect.poll(() => readStat(editForm, localizedText("Pagado", "Paid"))).toBe(enteredDeposit);
  await expect.poll(() => readStat(editForm, localizedText("Saldo", "Balance"))).toBe(Number((total - enteredDeposit).toFixed(2)));

  // An amount above the remaining balance is rejected before any payment request.
  await amountInput.fill("999999");
  await expect(editForm.getByTestId("payment-amount-balance-error")).toContainText(
    localizedText("Ingresá un importe positivo que no supere el saldo pendiente.", "Enter a positive amount that does not exceed the pending balance.")
  );
  await expect(depositButton).toBeDisabled();
  await expect(editForm.getByRole("button", { name: localizedName("Cobro parcial", "Partial payment") })).toBeDisabled();
  expect(paymentRequests).toHaveLength(1);
  expect(await readStat(editForm, localizedText("Pagado", "Paid"))).toBe(enteredDeposit);

  // Declining the confirmation must also leave the ledger untouched.
  await amountInput.fill("20");
  page.once("dialog", async (dialog) => dialog.dismiss());
  await depositButton.click();
  expect(paymentRequests).toHaveLength(1);
  expect(await readStat(editForm, localizedText("Pagado", "Paid"))).toBe(enteredDeposit);

  // Clearing the field uses the remaining configured deposit amount by default.
  await amountInput.fill("");
  const remainingDepositRequest = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname === "/api/payments" && request.method() === "POST";
  });
  await depositButton.click();
  const defaultDeposit = await remainingDepositRequest.then((request) => request.postDataJSON()) as {
    amount: number;
    transaction_type: string;
  };
  expect(defaultDeposit.amount).toBeCloseTo(remainingDeposit, 2);
  expect(defaultDeposit.transaction_type).toBe("deposit");
  await expect(page.getByText(localizedName("Se registró la Seña", "Deposit registered"))).toBeVisible();
  await expect.poll(() => readStat(editForm, localizedText("Pagado", "Paid"))).toBe(depositRequired);
  await expect.poll(() => readStat(editForm, localizedText("Saldo", "Balance"))).toBe(remainingBalance);
});

test("cross-currency payment quotes received tender into the reservation currency", async ({ page }) => {
  const suffix = `${Date.now()}fx`;
  const guestLastName = `QA-Pay-FX ${suffix}`;

  await login(page);
  await ensureCashSessionOpen(page, "USD");
  const { reservationRow } = await createReservation(page, guestLastName, suffix, 72, 75);
  const { editForm } = await openPaymentsPanel(reservationRow, page);
  await editForm.locator("label").filter({ hasText: localizedText("Medio de pago", "Payment method") }).locator("select").selectOption("cash");
  const currencySelect = editForm.getByTestId("payment-tender-currency");
  await expect(currencySelect.locator('option[value="USD"]')).toBeAttached();
  const amountInput = editForm.getByLabel(/Monto del movimiento|Monto a cobrar|Cash movement amount|Amount to collect/i);
  await amountInput.fill("1000");
  const balanceQuoteResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    if (url.pathname !== "/api/payment-surcharges/quote" || response.request().method() !== "POST" || response.status() !== 200) {
      return false;
    }
    const payload = response.request().postDataJSON() as { currency_code?: string; base_amount?: number | null };
    return payload.currency_code === "USD" && payload.base_amount == null;
  });
  await currencySelect.selectOption("USD");

  const balanceQuoteResponse = await balanceQuoteResponsePromise;
  const balanceQuote = await balanceQuoteResponse.json() as {
    applied_amount: number | string;
    base_amount: number | string;
    currency_code: string;
    final_amount: number | string;
    fx_quote_details: { fallback_used?: boolean; provider?: string } | null;
    fx_rate_snapshot: number | string | null;
    remaining_balance: number | string;
    reservation_currency_code: string;
  };
  const quotePanel = editForm.getByTestId("payment-backend-quote");
  await expect(quotePanel).toBeVisible();
  await expect(quotePanel).toContainText("Cotización confirmada por el servidor");
  await expect(quotePanel).toContainText(/Tipo fijado: 1 USD = [\d.,]+ ARS/);
  const expectedCurrencyAmount = (amount: number | string, currencyCode: string) =>
    new Intl.NumberFormat("es-AR", { style: "currency", currency: currencyCode }).format(Number(amount));
  const quoteRows = quotePanel.locator("dl");
  await expect(quoteRows.locator("dt").filter({ hasText: localizedName("Total a recibir en USD", "Total to receive in USD") }).locator("xpath=following-sibling::dd[1]")).toHaveText(
    expectedCurrencyAmount(balanceQuote.final_amount, "USD")
  );
  await expect(quoteRows.locator("dt").filter({ hasText: localizedName("Aplicado a la reserva", "Applied to reservation") }).locator("xpath=following-sibling::dd[1]")).toHaveText(
    expectedCurrencyAmount(balanceQuote.applied_amount, "ARS")
  );
  await expect(quoteRows.locator("dt").filter({ hasText: localizedName("Saldo restante", "Remaining balance") }).locator("xpath=following-sibling::dd[1]")).toHaveText(
    expectedCurrencyAmount(balanceQuote.remaining_balance, "ARS")
  );
  if (Number(balanceQuote.remaining_balance) > 0) {
    await expect(quotePanel.getByTestId("payment-quote-minor-unit-remainder")).toContainText(
      localizedText(
        "La conversión respeta los centavos de la moneda de cobro",
        "The conversion respects the tender currency's minor units"
      )
    );
  }
  await expect(editForm.getByTestId("payment-currency-hint")).toContainText("cotización");
  await expect(amountInput).toBeEditable();
  await expect(amountInput).toHaveValue(Number(balanceQuote.base_amount).toFixed(2));
  expect(balanceQuote).toMatchObject({ currency_code: "USD", reservation_currency_code: "ARS" });
  expect(Number(balanceQuote.base_amount)).toBeGreaterThan(0);
  expect(Number(balanceQuote.fx_rate_snapshot)).toBeGreaterThan(0);
  expect(balanceQuote.fx_quote_details?.provider).toBe("dolarapi.com");
  expect(balanceQuote.fx_quote_details?.fallback_used).toBe(false);

  const partialTenderAmount = Math.max(
    0.01,
    Math.floor(Number(balanceQuote.base_amount) * 100 / 2) / 100
  );
  const partialQuoteResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    if (url.pathname !== "/api/payment-surcharges/quote" || response.request().method() !== "POST" || response.status() !== 200) {
      return false;
    }
    const payload = response.request().postDataJSON() as { currency_code?: string; base_amount?: number };
    return payload.currency_code === "USD" && Number(payload.base_amount) === partialTenderAmount;
  });
  await amountInput.fill(partialTenderAmount.toFixed(2));
  const partialQuoteResponse = await partialQuoteResponsePromise;
  const partialQuote = await partialQuoteResponse.json() as {
    applied_amount: number | string;
    base_amount: number | string;
    fx_rate_snapshot: number | string;
    remaining_balance: number | string;
  };
  expect(Number(partialQuote.base_amount)).toBe(partialTenderAmount);
  expect(Number(partialQuote.applied_amount)).toBeCloseTo(
    partialTenderAmount / Number(partialQuote.fx_rate_snapshot),
    2
  );
  await expect(quoteRows.locator("dt").filter({ hasText: localizedName("Aplicado a la reserva", "Applied to reservation") }).locator("xpath=following-sibling::dd[1]")).toHaveText(
    expectedCurrencyAmount(partialQuote.applied_amount, "ARS")
  );
  await expect(quoteRows.locator("dt").filter({ hasText: localizedName("Saldo restante", "Remaining balance") }).locator("xpath=following-sibling::dd[1]")).toHaveText(
    expectedCurrencyAmount(partialQuote.remaining_balance, "ARS")
  );
  expect(Number(partialQuote.remaining_balance)).toBeGreaterThan(0);
  await expect(quotePanel.getByTestId("payment-quote-minor-unit-remainder")).toContainText(
    localizedText(
      "La conversión se limita a los centavos disponibles en la moneda de cobro",
      "The conversion is limited to the tender currency's minor units"
    )
  );

  const paymentResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/payments" && response.request().method() === "POST";
  });
  const summaryResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname.startsWith("/api/payments/summary/") && response.request().method() === "GET" && response.status() === 200;
  });
  const paymentRequest = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname === "/api/payments" && request.method() === "POST";
  });
  await editForm.getByRole("button", { name: localizedName("Pago total", "Full payment") }).click();
  const submittedRequest = await paymentRequest;
  const paymentResponse = await paymentResponsePromise;
  expect(paymentResponse.status()).toBe(201);
  const summaryResponse = await summaryResponsePromise;
  const summary = await summaryResponse.json() as {
    amount_paid: number | string;
    balance_due: number | string;
  };
  expect(Number(summary.amount_paid)).toBe(Number(balanceQuote.applied_amount));
  expect(Number(summary.balance_due)).toBe(Number(balanceQuote.remaining_balance));

  expect(submittedRequest.postDataJSON()).toMatchObject({
    amount: Number(balanceQuote.base_amount),
    currency: "USD",
    transaction_type: Number(balanceQuote.remaining_balance) > 0.01 ? "partial_payment" : "full_payment"
  });
});

test("reservation detail drawer quotes and records an editable USD cash payment with ARS change", async ({ page }) => {
  const suffix = `${Date.now()}drawerfx`;
  const guestLastName = `QA-Pay-Drawer-FX ${suffix}`;

  await login(page);
  await ensureCashSessionOpen(page, "ARS");
  await ensureCashSessionOpen(page, "USD");
  const { reservationId, confirmationCode } = await createReservation(page, guestLastName, suffix, 80, 83);
  await page.goto(`/dashboard?reserva=${reservationId}`);

  const drawer = page.getByRole("dialog", { name: confirmationCode });
  await expect(drawer).toBeVisible();
  const currencySelect = drawer.getByTestId("reservation-drawer-payment-currency");
  await expect(currencySelect).toBeVisible();
  await expect(currencySelect).toHaveValue("ARS");
  await expect(currencySelect.locator('option[value="USD"]')).toBeAttached();

  const balanceQuoteResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    if (url.pathname !== "/api/payment-surcharges/quote" || response.request().method() !== "POST" || response.status() !== 200) {
      return false;
    }
    const payload = response.request().postDataJSON() as { currency_code?: string; base_amount?: number | null };
    return payload.currency_code === "USD" && payload.base_amount == null;
  });
  await currencySelect.selectOption("USD");
  const balanceQuote = await balanceQuoteResponsePromise.then((response) => response.json()) as {
    base_amount: number | string;
    cash_change_currency_code: string;
    cash_change_fx_rate: number | string | null;
    final_amount: number | string;
  };
  expect(balanceQuote.cash_change_currency_code).toBe("ARS");
  expect(Number(balanceQuote.cash_change_fx_rate)).toBeGreaterThan(0);
  await expect(drawer.getByTestId("payment-quote-fx-rate")).toContainText(/1 USD = [\d.,]+ ARS/);
  await expect(drawer.getByTestId("reservation-drawer-payment-currency-hint")).toContainText("cotización");
  const amountInput = drawer.getByLabel(/Importe a cobrar \(USD\)|Amount to collect \(USD\)/);
  await expect(amountInput).toBeEditable();
  await expect(amountInput).toHaveValue(Number(balanceQuote.base_amount).toFixed(2));

  const partialTenderAmount = Math.max(0.01, Math.floor(Number(balanceQuote.base_amount) * 100 / 2) / 100);
  const partialQuoteResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    if (url.pathname !== "/api/payment-surcharges/quote" || response.request().method() !== "POST" || response.status() !== 200) {
      return false;
    }
    const payload = response.request().postDataJSON() as { currency_code?: string; base_amount?: number | null };
    return payload.currency_code === "USD" && Number(payload.base_amount) === partialTenderAmount;
  });
  await amountInput.fill(partialTenderAmount.toFixed(2));
  const partialQuote = await partialQuoteResponsePromise.then((response) => response.json()) as {
    final_amount: number | string;
    cash_change_currency_code: string;
    cash_change_fx_rate: number | string | null;
  };
  const receivedAmount = Number((Number(partialQuote.final_amount) + 5).toFixed(2));
  const expectedChange = Math.round((
    (receivedAmount - Number(partialQuote.final_amount)) * Number(partialQuote.cash_change_fx_rate) + Number.EPSILON
  ) * 100) / 100;
  const cashReceivedInput = drawer.getByTestId("reservation-drawer-cash-received");
  await cashReceivedInput.fill(receivedAmount.toFixed(2));
  const changeDisplay = drawer.getByTestId("reservation-drawer-cash-received-change");
  await expect(changeDisplay).toContainText("ARS");
  await expect(changeDisplay).toContainText(expectedChange.toLocaleString("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }));

  const paymentRequestPromise = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname === "/api/payments" && request.method() === "POST";
  });
  const paymentResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/payments" && response.request().method() === "POST";
  });
  await drawer.getByRole("button", { name: localizedName("Registrar cobro", "Register payment") }).click();
  const [paymentRequest, paymentResponse] = await Promise.all([paymentRequestPromise, paymentResponsePromise]);
  expect(paymentResponse.status()).toBe(201);
  expect(paymentRequest.postDataJSON()).toMatchObject({
    amount: partialTenderAmount,
    currency: "USD",
    cash_received_amount: receivedAmount
  });
  const transaction = await paymentResponse.json() as {
    cash_change_settled_amount: number | string;
    cash_change_settled_currency: string;
  };
  expect(transaction.cash_change_settled_currency).toBe("ARS");
  expect(Number(transaction.cash_change_settled_amount)).toBe(expectedChange);
  await expect(drawer.getByText(localizedName("Pago registrado.", "Payment registered."))).toBeVisible();
});

test("cross-currency cash change is calculated in hotel currency and posted to both cash drawers", async ({ page }) => {
  const suffix = `${Date.now()}fxchange`;
  const guestLastName = `QA-Pay-FX-Change ${suffix}`;

  await login(page);
  await ensureCashSessionOpen(page, "ARS");
  await ensureCashSessionOpen(page, "USD");
  const { reservationRow } = await createReservation(page, guestLastName, suffix, 76, 77);
  const { editForm } = await openPaymentsPanel(reservationRow, page);
  await editForm.locator("label")
    .filter({ hasText: localizedText("Medio de pago", "Payment method") })
    .locator("select")
    .selectOption("cash");

  const quoteResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    if (url.pathname !== "/api/payment-surcharges/quote" || response.request().method() !== "POST" || response.status() !== 200) {
      return false;
    }
    const payload = response.request().postDataJSON() as { currency_code?: string; base_amount?: number | null };
    return payload.currency_code === "USD" && payload.base_amount == null;
  });
  await editForm.getByTestId("payment-tender-currency").selectOption("USD");
  const quoteResponse = await quoteResponsePromise;
  const quote = await quoteResponse.json() as {
    final_amount: number | string;
    cash_change_currency_code: string;
    cash_change_fx_rate: number | string | null;
  };
  expect(quote.cash_change_currency_code).toBe("ARS");
  expect(Number(quote.cash_change_fx_rate)).toBeGreaterThan(0);
  await expect(editForm.getByTestId("payment-quote-cash-change-rate")).toContainText(/1 USD = [\d.,]+ ARS/);

  const receivedAmount = Number(quote.final_amount) + 10;
  const expectedChange = Math.round((10 * Number(quote.cash_change_fx_rate) + Number.EPSILON) * 100) / 100;
  const cashReceivedInput = editForm.getByTestId("reservation-payment-cash-received");
  await cashReceivedInput.fill(receivedAmount.toFixed(2));
  const changeDisplay = editForm.getByTestId("reservation-payment-cash-received-change");
  await expect(changeDisplay).toContainText("ARS");
  await expect(changeDisplay).toContainText(expectedChange.toLocaleString("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }));

  const paymentResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/payments" && response.request().method() === "POST";
  });
  const paymentRequestPromise = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname === "/api/payments" && request.method() === "POST";
  });
  await editForm.getByRole("button", { name: localizedName("Pago total", "Full payment") }).click();
  const paymentRequest = await paymentRequestPromise;
  const paymentResponse = await paymentResponsePromise;
  expect(paymentResponse.status()).toBe(201);
  const paymentRequestHeaders = await paymentRequest.allHeaders();
  const authenticatedApiHeaders = {
    Authorization: paymentRequestHeaders.authorization ?? "",
    "X-Hotel-Id": paymentRequestHeaders["x-hotel-id"] ?? "",
    "X-User-Id": paymentRequestHeaders["x-user-id"] ?? "",
    "X-CSRF-Token": paymentRequestHeaders["x-csrf-token"] ?? ""
  };
  expect(authenticatedApiHeaders.Authorization).toMatch(/^Bearer\s+\S+/);
  expect(authenticatedApiHeaders["X-Hotel-Id"]).not.toBe("");
  expect(authenticatedApiHeaders["X-User-Id"]).not.toBe("");
  const transaction = await paymentResponse.json() as {
    id: number;
    cash_change_settled_amount: number | string;
    cash_change_settled_currency: string;
    cash_change_fx_rate_snapshot: number | string;
  };
  expect(transaction.cash_change_settled_currency).toBe("ARS");
  expect(Number(transaction.cash_change_settled_amount)).toBe(expectedChange);
  expect(Number(transaction.cash_change_fx_rate_snapshot)).toBe(Number(quote.cash_change_fx_rate));

  const sessionsResponse = await page.request.get("/api/cash-register/sessions?status=open", {
    headers: authenticatedApiHeaders
  });
  expect(sessionsResponse.status()).toBe(200);
  const sessions = await sessionsResponse.json() as Array<{ id: number; currency_code: string }>;
  const usdSession = sessions.find((session) => session.currency_code === "USD");
  const arsSession = sessions.find((session) => session.currency_code === "ARS");
  expect(usdSession).toBeTruthy();
  expect(arsSession).toBeTruthy();
  const [usdMovementsResponse, arsMovementsResponse] = await Promise.all([
    page.request.get(`/api/cash-register/sessions/${usdSession?.id}/movements`, { headers: authenticatedApiHeaders }),
    page.request.get(`/api/cash-register/sessions/${arsSession?.id}/movements`, { headers: authenticatedApiHeaders })
  ]);
  const usdMovements = await usdMovementsResponse.json() as Array<{
    transaction_id: number | null;
    movement_type: string;
    amount: number | string;
    cash_received_amount?: number | string | null;
    cash_change_settled_amount?: number | string | null;
    cash_change_settled_currency?: string | null;
  }>;
  const arsMovements = await arsMovementsResponse.json() as Array<{
    transaction_id: number | null;
    movement_type: string;
    amount: number | string;
  }>;
  const usdIncomeMovement = usdMovements.find((movement) => movement.transaction_id === transaction.id);
  expect(usdIncomeMovement).toBeTruthy();
  expect(usdIncomeMovement?.movement_type).toBe("income");
  expect(Number(usdIncomeMovement?.amount)).toBe(receivedAmount);
  expect(Number(usdIncomeMovement?.cash_received_amount)).toBe(receivedAmount);
  expect(Number(usdIncomeMovement?.cash_change_settled_amount)).toBe(expectedChange);
  expect(usdIncomeMovement?.cash_change_settled_currency).toBe("ARS");

  const arsChangeMovement = arsMovements.find((movement) => movement.transaction_id === transaction.id);
  expect(arsChangeMovement).toBeTruthy();
  expect(arsChangeMovement?.movement_type).toBe("expense");
  expect(Number(arsChangeMovement?.amount)).toBe(expectedChange);

  const businessDate = localIsoDate(0);
  const dailySummaryResponse = await page.request.get(
    `/api/cash-register/daily-summary?date=${businessDate}&currency=USD`,
    { headers: authenticatedApiHeaders }
  );
  expect(dailySummaryResponse.status()).toBe(200);
  const dailySummary = await dailySummaryResponse.json() as {
    entries: Array<{
      transaction_id?: number | null;
      cash_change_settled_amount?: number | string | null;
      cash_change_settled_currency?: string | null;
    }>;
  };
  const dailyPaymentEntry = dailySummary.entries.find((entry) => entry.transaction_id === transaction.id);
  expect(dailyPaymentEntry).toBeTruthy();
  expect(Number(dailyPaymentEntry?.cash_change_settled_amount)).toBe(expectedChange);
  expect(dailyPaymentEntry?.cash_change_settled_currency).toBe("ARS");

  const csvResponse = await page.request.get(
    `/api/cash-register/export.csv?date=${businessDate}&currency=USD`,
    { headers: authenticatedApiHeaders }
  );
  expect(csvResponse.status()).toBe(200);
  const cashCsv = await csvResponse.text();
  expect(cashCsv).toContain("vuelto_monto_real");
  expect(cashCsv).toContain("moneda_vuelto");
  expect(cashCsv.split(/\r?\n/).some((line) =>
    line.includes(String(transaction.id)) &&
    line.includes("ARS") &&
    line.includes(expectedChange.toFixed(2).replace(".", ","))
  )).toBe(true);

  const correctionResponse = await page.request.post(
    `/api/payments/transactions/${transaction.id}/correction`,
    {
      data: {
        correction_type: "duplicate_reversal",
        reason: "Regresión sintética de vuelto en moneda base"
      },
      headers: {
        ...authenticatedApiHeaders,
        "Idempotency-Key": `fx-change-correction-${suffix}`
      }
    }
  );
  expect(correctionResponse.status()).toBe(201);
  const correction = await correctionResponse.json() as { correction_id: number };
  const [reversedUsdResponse, reversedArsResponse] = await Promise.all([
    page.request.get(`/api/cash-register/sessions/${usdSession?.id}/movements`, { headers: authenticatedApiHeaders }),
    page.request.get(`/api/cash-register/sessions/${arsSession?.id}/movements`, { headers: authenticatedApiHeaders })
  ]);
  const reversedUsdMovements = await reversedUsdResponse.json() as Array<{
    transaction_id: number | null;
    voided_by_payment_correction_id?: number | null;
  }>;
  const reversedArsMovements = await reversedArsResponse.json() as Array<{
    transaction_id: number | null;
    voided_by_payment_correction_id?: number | null;
  }>;
  expect(reversedUsdMovements.find((movement) => movement.transaction_id === transaction.id)
    ?.voided_by_payment_correction_id).toBe(correction.correction_id);
  expect(reversedArsMovements.find((movement) => movement.transaction_id === transaction.id)
    ?.voided_by_payment_correction_id).toBe(correction.correction_id);
});

test("cross-currency payment offers reservation-currency fallback when no current quote is available", async ({ page }) => {
  const suffix = `${Date.now()}fxfallback`;
  const guestLastName = `QA-Pay-FX-Fallback ${suffix}`;
  const quoteRequests: Array<{ currency_code?: string }> = [];

  await page.route("**/api/payment-surcharges/quote", async (route) => {
    const payload = route.request().postDataJSON() as { currency_code?: string };
    if (payload.currency_code !== "USD") {
      await route.continue();
      return;
    }
    quoteRequests.push(payload);
    await route.fulfill({
      status: 422,
      contentType: "application/json",
      json: {
        detail: "No hay cotización actual ni un respaldo de menos de 24 horas para USD. La conversión automática está bloqueada."
      }
    });
  });

  await login(page);
  await ensureCashSessionOpen(page, "ARS");
  const { reservationRow } = await createReservation(page, guestLastName, suffix, 76, 78);
  const { editForm } = await openPaymentsPanel(reservationRow, page);
  const currencySelect = editForm.getByTestId("payment-tender-currency");
  await currencySelect.selectOption("USD");

  const quoteError = editForm.getByTestId("payment-quote-error");
  await expect(quoteError).toBeVisible();
  await expect(quoteError).toContainText("No se pudo confirmar la cotización del cobro");
  expect(quoteRequests.some((payload) => payload.currency_code === "USD")).toBe(true);

  const amountInput = editForm.getByLabel(/Monto del movimiento|Monto a cobrar|Cash movement amount|Amount to collect/i);
  await amountInput.fill("10");
  await quoteError.getByTestId("payment-fx-switch-to-reservation-currency").click();

  await expect(currencySelect).toHaveValue("ARS");
  await expect(amountInput).toHaveValue("");
  await expect(quoteError).toHaveCount(0);
  await expect(editForm.getByText("Abrí una caja en ARS para registrar ese efectivo y poder arquearlo en su moneda.")).toHaveCount(0);
});

test("owner rejects a transfer proof with a reason and the proof cannot be approved afterwards", async ({ page }) => {
  const suffix = `${Date.now()}b`;
  const guestLastName = `QA-Pay-Reject ${suffix}`;

  await login(page);
  const { reservationRow } = await createReservation(page, guestLastName, suffix, 64, 66);
  const { editModal, editForm } = await openPaymentsPanel(reservationRow, page);

  await editForm.locator("label").filter({ hasText: localizedText("Medio de pago", "Payment method") }).locator("select").selectOption("bank_transfer");
  await editForm.getByLabel(/^(?:Monto a cobrar|Amount to collect) \([A-Z]{3}\)$/i).fill("60");
  await editForm.getByLabel(localizedName("Imagen del comprobante", "Proof image")).setInputFiles({
    name: "comprobante-reject.png",
    mimeType: "image/png",
    buffer: Buffer.from(TINY_PNG_BASE64_BLUE, "base64")
  });
  await editForm.getByRole("button", { name: localizedName("Enviar comprobante", "Send proof") }).click();
  await expect(page.getByText(localizedName("Comprobante enviado para aprobación", "Proof sent for approval"))).toBeVisible();

  await editForm.getByRole("button", { name: localizedName("Rechazar", "Reject") }).click();
  await editForm.getByPlaceholder(localizedName("Motivo del rechazo", "Rejection reason")).fill("El importe no coincide con el comprobante");
  await editForm.getByRole("button", { name: localizedName("Confirmar rechazo", "Confirm rejection") }).click();
  await expect(page.getByText(localizedName("Comprobante rechazado", "Proof rejected"))).toBeVisible();
  await expect(editForm.getByText(localizedText("Rechazado", "Rejected"))).toBeVisible();
  await expect(editForm.getByText("El importe no coincide con el comprobante")).toBeVisible();

  // A rejected proof no longer offers Aprobar/Rechazar -- it is a dead end, not
  // resubmittable, matching the backend's PaymentProofError("... rechazado").
  await expect(editForm.getByRole("button", { name: localizedName("Aprobar", "Approve") })).toHaveCount(0);
  await expect(editForm.getByRole("button", { name: localizedName("Rechazar", "Reject") })).toHaveCount(0);
  expect(await readStat(editForm, localizedText("Pagado", "Paid"))).toBe(0);

  await editModal.getByRole("button", { name: localizedName("Cerrar", "Close") }).click();
});

test("a rapid double-click on a cash partial payment must not double the charge", async ({ page }) => {
  const suffix = `${Date.now()}c`;
  const guestLastName = `QA-Pay-Retry ${suffix}`;

  await login(page);
  await ensureCashSessionOpen(page);
  const { reservationRow } = await createReservation(page, guestLastName, suffix, 67, 70);
  const { editModal, editForm } = await openPaymentsPanel(reservationRow, page);

  expect(await readStat(editForm, localizedText("Total", "Total"))).toBe(300);
  await editForm.getByLabel(/Monto del movimiento|Monto a cobrar|Cash movement amount|Amount to collect/i).fill("50");
  const partialPaymentButton = editForm.getByRole("button", { name: localizedName("Cobro parcial", "Partial payment") });
  await expect(editForm.getByTestId("payment-backend-quote")).toBeVisible();
  await expect(partialPaymentButton).toBeEnabled();

  // Fire two native clicks back-to-back in the SAME JS turn (no await between
  // them), before React has a chance to re-render the button as disabled from
  // the first click's mutation. This is the realistic double-click race: the
  // the payment hook reuses an Idempotency-Key when retrying the same intent,
  // so the backend's idempotency-key dedup cannot catch two distinct clicks --
  // only a same-amount-exceeds-balance guard could, and $50 + $50 is still
  // within the $300 balance, so nothing else stops a silent double charge.
  await partialPaymentButton.evaluate((button) => {
    button.click();
    button.click();
  });

  // Give both requests time to land, then reload the summary from the server
  // (not the optimistic toast) and assert exactly ONE $50 charge landed.
  await page.waitForTimeout(1500);
  await editModal.getByRole("button", { name: localizedName("Cerrar", "Close") }).click();
  const reopened = await openPaymentsPanel(reservationRow, page);
  const paidAfterDoubleClick = await readStat(reopened.editForm, localizedText("Pagado", "Paid"));
  expect(paidAfterDoubleClick, "a double-click must charge $50 once, not twice").toBe(50);

  await reopened.editModal.getByRole("button", { name: localizedName("Cerrar", "Close") }).click();
});
