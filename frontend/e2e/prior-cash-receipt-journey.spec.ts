import { expect, test, type Page } from "@playwright/test";

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

async function login(page: Page, user: typeof manager) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(user.email);
  await page.locator('input[type="password"]').fill(user.password);
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
    await openingForm.getByText("Saldo inicial", { exact: true }).locator("..").locator("input").fill("50000");
    await openButton.click();
    await expect(page.getByText("Caja abierta.", { exact: true })).toBeVisible();
  }
}

async function readDailyCashSummary(page: Page) {
  const responsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/cash-register/daily-summary" && response.request().method() === "GET";
  });
  await page.goto("/caja");
  const response = await responsePromise;
  expect(response.ok()).toBeTruthy();
  return await response.json() as {
    gross_collected: string | number;
    refunds: string | number;
    net_collected: string | number;
    physical_cash_net_collected: string | number;
    physical_cash: Record<string, string | number | null>;
  };
}

async function createReservation(page: Page, suffix: string) {
  const guestLastName = `QA-Previo ${suffix}`;
  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  const form = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(form).toBeVisible();

  await form.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
  await form.getByPlaceholder("Nombre").fill("Huésped");
  await form.getByPlaceholder("Apellido").fill(guestLastName);
  await form.getByPlaceholder("Email").fill(`qa.prior.${suffix}@example.test`);
  await form.getByPlaceholder("Teléfono").fill("1112345678");
  await form.getByLabel("Tipo de documento").selectOption("DNI");
  await form.getByPlaceholder("Documento").fill(`QAPREVIO-${suffix}`);
  await form.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = form.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  await categorySelect.selectOption((await categoryOption.getAttribute("value"))!);
  await form.getByLabel("Check-in", { exact: true }).fill(localIsoDate(60));
  await form.getByLabel("Check-out", { exact: true }).fill(localIsoDate(63));
  await form.getByRole("button", { name: "Crear", exact: true }).click();
  await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();

  const row = page.locator("table").filter({ hasText: "Código" }).locator("tbody tr").filter({ hasText: guestLastName });
  await expect(row).toHaveCount(1);
  return { guestLastName, row };
}

test.use({ trace: "off", screenshot: "off", video: "off" });
test.describe.configure({ mode: "serial" });

test("manager records prior cash outside the open drawer and reception cannot select that action", async ({ page }) => {
  test.setTimeout(90_000);
  const suffix = `${Date.now()}`;
  const reason = `Seña del libro anterior ${suffix}`;

  await login(page, manager);
  await ensureCashSessionOpen(page);
  const beforePriorReceipt = await readDailyCashSummary(page);
  const { guestLastName, row } = await createReservation(page, suffix);
  await row.getByRole("button", { name: "Editar", exact: true }).click();
  const editForm = page.locator("div.fixed").filter({ hasText: "Pagos y balance" }).locator("form").filter({ hasText: "Pagos y balance" });
  await expect(editForm).toBeVisible();
  await expect(editForm.getByText("Cargando resumen...", { exact: true })).toHaveCount(0);

  await editForm.getByTestId("prior-receipt-toggle").check();
  await editForm.getByTestId("prior-receipt-date").fill(localIsoDate(-2));
  await editForm.getByTestId("prior-receipt-reason").fill(reason);
  const paymentRequest = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname === "/api/payments" && request.method() === "POST";
  });
  await editForm.getByRole("button", { name: /Registrar Seña/ }).click();
  const payload = await paymentRequest.then((request) => request.postDataJSON()) as {
    amount: number;
    collected_before: boolean;
    collected_on: string;
    payment_method: string;
    prior_receipt_note: string;
    transaction_type: string;
  };
  expect(payload).toMatchObject({
    collected_before: true,
    collected_on: localIsoDate(-2),
    payment_method: "cash",
    prior_receipt_note: reason,
    transaction_type: "deposit"
  });
  expect(payload.amount).toBeGreaterThan(0);
  await expect(page.getByText("Se registró la Seña", { exact: true })).toBeVisible();
  await expect(editForm.getByText(new RegExp(reason))).toBeVisible();

  const afterPriorReceipt = await readDailyCashSummary(page);
  const priorReceipts = page.getByTestId("cash-prior-receipts");
  await expect(priorReceipts).toContainText("1 cobro(s)");
  await expect(priorReceipts).toContainText(reason);
  for (const field of ["gross_collected", "refunds", "net_collected", "physical_cash_net_collected"] as const) {
    expect(Number(afterPriorReceipt[field])).toBe(Number(beforePriorReceipt[field]));
  }
  for (const field of [
    "opening_balance",
    "income_total",
    "expense_total",
    "expected_balance",
    "manual_income_total",
    "manual_expense_total",
    "difference"
  ]) {
    expect(afterPriorReceipt.physical_cash[field]).toBe(beforePriorReceipt.physical_cash[field]);
  }

  await page.context().clearCookies();
  await login(page, receptionist);
  await page.goto("/reservas");
  const receptionistRow = page.locator("table").filter({ hasText: "Código" }).locator("tbody tr").filter({ hasText: guestLastName });
  await expect(receptionistRow).toHaveCount(1);
  await receptionistRow.getByRole("button", { name: "Editar", exact: true }).click();
  const receptionistForm = page.locator("div.fixed").filter({ hasText: "Pagos y balance" }).locator("form").filter({ hasText: "Pagos y balance" });
  await expect(receptionistForm).toBeVisible();
  await expect(receptionistForm.getByTestId("prior-receipt-toggle")).toHaveCount(0);
});
