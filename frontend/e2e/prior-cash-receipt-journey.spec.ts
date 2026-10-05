import { expect, test, type Page } from "@playwright/test";

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const localizedName = (spanish: string, english: string) =>
  new RegExp(`^(?:${escapeRegExp(spanish)}|${escapeRegExp(english)})$`, "i");
const localizedText = (spanish: string, english: string) =>
  new RegExp(`(?:${escapeRegExp(spanish)}|${escapeRegExp(english)})`, "i");

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
  const openingForm = page
    .locator("form")
    .filter({ hasText: localizedText("Saldo inicial", "Opening balance") })
    .filter({ hasText: localizedText("Abrir caja", "Open cash register") });
  const openButton = openingForm.getByRole("button", { name: localizedName("Abrir caja", "Open cash register") });
  if (await openButton.isVisible().catch(() => false)) {
    await openingForm.getByText(localizedName("Saldo inicial", "Opening balance")).locator("..").locator("input").fill("50000");
    await openButton.click();
    await expect(page.getByText(localizedName("Caja abierta.", "Cash register opened."))).toBeVisible();
  }
}

async function readDailyCashSummary(page: Page) {
  const requestPromise = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname === "/api/cash-register/daily-summary" && request.method() === "GET";
  });
  await page.goto("/caja");
  const appRequest = await requestPromise;
  const appHeaders = new Headers(await appRequest.allHeaders());
  const authorization = appHeaders.get("authorization");
  const hotelId = appHeaders.get("x-hotel-id");
  const userId = appHeaders.get("x-user-id");
  expect(authorization).toBeTruthy();
  expect(hotelId).toBeTruthy();
  expect(userId).toBeTruthy();

  // The browser Response can outlive its CDP body resource during navigation.
  // Replay the same authenticated GET through Playwright's API context, whose
  // response body is buffered independently of the browser network lifecycle.
  const response = await page.request.get(appRequest.url(), {
    headers: {
      Authorization: authorization!,
      "X-Hotel-Id": hotelId!,
      "X-User-Id": userId!
    }
  });
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
  await page.getByRole("button", { name: /^(?:Crear reserva|Create reservation)$/i }).click();
  const form = page.locator("form").filter({ hasText: localizedText("Datos de la reserva", "Reservation details") });
  await expect(form).toBeVisible();

  await form
    .getByRole("button", { name: localizedName("¿No lo encontrás? Crear huésped nuevo", "Can't find them? Create a new guest") })
    .click();
  await form.getByPlaceholder(localizedName("Nombre", "First name")).fill("Huésped");
  await form.getByPlaceholder(localizedName("Apellido", "Last name")).fill(guestLastName);
  await form.getByPlaceholder(localizedName("Email", "Email")).fill(`qa.prior.${suffix}@example.test`);
  await form.getByPlaceholder(localizedName("Teléfono", "Phone")).fill(`11${Date.now().toString().slice(-8)}${Math.floor(Math.random() * 100).toString().padStart(2, "0")}`);
  await form.getByLabel(localizedName("Tipo de documento", "Document type")).selectOption("DNI");
  await form.getByPlaceholder(localizedName("Documento", "Document")).fill(`QAPREVIO-${suffix}`);
  await form.getByRole("button", { name: localizedName("Crear Huésped y asignar ID", "Create guest and assign ID") }).click();
  await expect(page.getByText(localizedName("Huésped creado y asignado", "Guest created and assigned"))).toBeVisible();

  const categorySelect = form.locator("label").filter({ hasText: localizedText("Categoría", "Category") }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  await categorySelect.selectOption((await categoryOption.getAttribute("value"))!);
  await form.getByLabel(localizedName("Check-in", "Check-in")).fill(localIsoDate(60));
  await form.getByLabel(localizedName("Check-out", "Check-out")).fill(localIsoDate(63));
  await form.getByRole("button", { name: localizedName("Crear", "Create") }).click();
  await expect(page.getByText(localizedName("Reserva creada", "Reservation created"))).toBeVisible();

  const row = page.locator("table").filter({ hasText: localizedText("Código", "Code") }).locator("tbody tr").filter({ hasText: guestLastName });
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
  await row.getByRole("button", { name: localizedName("Editar", "Edit") }).click();
  const editForm = page
    .locator("div.fixed")
    .filter({ hasText: localizedText("Pagos y balance", "Payments and balance") })
    .locator("form")
    .filter({ hasText: localizedText("Pagos y balance", "Payments and balance") });
  await expect(editForm).toBeVisible();
  await expect(editForm.getByText(localizedName("Cargando resumen...", "Loading summary..."))).toHaveCount(0);

  await editForm.getByTestId("prior-receipt-toggle").check();
  await editForm.getByTestId("prior-receipt-date").fill(localIsoDate(-2));
  await editForm.getByTestId("prior-receipt-reason").fill(reason);
  const paymentRequest = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname === "/api/payments" && request.method() === "POST";
  });
  await editForm.getByRole("button", { name: localizedText("Registrar Seña", "Register deposit") }).click();
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
  await expect(page.getByText(localizedName("Se registró la Seña", "Deposit registered"))).toBeVisible();
  await expect(editForm.getByText(new RegExp(reason))).toBeVisible();

  const afterPriorReceipt = await readDailyCashSummary(page);
  const priorReceipts = page.getByTestId("cash-prior-receipts");
  await expect(priorReceipts).toContainText(/1\s+(?:cobro\(s\)|receipt(?:\(s\))?)/i);
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
  const receptionistRow = page.locator("table").filter({ hasText: localizedText("Código", "Code") }).locator("tbody tr").filter({ hasText: guestLastName });
  await expect(receptionistRow).toHaveCount(1);
  await receptionistRow.getByRole("button", { name: localizedName("Editar", "Edit") }).click();
  const receptionistForm = page
    .locator("div.fixed")
    .filter({ hasText: localizedText("Pagos y balance", "Payments and balance") })
    .locator("form")
    .filter({ hasText: localizedText("Pagos y balance", "Payments and balance") });
  await expect(receptionistForm).toBeVisible();
  await expect(receptionistForm.getByTestId("prior-receipt-toggle")).toHaveCount(0);
});
