import { expect, test, type Page } from "@playwright/test";

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

function parseMoney(text: string) {
  return Number(text.replace(/[^0-9,.-]/g, "").replace(/\./g, "").replace(",", "."));
}

test("owner controls manual cash movements, approves an arqueo difference and confirms custody", async ({ page }) => {
  await login(page);
  await page.goto("/caja");

  const openingForm = page.locator("form").filter({ hasText: "Saldo inicial" }).filter({ hasText: "Abrir caja" });
  const openButton = page.getByRole("button", { name: "Abrir caja", exact: true });
  const existingOpenButton = page.getByRole("button", { name: "Ya hay una caja abierta", exact: true });
  await expect
    .poll(
      async () => {
        if (await existingOpenButton.count()) return "already-open";
        if (await openButton.count()) return "can-open";
        return "loading";
      },
      { timeout: 15_000 }
    )
    .toMatch(/^(already-open|can-open)$/);
  if (!(await existingOpenButton.count())) {
    await openingForm.getByText("Saldo inicial", { exact: true }).locator("..").locator("input").fill("1000");
    await openButton.click();
    await expect(page.getByText("Caja abierta.", { exact: true })).toBeVisible();
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
