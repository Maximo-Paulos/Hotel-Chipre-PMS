import { expect, test, type Page } from "@playwright/test";

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
  const openingForm = page.locator("form").filter({ hasText: "Saldo inicial" }).filter({ hasText: "Abrir caja" });
  const openButton = openingForm.getByRole("button", { name: "Abrir caja", exact: true });
  if (await openButton.isVisible().catch(() => false)) {
    await openingForm.getByText("Saldo inicial", { exact: true }).locator("..").locator("input").fill("0");
    await openButton.click();
    await expect(page.getByText("Caja abierta.", { exact: true })).toBeVisible();
  }
}

async function createReservation(page: Page, guestLastName: string, suffix: string, offsetIn: number, offsetOut: number) {
  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  const reservationForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(reservationForm).toBeVisible();

  await reservationForm.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
  await reservationForm.getByPlaceholder("Nombre").fill("Huésped");
  await reservationForm.getByPlaceholder("Apellido").fill(guestLastName);
  await reservationForm.getByPlaceholder("Email").fill(`qa.pay.${suffix}@example.test`);
  await reservationForm.getByPlaceholder("Teléfono").fill("1112345678");
  await reservationForm.getByLabel("Tipo de documento").selectOption("DNI");
  await reservationForm.getByPlaceholder("Documento").fill(`QA-PAY-${suffix}`);
  await reservationForm.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = reservationForm.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  await categorySelect.selectOption((await categoryOption.getAttribute("value"))!);
  await reservationForm.locator("label").filter({ hasText: "Check-in" }).locator('input[type="date"]').fill(localIsoDate(offsetIn));
  await reservationForm.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]').fill(localIsoDate(offsetOut));

  const createButton = reservationForm.getByRole("button", { name: "Crear", exact: true });
  await expect(createButton).toBeEnabled();
  await createButton.click();
  await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();

  const reservationTable = page.locator("table").filter({ hasText: "Código" });
  const reservationRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await expect(reservationRow).toHaveCount(1);
  return { reservationTable, reservationRow };
}

async function openPaymentsPanel(row: ReturnType<Page["locator"]>, page: Page) {
  await row.getByRole("button", { name: "Editar", exact: true }).click();
  const editModal = page.locator("div.fixed").filter({ hasText: "Pagos y balance" });
  const editForm = editModal.locator("form").filter({ hasText: "Pagos y balance" });
  await expect(editForm).toBeVisible();
  await expect(editForm.getByText("Cargando resumen...", { exact: true })).toHaveCount(0);
  return { editModal, editForm };
}

async function readStat(editForm: ReturnType<Page["locator"]>, label: string) {
  const value = await editForm
    .locator("p.text-xs.text-slate-500", { hasText: label })
    .locator("xpath=following-sibling::p[1]")
    .innerText();
  return parseMoney(value);
}

test.describe.configure({ mode: "serial" });

test("owner pays deposit in cash, blocks an overpayment, settles the rest by approved bank transfer with a different method", async ({
  page
}) => {
  const suffix = `${Date.now()}a`;
  const guestLastName = `QA-Pay-Mix ${suffix}`;

  await login(page);
  await ensureCashSessionOpen(page);

  const { reservationTable, reservationRow } = await createReservation(page, guestLastName, suffix, 60, 63);
  const { editModal, editForm } = await openPaymentsPanel(reservationRow, page);

  const total = await readStat(editForm, "Total");
  expect(total).toBe(300);
  const depositRequired = await readStat(editForm, "Seña requerida");
  expect(depositRequired).toBe(90);

  // 1) Seña manual en efectivo.
  await editForm.getByRole("button", { name: "Registrar Seña", exact: true }).click();
  await expect(page.getByText("Se registró la Seña", { exact: true })).toBeVisible();
  await expect.poll(() => readStat(editForm, "Pagado")).toBe(90);
  await expect.poll(() => readStat(editForm, "Saldo")).toBe(210);

  // 12) Intento de sobrepago: pedir más que el saldo pendiente debe rechazarse
  // client-side, sin llegar a cobrar nada de más.
  await editForm.getByLabel("Monto a cobrar").fill("999999");
  await editForm.getByRole("button", { name: "Cobro parcial", exact: true }).click();
  await expect(page.getByText("Ingresá un importe positivo que no supere el saldo pendiente.", { exact: true })).toBeVisible();
  expect(await readStat(editForm, "Pagado")).toBe(90);

  // 9) Saldo final con un método DISTINTO al de la seña: transferencia + comprobante.
  await editForm.locator("label").filter({ hasText: "Medio de pago" }).locator("select").selectOption("bank_transfer");
  await editForm.getByLabel("Monto a cobrar").fill("210");
  await editForm.getByLabel("Imagen del comprobante").setInputFiles({
    name: "comprobante.png",
    mimeType: "image/png",
    buffer: Buffer.from(TINY_PNG_BASE64_RED, "base64")
  });
  await editForm.getByRole("button", { name: "Enviar comprobante", exact: true }).click();
  await expect(page.getByText("Comprobante enviado para aprobación", { exact: true })).toBeVisible();
  // Bank transfer does not touch the balance until approved.
  expect(await readStat(editForm, "Pagado")).toBe(90);
  await expect(editForm.getByText(/pending/)).toBeVisible();

  // 4) Aprobación del comprobante -> ahora sí se aplica al saldo, con el método
  // distinto al de la seña (transferencia vs. la seña en efectivo).
  await editForm.getByRole("button", { name: "Aprobar", exact: true }).click();
  await expect.poll(() => readStat(editForm, "Pagado")).toBe(300);
  await expect.poll(() => readStat(editForm, "Saldo")).toBe(0);
  await expect(editForm.getByText(/approved/)).toBeVisible();

  // 10) Reembolso: devolución parcial en efectivo sobre lo cobrado.
  await editForm.locator("label").filter({ hasText: "Medio de pago" }).locator("select").selectOption("cash");
  await editForm.getByLabel("Monto a cobrar").fill("50");
  page.once("dialog", (dialog) => dialog.accept());
  await editForm.getByRole("button", { name: "Registrar devolución", exact: true }).click();
  await expect(page.getByText("Devolución registrada", { exact: true })).toBeVisible();
  await expect.poll(() => readStat(editForm, "Pagado")).toBe(250);
  await expect.poll(() => readStat(editForm, "Saldo")).toBe(50);

  // Refund beyond what was actually paid must be rejected client-side too, never
  // leaving a negative balance/paid amount.
  await editForm.getByLabel("Monto a cobrar").fill("999999");
  await editForm.getByRole("button", { name: "Registrar devolución", exact: true }).click();
  await expect(page.getByText("Ingresá un importe positivo que no supere el total pagado.", { exact: true })).toBeVisible();
  expect(await readStat(editForm, "Pagado")).toBe(250);

  await editModal.getByRole("button", { name: "Cerrar", exact: true }).click();
  void reservationTable;
});

