import { expect, test, type Page } from "@playwright/test";
import { completeStepUpPrompt, loginAsStepUpOwner } from "./support/step-up-owner";

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const localizedName = (spanish: string, english: string) =>
  new RegExp(`^(?:${escapeRegExp(spanish)}|${escapeRegExp(english)})$`, "i");
const localizedText = (spanish: string, english: string) =>
  new RegExp(`(?:${escapeRegExp(spanish)}|${escapeRegExp(english)})`, "i");

// Fase 4 (Fase master): full payments/balance journey, real backend, real UI.
// Standard E2E category prices at $100/night (see manager-reports-journey.spec.ts),
// so a deterministic 3-night reservation totals $300 and a 30% deposit is $90.
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

async function ensureCashSessionOpen(page: Page) {
  const sessionsResponse = page.waitForResponse(
    (response) => response.url().includes("/api/cash-register/sessions") && response.request().method() === "GET"
  );
  await page.goto("/caja");
  await sessionsResponse;
  const openingForm = page
    .locator("form")
    .filter({ hasText: localizedText("Saldo inicial", "Opening balance") })
    .filter({ hasText: localizedText("Abrir caja", "Open cash register") });
  const openButton = openingForm.getByRole("button", { name: localizedName("Abrir caja", "Open cash register") });
  if (await openButton.isVisible().catch(() => false)) {
    await openingForm.getByText(localizedName("Saldo inicial", "Opening balance")).locator("..").locator("input").fill("0");
    await openButton.click();
    await expect(page.getByText(localizedName("Caja abierta.", "Cash register opened."))).toBeVisible();
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
  await createButton.click();
  await expect(page.getByText(localizedName("Reserva creada", "Reservation created"))).toBeVisible();

  const reservationTable = page.locator("table").filter({ hasText: localizedText("Código", "Code") });
  const reservationRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await expect(reservationRow).toHaveCount(1);
  return { reservationTable, reservationRow };
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
  const suffix = `${Date.now()}a`;
  const guestLastName = `QA-Pay-Mix ${suffix}`;

  const ownerSession = await loginAsStepUpOwner(page, "cash", testInfo.project.name);
  let lastTotpStep = ownerSession.lastTotpStep;
  await ensureCashSessionOpen(page);

  const { reservationTable, reservationRow } = await createReservation(page, guestLastName, suffix, 60, 63);
  const { editModal, editForm } = await openPaymentsPanel(reservationRow, page);

  const total = await readStat(editForm, localizedText("Total", "Total"));
  expect(total).toBe(300);
  const depositRequired = await readStat(editForm, localizedText("Seña requerida", "Deposit required"));
  expect(depositRequired).toBe(90);

  // 1) Seña manual en efectivo.
  await editForm.getByRole("button", { name: localizedText("Registrar Seña", "Register deposit") }).click();
  await expect(page.getByText(localizedName("Se registró la Seña", "Deposit registered"))).toBeVisible();
  await expect.poll(() => readStat(editForm, localizedText("Pagado", "Paid"))).toBe(90);
  await expect.poll(() => readStat(editForm, localizedText("Saldo", "Balance"))).toBe(210);

  // 12) Intento de sobrepago: pedir más que el saldo pendiente debe rechazarse
  // client-side, sin llegar a cobrar nada de más.
  await editForm.getByLabel(/Monto del movimiento|Monto a cobrar|Cash movement amount|Amount to collect/i).fill("999999");
  await editForm.getByRole("button", { name: localizedName("Cobro parcial", "Partial payment") }).click();
  await expect(page.getByText(localizedName("Ingresá un importe positivo que no supere el saldo pendiente.", "Enter a positive amount that does not exceed the pending balance."))).toBeVisible();
  expect(await readStat(editForm, localizedText("Pagado", "Paid"))).toBe(90);

  // 9) Saldo final con un método DISTINTO al de la seña: transferencia + comprobante.
  await editForm.locator("label").filter({ hasText: localizedText("Medio de pago", "Payment method") }).locator("select").selectOption("bank_transfer");
  await editForm.getByLabel(/Monto del movimiento|Monto a cobrar|Cash movement amount|Amount to collect/i).fill("210");
  await editForm.getByLabel(localizedName("Imagen del comprobante", "Proof image")).setInputFiles({
    name: "comprobante.png",
    mimeType: "image/png",
    buffer: Buffer.from(TINY_PNG_BASE64_RED, "base64")
  });
  await editForm.getByRole("button", { name: localizedName("Enviar comprobante", "Send proof") }).click();
  await expect(page.getByText(localizedName("Comprobante enviado para aprobación", "Proof sent for approval"))).toBeVisible();
  // Bank transfer does not touch the balance until approved.
  expect(await readStat(editForm, localizedText("Pagado", "Paid"))).toBe(90);
  await expect(editForm.getByText(localizedText("· pendiente", "· pending"))).toBeVisible();

  // 4) Aprobación del comprobante -> ahora sí se aplica al saldo, con el método
  // distinto al de la seña (transferencia vs. la seña en efectivo).
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
  await editForm.getByRole("button", { name: localizedName("Registrar devolución", "Register refund") }).click();
  lastTotpStep = await completeStepUpPrompt(page, lastTotpStep, ownerSession.auth.user.email);
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
  expect(await readStat(editForm, localizedText("Seña requerida", "Deposit required"))).toBe(90);

  const amountInput = editForm.getByLabel(/Monto del movimiento|Monto a cobrar|Cash movement amount|Amount to collect/i);
  const depositButton = editForm.getByRole("button", { name: localizedText("Registrar Seña", "Register deposit") });
  await expect(depositButton).toContainText("90");
  await amountInput.fill("51");
  await expect(depositButton).toContainText("51");

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
  expect(registeredDeposit.amount).toBe(51);
  expect(registeredDeposit.transaction_type).toBe("deposit");
  expect(confirmationMessage).toContain("90");
  expect(confirmationMessage).toContain("51");
  await expect(page.getByText(localizedName("Se registró la Seña", "Deposit registered"))).toBeVisible();
  await expect.poll(() => readStat(editForm, localizedText("Pagado", "Paid"))).toBe(51);
  await expect.poll(() => readStat(editForm, localizedText("Saldo", "Balance"))).toBe(249);

  // An amount above the remaining balance is rejected before any payment request.
  await amountInput.fill("999999");
  await depositButton.click();
  await expect(page.getByText(localizedName("Ingresá un importe positivo que no supere el saldo pendiente.", "Enter a positive amount that does not exceed the pending balance."))).toBeVisible();
  expect(paymentRequests).toHaveLength(1);
  expect(await readStat(editForm, localizedText("Pagado", "Paid"))).toBe(51);

  // Declining the confirmation must also leave the ledger untouched.
  await amountInput.fill("20");
  page.once("dialog", async (dialog) => dialog.dismiss());
  await depositButton.click();
  expect(paymentRequests).toHaveLength(1);
  expect(await readStat(editForm, localizedText("Pagado", "Paid"))).toBe(51);

  // Clearing the field uses the remaining deposit amount (90 - 51) by default.
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
  expect(defaultDeposit.amount).toBe(39);
  expect(defaultDeposit.transaction_type).toBe("deposit");
  await expect(page.getByText(localizedName("Se registró la Seña", "Deposit registered"))).toBeVisible();
  await expect.poll(() => readStat(editForm, localizedText("Pagado", "Paid"))).toBe(90);
  await expect.poll(() => readStat(editForm, localizedText("Saldo", "Balance"))).toBe(210);
});

test("owner rejects a transfer proof with a reason and the proof cannot be approved afterwards", async ({ page }) => {
  const suffix = `${Date.now()}b`;
  const guestLastName = `QA-Pay-Reject ${suffix}`;

  await login(page);
  const { reservationRow } = await createReservation(page, guestLastName, suffix, 64, 66);
  const { editModal, editForm } = await openPaymentsPanel(reservationRow, page);

  await editForm.locator("label").filter({ hasText: localizedText("Medio de pago", "Payment method") }).locator("select").selectOption("bank_transfer");
  await editForm.getByLabel(localizedName("Monto a cobrar", "Amount to collect")).fill("60");
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

  // Fire two native clicks back-to-back in the SAME JS turn (no await between
  // them), before React has a chance to re-render the button as disabled from
  // the first click's mutation. This is the realistic double-click race: the
  // the payment hook reuses an Idempotency-Key when retrying the same intent,
  // so the backend's idempotency-key dedup cannot catch two distinct clicks --
  // only a same-amount-exceeds-balance guard could, and $50 + $50 is still
  // within the $300 balance, so nothing else stops a silent double charge.
  await editForm.getByRole("button", { name: localizedName("Cobro parcial", "Partial payment") }).evaluate((button) => {
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
