import { expect, test, type Page, type TestInfo } from "@playwright/test";

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

// The 3 webkit-*-business Apple device projects share one SQLite database
// and run this exact spec concurrently, auto-assigning the same 2 rooms of
// the seeded E2E category for the same relative dates. A per-project date
// salt gives each device project its own calendar days so the room
// allocation can never race, instead of relying on timing between a create
// and a later cleanup cancel.
const projectDateSalt = (testInfo: TestInfo) => {
  const name = testInfo.project.name;
  if (name.includes("pro-max")) return 300;
  if (name.includes("iphone-se")) return 200;
  if (name.includes("iphone-15")) return 100;
  return 0;
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
  if (await desktopLink.isVisible().catch(() => false)) {
    await expect(desktopLink).toHaveCount(1);
    await desktopLink.click();
    await expect(page).toHaveURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
    return;
  }
  // B7: on mobile the whole nav lives inside a slide-over panel opened via
  // the hamburger button -- open it before looking for the link.
  const menuButton = page.getByTestId("mobile-menu-button");
  if (await menuButton.isVisible().catch(() => false)) {
    await menuButton.click();
  }
  const mobileLink = page.locator(`nav[aria-label="Navegación móvil"] a[href="${path}"]`);
  await expect(mobileLink).toHaveCount(1);
  await mobileLink.click();
  await expect(page).toHaveURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
}

test("owner records a reservation consumption from the guest stay file", async ({ page }, testInfo) => {
  const salt = projectDateSalt(testInfo);
  // WebKit clamps Date.now() precision, so concurrent device projects can
  // get the exact same millisecond suffix. Append the (already per-project
  // unique) date salt to keep guest names unique too.
  const suffix = `${Date.now()}-${salt}`;
  const guestLastName = `Cargo ${suffix}`;

  await login(page);
  await navigateFromShell(page, "/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();

  const reservationForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await reservationForm.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
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
  await reservationForm.locator("label").filter({ hasText: "Check-in" }).locator('input[type="date"]').fill(localIsoDate(30 + salt));
  await reservationForm.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]').fill(localIsoDate(32 + salt));

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

  // Cleanup: this test's reservation is left pinned on localIsoDate(30..32)
  // with an auto-assigned room from the 2-room seeded E2E category. The
  // WebKit Apple business matrix reruns this exact spec once per device
  // project against the shared database, so leaving it pending would make
  // the next device run fail room availability with a false "no rooms
  // available" negative. Cancel it to free the room for the next run.
  await reopenedModal.getByRole("button", { name: "Cerrar", exact: true }).last().click();
  await reservationRow.getByRole("button", { name: "Cancelar", exact: true }).click();
  await expect(page.getByText("Reserva cancelada", { exact: true })).toBeVisible();
});