test("owner rejects a transfer proof with a reason and the proof cannot be approved afterwards", async ({ page }) => {
  const suffix = `${Date.now()}b`;
  const guestLastName = `QA-Pay-Reject ${suffix}`;

  await login(page);
  const { reservationRow } = await createReservation(page, guestLastName, suffix, 64, 66);
  const { editModal, editForm } = await openPaymentsPanel(reservationRow, page);

  await editForm.locator("label").filter({ hasText: "Medio de pago" }).locator("select").selectOption("bank_transfer");
  await editForm.getByLabel("Monto a cobrar").fill("60");
  await editForm.getByLabel("Imagen del comprobante").setInputFiles({
    name: "comprobante-reject.png",
    mimeType: "image/png",
    buffer: Buffer.from(TINY_PNG_BASE64_BLUE, "base64")
  });
  await editForm.getByRole("button", { name: "Enviar comprobante", exact: true }).click();
  await expect(page.getByText("Comprobante enviado para aprobación", { exact: true })).toBeVisible();

  await editForm.getByRole("button", { name: "Rechazar", exact: true }).click();
  await editForm.getByPlaceholder("Motivo del rechazo").fill("El importe no coincide con el comprobante");
  await editForm.getByRole("button", { name: "Confirmar rechazo", exact: true }).click();
  await expect(page.getByText("Comprobante rechazado", { exact: true })).toBeVisible();
  await expect(editForm.getByText(/rejected/)).toBeVisible();
  await expect(editForm.getByText("El importe no coincide con el comprobante")).toBeVisible();

  // A rejected proof no longer offers Aprobar/Rechazar -- it is a dead end, not
  // resubmittable, matching the backend's PaymentProofError("... rechazado").
  await expect(editForm.getByRole("button", { name: "Aprobar", exact: true })).toHaveCount(0);
  await expect(editForm.getByRole("button", { name: "Rechazar", exact: true })).toHaveCount(0);
  expect(await readStat(editForm, "Pagado")).toBe(0);

  await editModal.getByRole("button", { name: "Cerrar", exact: true }).click();
});

test("a rapid double-click on a cash partial payment must not double the charge", async ({ page }) => {
  const suffix = `${Date.now()}c`;
  const guestLastName = `QA-Pay-Retry ${suffix}`;

  await login(page);
  await ensureCashSessionOpen(page);
  const { reservationRow } = await createReservation(page, guestLastName, suffix, 67, 70);
  const { editModal, editForm } = await openPaymentsPanel(reservationRow, page);

  expect(await readStat(editForm, "Total")).toBe(300);
  await editForm.getByLabel("Monto a cobrar").fill("50");

  // Fire two native clicks back-to-back in the SAME JS turn (no await between
  // them), before React has a chance to re-render the button as disabled from
  // the first click's mutation. This is the realistic double-click race: the
  // frontend mints a brand-new Idempotency-Key on every call to makePayment(),
  // so the backend's idempotency-key dedup cannot catch two distinct clicks --
  // only a same-amount-exceeds-balance guard could, and $50 + $50 is still
  // within the $300 balance, so nothing else stops a silent double charge.
  await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll("button"));
    const target = buttons.find((btn) => btn.textContent?.trim() === "Cobro parcial");
    if (!target) throw new Error("Cobro parcial button not found");
    target.click();
    target.click();
  });

  // Give both requests time to land, then reload the summary from the server
  // (not the optimistic toast) and assert exactly ONE $50 charge landed.
  await page.waitForTimeout(1500);
  await editModal.getByRole("button", { name: "Cerrar", exact: true }).click();
  const reopened = await openPaymentsPanel(reservationRow, page);
  const paidAfterDoubleClick = await readStat(reopened.editForm, "Pagado");
  expect(paidAfterDoubleClick, "a double-click must charge $50 once, not twice").toBe(50);

  await reopened.editModal.getByRole("button", { name: "Cerrar", exact: true }).click();
});
