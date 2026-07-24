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

test("owner creates a guest and records a documented companion from the guest file", async ({ page }) => {
  const suffix = Date.now().toString();
  const guestLastName = "Acompañante " + suffix;
  const companionLastName = "Vínculo " + suffix;
  const guestDocument = "GUEST-" + suffix;
  const companionDocument = "COMP-" + suffix;

  await login(page);
  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();

  const reservationForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await reservationForm.getByPlaceholder("Nombre").fill("Huésped");
  await reservationForm.getByPlaceholder("Apellido").fill(guestLastName);
  await reservationForm.getByPlaceholder("Email").fill("guest." + suffix + "@example.test");
  await reservationForm.getByPlaceholder("Teléfono").fill("1112345678");
  await reservationForm.getByLabel("Tipo de documento").selectOption("DNI");
  await reservationForm.getByPlaceholder("Documento").fill(guestDocument);
  await reservationForm.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Cerrar", exact: true }).last().click();
  await page.goto("/huespedes");

  await page.getByPlaceholder("Buscar por nombre, documento o email").fill(guestLastName);
  const guestButton = page.getByRole("button", { name: new RegExp(guestLastName) });
  await expect(guestButton).toBeVisible();
  await guestButton.click();

  const companionForm = page.locator("form").filter({ hasText: "Agregar acompañante" });
  await expect(companionForm).toBeVisible();
  await companionForm.getByText("Nombre", { exact: true }).locator("..").locator("input").fill("Compañero");
  await companionForm.getByText("Apellido", { exact: true }).locator("..").locator("input").fill(companionLastName);
  await companionForm.getByText("Relación", { exact: true }).locator("..").locator("input").fill("pareja");
  await companionForm.getByText("Número de documento", { exact: true }).locator("..").locator("input").fill(companionDocument);
  await companionForm.getByRole("button", { name: "Agregar acompañante", exact: true }).click();

  await expect(page.getByText("Compañero " + companionLastName, { exact: true })).toBeVisible();
  await expect(page.getByText("DNI - " + companionDocument, { exact: true })).toBeVisible();
  await expect(page.getByText("pareja", { exact: true })).toBeVisible();
});
