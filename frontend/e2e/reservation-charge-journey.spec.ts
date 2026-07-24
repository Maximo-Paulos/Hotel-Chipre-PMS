import { expect, test, type Page } from "@playwright/test";

const credentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

const localIsoDate = (offsetDays: number) => {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
};

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

async function navigateFromShell(page: Page, path: string) {
  const desktopLink = page.locator(`aside nav a[href="${path}"]`);
  const mobileLink = page.locator(`nav[aria-label="Navegación móvil"] a[href="${path}"]`);
  const link = (await desktopLink.isVisible().catch(() => false)) ? desktopLink : mobileLink;
  await expect(link).toHaveCount(1);
  await link.click();
  await expect(page).toHaveURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
}

test("owner records a reservation consumption from the guest stay file", async ({ page }) => {
  const suffix = Date.now().toString();
  const guestLastName = `Cargo ${suffix}`;

  await login(page);
  await navigateFromShell(page, "/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();

  const reservationForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await reservationForm.getByPlaceholder("Nombre").fill("Huésped");
  await reservationForm.getByPlaceholder("Apellido").fill(guestLastName);
  await reservationForm.getByPlaceholder("Email").fill(`charge.${suffix}@example.test`);
  await reservationForm.getByPlaceholder("Teléfono").fill("1112345678");
  await reservationForm.getByLabel("Tipo de documento").selectOption("DNI");
  await reservationForm.getByPlaceholder("Documento").fill(`CHG-${suffix}`);
  await reservationForm.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = reservationForm.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  await categorySelect.selectOption((await categoryOption.getAttribute("value"))!);
  await reservationForm.locator("label").filter({ hasText: "Check-in" }).locator('input[type="date"]').fill(localIsoDate(30));
  await reservationForm.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]').fill(localIsoDate(32));

  const createButton = reservationForm.getByRole("button", { name: "Crear", exact: true });
  await expect(createButton).toBeEnabled();
  await createButton.click();
  await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();

  const reservationRow = page.locator("table").filter({ hasText: "Código" }).locator("tbody tr").filter({ hasText: guestLastName });
  await expect(reservationRow).toHaveCount(1);
  await reservationRow.getByRole("button", { name: "Ficha", exact: true }).click();

  const detailsModal = page.locator("div.fixed").filter({ hasText: "Consumos y cargos" });
  await expect(detailsModal).toBeVisible();
  const chargeRegion = detailsModal.getByRole("region", { name: "Consumos y cargos" });
  await expect(chargeRegion).toContainText("Todavía no hay consumos cargados.");
  await chargeRegion.getByLabel("Detalle del consumo").fill("Desayuno y minibar");
  await chargeRegion.getByLabel("Importe").fill("1250.50");
  await chargeRegion.getByRole("button", { name: "Cargar consumo", exact: true }).click();

  await expect(page.getByText("Consumo cargado a la reserva.", { exact: true })).toBeVisible();
  await expect(chargeRegion).toContainText("Desayuno y minibar");
  await expect(chargeRegion).toContainText("Saldo operativo:");

  await detailsModal.getByRole("button", { name: "Cerrar", exact: true }).last().click();
  await reservationRow.getByRole("button", { name: "Ficha", exact: true }).click();
  const reopenedModal = page.locator("div.fixed").filter({ hasText: "Consumos y cargos" });
  await expect(reopenedModal.getByRole("region", { name: "Consumos y cargos" })).toContainText("Desayuno y minibar");
});
