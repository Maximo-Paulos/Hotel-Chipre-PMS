import { expect, test, type Page } from "@playwright/test";

// Functional journey for the GuestRestriction feature (formal lodging
// prohibition, distinct from the legacy "prohibido_alojar" GuestTag):
// owner creates a restriction on a guest -> the badge shows up on guest
// search/list -> price-quote and reservation create both 409 with
// GUEST_PROHIBITED -> the override modal collects a mandatory reason and
// the retried request succeeds -> resolving the restriction clears the
// badge. Uses the owner persona (has guest:prohibition_manage and
// reservation:prohibition_override by default -- see
// app/services/permission_service.py DEFAULT_MATRIX).
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

test("owner creates a lodging restriction, it blocks booking, override unblocks it, and resolving clears the badge", async ({
  page
}) => {
  const suffix = Date.now().toString();
  const guestLastName = `QA-Restriccion ${suffix}`;
  const checkIn = localIsoDate(120);
  const checkOut = localIsoDate(122);

  await login(page);

  // Create the guest from the reservation quick-create panel.
  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  const createForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(createForm).toBeVisible();
  await createForm.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
  await createForm.getByPlaceholder("Nombre").fill("Huésped");
  await createForm.getByPlaceholder("Apellido").fill(guestLastName);
  await createForm.getByPlaceholder("Email").fill(`restriccion.${suffix}@example.test`);
  await createForm.getByPlaceholder("Teléfono").fill("1112345678");
  await createForm.getByLabel("Tipo de documento").selectOption("DNI");
  await createForm.getByPlaceholder("Documento").fill(`RESTR-${suffix}`);
  await createForm.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Cerrar", exact: true }).last().click();

  // Create a restriction on the guest from the guest file.
  await page.goto("/huespedes");
  await page.getByPlaceholder("Buscar por nombre, documento o email").fill(guestLastName);
  const guestButton = page.getByRole("button", { name: new RegExp(guestLastName) });
  await expect(guestButton).toBeVisible();
  await guestButton.click();

  const restrictionsPanel = page.getByTestId("guest-restrictions-panel");
  await expect(restrictionsPanel).toBeVisible();
  await restrictionsPanel.getByTestId("guest-restriction-reason-input").fill("Cheque rechazado en estadía anterior");
  await restrictionsPanel.getByTestId("guest-restriction-create-submit").click();
  await expect(page.getByText("Restricción creada.", { exact: true })).toBeVisible();
  await expect(page.locator('[data-testid^="guest-restriction-badge-"]').first()).toBeVisible();

  // A fresh reservation form for this restricted guest must 409 on the
  // auto-priced quote and block "Crear" until a manual total is entered.
  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  const reservationForm = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(reservationForm).toBeVisible();

  await reservationForm.getByTestId("guest-search-input").fill(guestLastName);
  const searchResult = reservationForm.locator('[data-testid^="guest-search-result-"]').first();
  await expect(searchResult).toBeVisible();
  // The restriction badge must show on the search result row itself.
  await expect(searchResult.locator('[data-testid^="guest-restriction-badge-"]')).toBeVisible();
  await searchResult.click();
  await reservationForm.getByTestId("guest-confirm-button").click();
  await expect(reservationForm.getByTestId("guest-confirm-card").locator('[data-testid^="guest-restriction-badge-"]')).toBeVisible();

  const categorySelect = reservationForm.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  const categoryValue = await categoryOption.getAttribute("value");
  expect(categoryValue).toBeTruthy();
  await categorySelect.selectOption(categoryValue!);
  await reservationForm.locator("label").filter({ hasText: "Check-in" }).locator('input[type="date"]').fill(checkIn);
  await reservationForm.locator("label").filter({ hasText: "Check-out" }).locator('input[type="date"]').fill(checkOut);

  await expect(reservationForm.getByText(/restricción de alojamiento activa/i)).toBeVisible();
  await expect(reservationForm.getByRole("button", { name: "Crear", exact: true })).toBeDisabled();

  // Manual total skips the quote_token requirement -- "Crear reserva" itself
  // still enforces the restriction and surfaces the override modal.
  await reservationForm.locator("label").filter({ hasText: "Monto total manual" }).locator("input").fill("15000");
  await expect(reservationForm.getByRole("button", { name: "Crear", exact: true })).toBeEnabled();
  await reservationForm.getByRole("button", { name: "Crear", exact: true }).click();

  const overrideModal = page.getByRole("dialog", { name: "Huésped con restricción activa" });
  await expect(overrideModal).toBeVisible();
  await expect(overrideModal.getByTestId("restriction-override-submit")).toBeDisabled();
  await overrideModal.getByTestId("restriction-override-reason").fill("Autorizado por gerencia -- override QA");
  await expect(overrideModal.getByTestId("restriction-override-submit")).toBeEnabled();
  await overrideModal.getByTestId("restriction-override-submit").click();

  await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();

  // Resolve the restriction and confirm the badge disappears from the guest file.
  await page.goto("/huespedes");
  await page.getByPlaceholder("Buscar por nombre, documento o email").fill(guestLastName);
  await page.getByRole("button", { name: new RegExp(guestLastName) }).click();
  const activePanel = page.getByTestId("guest-restrictions-panel");
  await activePanel.locator('[data-testid^="guest-restriction-resolve-"]').first().click();
  await activePanel.getByRole("button", { name: "Confirmar resolución", exact: true }).click();
  await expect(page.getByText("Restricción resuelta.", { exact: true })).toBeVisible();
  await expect(page.locator('[data-testid^="guest-restriction-badge-"]')).toHaveCount(0);
});

test("receptionist without guest:prohibition_manage never sees the create/resolve UI", async ({ page }) => {
  // The receptionist persona has guest:prohibition_read but not
  // guest:prohibition_manage by default (see DEFAULT_MATRIX) -- the
  // create/resolve panel must never render for them, even on a guest file
  // they're otherwise allowed to open.
  const receptionist = {
    email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
    password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!"
  };
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(receptionist.email);
  await page.locator('input[type="password"]').fill(receptionist.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });

  await page.goto("/huespedes");
  const guestsSection = page.locator("section").filter({ hasText: "Huéspedes del hotel" });
  const firstGuestButton = guestsSection.locator("button").first();
  await expect(firstGuestButton).toBeVisible();
  await firstGuestButton.click();
  await expect(page.getByTestId("guest-restrictions-panel")).toHaveCount(0);
});
