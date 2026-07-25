import { expect, test, type Page } from "@playwright/test";

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

test("owner controls manual cash movements, approves an arqueo difference and confirms custody", async ({ page }) => {
  await login(page);
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

  const movementForm = page.locator("form").filter({ hasText: "Registrar movimiento" });
  await expect(movementForm.getByText("Reserva ID", { exact: true })).not.toBeVisible();
  await expect(movementForm.getByText("Transaccion ID", { exact: true })).not.toBeVisible();
  await movementForm.getByText("Tipo", { exact: true }).locator("..").locator("select").selectOption("income");
  await movementForm.getByText("Importe", { exact: true }).locator("..").locator("input").fill("500");
  await movementForm.getByText("Descripcion", { exact: true }).locator("..").locator("input").fill("Venta de minibar");
  await movementForm.getByRole("button", { name: "Registrar movimiento", exact: true }).click();
  await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();

  await movementForm.getByText("Tipo", { exact: true }).locator("..").locator("select").selectOption("expense");
  await movementForm.getByText("Importe", { exact: true }).locator("..").locator("input").fill("200");
  await movementForm.getByText("Descripcion", { exact: true }).locator("..").locator("input").fill("Compra de insumos");
  await movementForm.getByRole("button", { name: "Registrar movimiento", exact: true }).click();
  await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();

  const closeForm = page.locator("form").filter({ hasText: "Saldo esperado:" }).filter({ hasText: "Cerrar caja" });
  const expectedText = await closeForm.getByText(/Saldo esperado:/).innerText();
  const expectedBalance = parseMoney(expectedText);
  expect(expectedBalance).toBeGreaterThanOrEqual(300);
  const countedBalance = Math.max(0, expectedBalance - 50);
  await closeForm.getByText("Saldo contado", { exact: true }).locator("..").locator("input").fill(String(countedBalance));
  await closeForm.getByRole("button", { name: "Cerrar caja", exact: true }).click();
  await expect(page.getByText("Caja cerrada.", { exact: true })).toBeVisible();
  await expect(page.getByText(/Estado: pendiente de aprobacion/, { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Aprobar diferencia", exact: true }).last().click();
  await expect(page.getByText("Diferencia aprobada.", { exact: true })).toBeVisible();
  await expect(page.getByText("Custodia: recepción confirmada.", { exact: true })).toBeVisible();
  await expect(page.getByText(/Caja sucesora: .* abierta con saldo \$0/)).toBeVisible();
});

// PERMISSION_CASH_APPROVE_DIFFERENCE is manager+ only (see permission_service.py);
// receptionist can operate cash (open/close/movements) but not approve a close
// difference. The close-report panel's "Aprobar diferencia" button was only
// gated by canApproveDifference at the top warning banner, not in this second
// occurrence shown right after closing -- receptionist could see and click it.
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
  await movementForm.getByText("Descripcion", { exact: true }).locator("..").locator("input").fill("Venta de minibar QA");
  await movementForm.getByRole("button", { name: "Registrar movimiento", exact: true }).click();
  await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();

  const closeForm = page.locator("form").filter({ hasText: "Saldo esperado:" }).filter({ hasText: "Cerrar caja" });
  await closeForm.getByText("Saldo contado", { exact: true }).locator("..").locator("input").fill("0");
  await closeForm.getByRole("button", { name: "Cerrar caja", exact: true }).click();
  await expect(page.getByText("Caja cerrada.", { exact: true })).toBeVisible();
  await expect(page.getByText(/Estado: pendiente de aprobacion/, { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Aprobar diferencia", exact: true })).toHaveCount(0);
});
