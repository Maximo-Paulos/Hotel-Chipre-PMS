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
  await expect(page.getByText(`Usuario ${credentials.email}`)).toBeVisible();
}

async function navigateFromShell(page: Page, path: string) {
  const link = page.locator(`aside nav a[href="${path}"]`);
  await expect(link).toHaveCount(1);
  await expect(link).toBeVisible();
  await link.click();
  await expect(page).toHaveURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
}

test("owner completes the core reservation journey through the UI", async ({ page }) => {
  const suffix = Date.now().toString();
  const categoryName = `Journey ${suffix}`;
  const categoryCode = `J${suffix.slice(-6)}`;
  const roomNumber = `J${suffix.slice(-5)}`;
  const guestLastName = `Journey ${suffix}`;

  await login(page);

  await navigateFromShell(page, "/settings/hotel");
  await expect(page.getByRole("heading", { name: "Hotel", exact: true })).toBeVisible();

  await page.getByPlaceholder("Nombre").fill(categoryName);
  await page.getByPlaceholder("Código").fill(categoryCode);
  await page.getByPlaceholder("Precio base").fill("65000");
  await page.getByPlaceholder("Ocupación máx").fill("2");
  await page.getByPlaceholder("Amenidades").fill("wifi, aire acondicionado");
  await page.getByPlaceholder("Descripción").fill("Categoría de journey E2E");
  await page.getByRole("button", { name: "Agregar categoría", exact: true }).click();
  await expect(page.getByText(`${categoryName} (${categoryCode})`, { exact: true })).toBeVisible();

  const roomCategorySelect = page.locator("select").filter({ hasText: categoryName });
  await expect(roomCategorySelect).toHaveCount(1);
  await roomCategorySelect.selectOption({ label: categoryName });
  await page.getByPlaceholder("Número").fill(roomNumber);
  await page.getByPlaceholder("Piso").fill("2");
  await page.getByPlaceholder("Notas").fill("Habitación de journey E2E");
  await page.getByRole("button", { name: "Agregar habitación", exact: true }).click();
  await expect(page.getByText(`Hab ${roomNumber}`, { exact: false })).toBeVisible();

  await navigateFromShell(page, "/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  const reservationForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(reservationForm).toBeVisible();

  await reservationForm.getByPlaceholder("Nombre").fill("Huésped");
  await reservationForm.getByPlaceholder("Apellido").fill(guestLastName);
  await reservationForm.getByPlaceholder("Email").fill(`journey.${suffix}@example.test`);
  await reservationForm.getByPlaceholder("Teléfono").fill("1112345678");
  await reservationForm.getByLabel("Tipo de documento").selectOption("DNI");
  await reservationForm.getByPlaceholder("Documento").fill(`E2E-${suffix}`);
  await reservationForm.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = reservationForm.locator("label").filter({ hasText: "Categoría" }).locator("select");
  await expect(categorySelect).toHaveCount(1);
  const categoryOption = categorySelect.locator("option").filter({ hasText: categoryName });
  await expect(categoryOption).toHaveCount(1);
  const categoryValue = await categoryOption.getAttribute("value");
  expect(categoryValue).toBeTruthy();
  await categorySelect.selectOption(categoryValue!);

  const roomSelect = reservationForm.locator("label").filter({ hasText: "Habitación (opcional)" }).locator("select");
  await expect(roomSelect).toHaveCount(1);
  const roomOption = roomSelect.locator("option").filter({ hasText: roomNumber });
  await expect(roomOption).toHaveCount(1);
  const roomValue = await roomOption.getAttribute("value");
  expect(roomValue).toBeTruthy();
  await roomSelect.selectOption(roomValue!);

  const checkIn = reservationForm.locator("label").filter({ hasText: "Check-in" }).locator('input[type="date"]');
  const checkOut = reservationForm.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]');
  await checkIn.fill(localIsoDate(0));
  await checkOut.fill(localIsoDate(1));
  await reservationForm.getByPlaceholder("Usar configuración del hotel").fill("1000");

  await reservationForm.getByRole("button", { name: "Crear", exact: true }).click();
  await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();

  const reservationTable = page.locator("table").filter({ hasText: "Código" });
  const reservationRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await expect(reservationRow).toHaveCount(1);

  await reservationRow.getByRole("button", { name: "Editar", exact: true }).click();
  const editModal = page.locator("div.fixed").filter({ hasText: "Pagos y balance" });
  const editForm = editModal.locator("form").filter({ hasText: "Pagos y balance" });
  await expect(editForm.getByText("Resumen financiero y acciones rápidas.", { exact: true })).toBeVisible();
  const partialAmount = editForm.getByLabel("Monto a cobrar");
  await expect(partialAmount).toBeVisible();
  await partialAmount.fill("500");
  await editForm.getByRole("button", { name: "Cobro parcial", exact: true }).click();
  await expect(page.getByText("Cobro parcial registrado", { exact: true })).toBeVisible();
  await editForm.getByLabel("Medio de pago").selectOption("bank_transfer");
  await expect(editForm.getByLabel("Imagen del comprobante")).toBeVisible();
  await partialAmount.fill("500");
  await editForm.getByLabel("Imagen del comprobante").setInputFiles({
    name: "transfer-proof.png",
    mimeType: "image/png",
    buffer: Buffer.from(await page.evaluate((seed) => {
      const canvas = document.createElement("canvas");
      canvas.width = 1;
      canvas.height = 1;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Canvas no disponible para el fixture del comprobante");
      context.fillStyle = `hsl(${seed % 360} 70% 50%)`;
      context.fillRect(0, 0, 1, 1);
      return canvas.toDataURL("image/png").split(",")[1];
    }, Number(suffix.slice(-6))), "base64")
  });
  await editForm.getByRole("button", { name: "Enviar comprobante", exact: true }).click();
  await expect(page.getByText("Comprobante enviado para aprobación", { exact: true })).toBeVisible();
  await expect(editForm.getByText(/pending$/)).toBeVisible();
  await editForm.getByRole("button", { name: "Aprobar", exact: true }).click();
  await expect(editForm.getByText(/approved$/)).toBeVisible();
  await editForm.getByLabel("Medio de pago").selectOption("cash");
  await editForm.getByRole("button", { name: "Pago total", exact: true }).click();
  await expect(page.getByText("Pago completo registrado", { exact: true })).toBeVisible();
  await editModal.getByRole("button", { name: "Cerrar", exact: true }).click();

  const paidRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await paidRow.getByRole("button", { name: "Check-in", exact: true }).click();
  await expect(page.getByText("Check-in registrado", { exact: true })).toBeVisible();

  const checkedInRow = reservationTable.locator("tbody tr").filter({ hasText: guestLastName });
  await checkedInRow.getByRole("button", { name: "Check-out", exact: true }).click();
  await expect(page.getByText("Check-out registrado", { exact: true })).toBeVisible();
});
