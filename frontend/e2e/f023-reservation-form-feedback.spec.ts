import { expect, test } from "@playwright/test";

const owner = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

const localIsoDate = (offsetDays: number) => {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
};

test("F-023: guest selection assigns once, quote locks inputs, and errors stay by submit", async ({ page }) => {
  const suffix = `${Date.now()}`;
  let releaseQuote!: () => void;
  let markQuoteRequested!: () => void;
  const quoteGate = new Promise<void>((resolve) => { releaseQuote = resolve; });
  const quoteRequested = new Promise<void>((resolve) => { markQuoteRequested = resolve; });

  await page.route("**/api/bookings/price-quote**", async (route) => {
    markQuoteRequested();
    await quoteGate;
    await route.continue();
  });
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(owner.email);
  await page.locator('input[type="password"]').fill(owner.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard");
  await page.goto("/reservas");
  await expect(page.getByLabel("Categoría para disponibilidad")).toBeVisible();
  await expect(page.getByLabel("Check-in para disponibilidad")).toBeVisible();
  await expect(page.getByLabel("Check-out para disponibilidad")).toBeVisible();
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();

  const form = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await form.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
  await form.getByPlaceholder("Nombre").fill("F023");
  await form.getByPlaceholder("Apellido").fill(`Reproduccion-${suffix}`);
  await form.getByPlaceholder("Email").fill(`f023.${suffix}@example.test`);
  await form.getByPlaceholder("Teléfono").fill(`11${Date.now().toString().slice(-8)}${Math.floor(Math.random() * 100).toString().padStart(2, "0")}`);
  await form.getByLabel("Tipo de documento").selectOption("DNI");
  await form.getByPlaceholder("Documento").fill(`F023-${suffix}`);
  await form.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(form.getByTestId("guest-confirm-card")).toContainText(`Reproduccion-${suffix}`);
  await form.getByTestId("guest-change-button").click();

  const guestSearch = form.getByPlaceholder("Buscar por nombre, documento o email");
  await guestSearch.fill(`Reproduccion-${suffix}`);
  const result = form.getByTestId("guest-search-results").getByRole("button").filter({ hasText: `Reproduccion-${suffix}` });
  await expect(result).toBeVisible({ timeout: 5_000 });
  await result.click();

  const categorySelect = form.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  await categorySelect.selectOption((await categoryOption.getAttribute("value"))!);
  const checkIn = form.getByLabel("Check-in", { exact: true });
  const checkOut = form.getByLabel("Check-out", { exact: true });
  await checkIn.fill(localIsoDate(500));
  await checkOut.fill(localIsoDate(502));
  await quoteRequested;

  await expect(form.getByTestId("guest-confirm-button")).toHaveCount(0);
  await expect(form.getByTestId("guest-confirm-card")).toContainText(`Reproduccion-${suffix}`);
  await expect(guestSearch).toBeHidden();
  await expect(checkIn).toBeDisabled();
  releaseQuote();
  await expect(form.getByRole("button", { name: "Crear", exact: true })).toBeEnabled();
  const createResponse = page.waitForResponse((response) =>
    response.url().includes("/api/reservations") && response.request().method() === "POST"
  );
  await form.getByRole("button", { name: "Crear", exact: true }).click();
  expect((await createResponse).status()).toBe(201);
  await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  const emptyGuestForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  const emptyGuestCategory = emptyGuestForm.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const standardOption = emptyGuestCategory.locator("option").filter({ hasText: "Standard E2E" });
  await emptyGuestCategory.selectOption((await standardOption.getAttribute("value"))!);
  await emptyGuestForm.getByLabel("Check-in", { exact: true }).fill(localIsoDate(510));
  await emptyGuestForm.getByLabel("Check-out", { exact: true }).fill(localIsoDate(512));
  const emptyGuestCreateButton = emptyGuestForm.getByRole("button", { name: "Crear", exact: true });
  await expect(emptyGuestCreateButton).toBeEnabled();
  await emptyGuestCreateButton.click();
  const submitError = emptyGuestForm.getByTestId("reservation-submit-error");
  await expect(submitError).toHaveAttribute("role", "alert");
  await expect(submitError).toContainText(/Ingresá el ID del huésped o completá/);
  await expect(emptyGuestForm.getByRole("alert")).toHaveCount(1);
});
