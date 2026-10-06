import { expect, test, type Page } from "@playwright/test";

import { completeStepUpPrompt, loginAsStepUpOwner } from "./support/step-up-owner";

const credentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

const receptionistCredentials = {
  email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
  password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!"
};

async function login(page: Page, creds: { email: string; password: string } = credentials) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(creds.email);
  await page.locator('input[type="password"]').fill(creds.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

function parseMoney(text: string) {
  return Number(text.replace(/[^0-9,.-]/g, "").replace(/\./g, "").replace(",", "."));
}

test("owner controls manual cash movements, approves an arqueo difference and confirms custody", async ({ page }, testInfo) => {
  // Login, difference approval, and custody receipt each consume a distinct
  // TOTP step; allow two code-window boundaries plus the UI journey.
  test.setTimeout(120_000);
  const ownerSession = await loginAsStepUpOwner(page, "cash", testInfo.project.name);
  let lastTotpStep = ownerSession.lastTotpStep;
  // The "Abrir caja" button starts enabled optimistically and only flips to
  // "Ya hay una caja abierta" once GET /api/cash-register/sessions resolves
  // (CashRegisterPage derives openSession from an initially-empty sessions
  // array). Other specs sharing this hotel's cash sessions can leave one
  // open, so wait for that response before reading the button state --
  // otherwise the decision (and the click right after) can race the
  // real data and target a button that is about to disappear.
  const sessionsResponse = page.waitForResponse(
    (response) => response.url().includes("/api/cash-register/sessions") && response.request().method() === "GET"
  );
  await page.goto("/caja");
  await sessionsResponse;

  const openingForm = page.locator("form").filter({ hasText: "Saldo inicial" }).filter({ hasText: "Abrir caja" });
  const openButton = page.getByRole("button", { name: "Abrir caja", exact: true });
  const existingOpenButton = page.getByRole("button", { name: "Ya hay una caja abierta", exact: true });
  if (await openButton.isVisible().catch(() => false)) {
    await openingForm.getByText("Saldo inicial", { exact: true }).locator("..").locator("input").fill("1000");
    await openButton.click();
    await expect(page.getByText("Caja abierta.", { exact: true })).toBeVisible();
  } else {
    await expect(existingOpenButton).toBeVisible();
  }

  const movementForm = page.locator("form")
    .filter({ hasText: "Tipo" })
    .filter({ hasText: "Importe" })
    .filter({ hasText: "Descripción" });
  const createExpenseButton = page.getByTestId("cash-create-expense-button");
  await expect(createExpenseButton).toBeVisible();
  await createExpenseButton.click();
  await expect(movementForm.getByText("Categoría", { exact: true })).toBeVisible();
  await expect(movementForm.getByText("Proveedor", { exact: true })).toBeVisible();
  await expect(movementForm.getByText("Referencia del comprobante", { exact: true })).toBeVisible();
  await expect(movementForm.getByText("Reserva ID", { exact: true })).not.toBeVisible();
  await expect(movementForm.getByText("Transaccion ID", { exact: true })).not.toBeVisible();

  const rejectedExpensePosts: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (
      request.method() === "POST" &&
      /^\/api\/cash-register\/sessions\/\d+\/expenses$/.test(url.pathname)
    ) {
      rejectedExpensePosts.push(url.pathname);
    }
  });
  await movementForm.getByText("Importe", { exact: true }).locator("..").locator("input").fill("200");
  await movementForm.getByText("Descripción", { exact: true }).locator("..").locator("input").fill("Gasto sin proveedor");
  await movementForm.getByText("Categoría", { exact: true }).locator("..").locator("input").fill("Insumos");
  await movementForm.getByText("Referencia del comprobante", { exact: true }).locator("..").locator("input").fill("COMP-E2E-NEGATIVE");
  await movementForm.getByRole("button", { name: "Registrar gasto pendiente", exact: true }).click();
  await expect(page.getByTestId("cash-expense-validation-error")).toHaveText("Completá: Proveedor.");
  expect(rejectedExpensePosts).toHaveLength(0);

  await movementForm.getByText("Tipo", { exact: true }).locator("..").locator("select").selectOption("income");
  await movementForm.getByText("Importe", { exact: true }).locator("..").locator("input").fill("500");
  await movementForm.getByText("Descripción", { exact: true }).locator("..").locator("input").fill("Venta de minibar");
  await movementForm.getByRole("button", { name: "Registrar movimiento", exact: true }).click();
  await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();

  await createExpenseButton.click();
  await movementForm.getByText("Importe", { exact: true }).locator("..").locator("input").fill("200");
  await movementForm.getByText("Descripción", { exact: true }).locator("..").locator("input").fill("Compra de insumos");
  await movementForm.getByText("Categoría", { exact: true }).locator("..").locator("input").fill("Insumos");
  await movementForm.getByText("Proveedor", { exact: true }).locator("..").locator("input").fill("Proveedor E2E");
  await movementForm.getByText("Referencia del comprobante", { exact: true }).locator("..").locator("input").fill("COMP-2026-001");
  await movementForm.getByRole("button", { name: "Registrar gasto pendiente", exact: true }).click();
  await expect(page.getByText("Gasto pendiente de aprobación. Todavía no modifica el saldo de caja.", { exact: true })).toBeVisible();
  const pendingExpense = page.getByTestId("cash-expenses").locator("li").filter({ hasText: "Compra de insumos" });
  await expect(pendingExpense).toContainText("Pendiente de aprobación");
  await pendingExpense.getByRole("button", { name: "Aprobar gasto · MFA", exact: true }).click();
  lastTotpStep = await completeStepUpPrompt(page, lastTotpStep, ownerSession.auth.user.email);
  await expect(page.getByText("Gasto aprobado y registrado en caja.", { exact: true })).toBeVisible();

  const closeForm = page.locator("form").filter({ hasText: "Saldo esperado:" }).filter({ hasText: "Cerrar caja" });
  const expectedText = await closeForm.getByText(/Saldo esperado:/).innerText();
  const expectedBalance = parseMoney(expectedText);
  expect(expectedBalance).toBeGreaterThanOrEqual(300);
  const countedBalance = Math.max(0, expectedBalance - 50);
  await closeForm.getByText("Saldo contado", { exact: true }).locator("..").locator("input").fill(String(countedBalance));
  const closeResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return response.request().method() === "POST" && /\/api\/cash-register\/sessions\/\d+\/close$/.test(url.pathname);
  });
  await closeForm.getByRole("button", { name: "Cerrar caja", exact: true }).click();
  const closedReport = await closeResponse.then((response) =>
    response.json() as Promise<{ session_id: number }>
  );
  await expect(page.getByText("Caja cerrada.", { exact: true })).toBeVisible();
  await expect(page.getByText(/Estado: pendiente de aprobación/, { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Aprobar diferencia", exact: true }).last().click();
  lastTotpStep = await completeStepUpPrompt(page, lastTotpStep, ownerSession.auth.user.email);
  await expect(page.getByText("Diferencia aprobada.", { exact: true })).toBeVisible();
  await expect(page.getByText(/^Custodia: pendiente de recepción del dueño o la codueña por /)).toBeVisible();
  const currentCustody = page.getByTestId("cash-pending-custodies")
    .getByRole("listitem")
    .filter({ hasText: new RegExp(`Caja #${closedReport.session_id} ·`) });
  await expect(currentCustody).toHaveCount(1);
  await currentCustody
    .getByRole("button", { name: "Confirmar custodia y cambio", exact: true })
    .click();
  const custodyTotpStep = await completeStepUpPrompt(page, lastTotpStep, ownerSession.auth.user.email);
  await expect(page.getByText(/Recepción confirmada\. Fondo de cambio para la sucesora:/)).toBeVisible();
  expect(lastTotpStep).toBeGreaterThan(ownerSession.lastTotpStep);
  expect(custodyTotpStep).toBeGreaterThan(lastTotpStep);
  await expect(page.getByText(/^Caja sucesora: .* abierta con saldo \$\s*0(?:,00)?\.$/)).toBeVisible();
});

// Cash-difference approval is owner/co-owner only (see permission_service.py);
// receptionist can operate cash (open/close/movements) but not approve a close
// difference.
test("receptionist can close cash with a difference but cannot approve it", async ({ page }) => {
  await login(page, receptionistCredentials);
  await page.goto("/caja");

  // Reuses the successor session the owner test above leaves open at $0.
  await expect(page.getByRole("button", { name: "Ya hay una caja abierta", exact: true })).toBeVisible({
    timeout: 15_000
  });

  const movementForm = page.locator("form").filter({ hasText: "Registrar movimiento" });
  await movementForm.getByText("Tipo", { exact: true }).locator("..").locator("select").selectOption("income");
  await movementForm.getByText("Importe", { exact: true }).locator("..").locator("input").fill("300");
  await movementForm.getByText("Descripción", { exact: true }).locator("..").locator("input").fill("Venta de minibar QA");
  await movementForm.getByRole("button", { name: "Registrar movimiento", exact: true }).click();
  await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();

  const closeForm = page.locator("form").filter({ hasText: "Saldo esperado:" }).filter({ hasText: "Cerrar caja" });
  await closeForm.getByText("Saldo contado", { exact: true }).locator("..").locator("input").fill("0");
  await closeForm.getByRole("button", { name: "Cerrar caja", exact: true }).click();
  await expect(page.getByText("Caja cerrada.", { exact: true })).toBeVisible();
  await expect(page.getByText(/Estado: pendiente de aprobación/, { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Aprobar diferencia", exact: true })).toHaveCount(0);
  // No cleanup needed: close_session() always opens a new successor session
  // regardless of whether this difference gets approved (see
  // app/services/cash_register_service.py), so leaving it pending here
  // doesn't block the next test from opening/using cash.
});
