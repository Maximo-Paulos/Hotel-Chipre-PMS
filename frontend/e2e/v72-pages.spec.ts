import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";

const credentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

async function login(page: Page) {
  await page.goto("/login");
  // Labels are not associated to inputs (no htmlFor/id), so select by input type.
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

async function visitAndCapture(page: Page, path: string, screenshotName: string) {
  await page.goto(path);
  await page.screenshot({ path: `e2e/screenshots/${screenshotName}.png`, fullPage: true });
}

test.describe("V72 authenticated pages", () => {
  test.beforeAll(() => {
    mkdirSync("e2e/screenshots", { recursive: true });
  });

  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("Caja renders the live cash-register area", async ({ page }) => {
    await visitAndCapture(page, "/caja", "caja");
    await expect(page.getByRole("heading", { name: "Caja" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Turnos de caja" })).toBeVisible();
  });

  test("Empresas renders the companies endpoint area", async ({ page }) => {
    await visitAndCapture(page, "/settings/companies", "empresas");
    await expect(page.getByRole("heading", { name: "Empresas" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Empresas \(/ })).toBeVisible();
  });

  test("Reportes renders the operational report area", async ({ page }) => {
    await visitAndCapture(page, "/reportes", "reportes");
    await expect(page.getByRole("heading", { name: "Reportes" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Estado operativo" })).toBeVisible();
  });

  test("Lista de espera renders waitlist entries", async ({ page }) => {
    await visitAndCapture(page, "/operacion/lista-espera", "lista-espera");
    await expect(page.getByRole("heading", { name: "Lista de espera" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Entradas \(/ })).toBeVisible();
  });

  test("Lavanderia renders laundry batches", async ({ page }) => {
    await visitAndCapture(page, "/operacion/lavanderia", "lavanderia");
    await expect(page.getByRole("heading", { name: "Lavanderia" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Lavanderia \(/ })).toBeVisible();
  });

  test("Stock renders inventory controls", async ({ page }) => {
    await visitAndCapture(page, "/operacion/stock", "stock");
    await expect(page.getByRole("heading", { name: "Stock" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Items \(/ })).toBeVisible();
  });

  test("API Keys renders hotel key management", async ({ page }) => {
    await visitAndCapture(page, "/settings/api-keys", "api-keys");
    await expect(page.getByRole("heading", { name: "API Keys" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Emitir nueva API Key" })).toBeVisible();
  });

  test("Permisos renders the role matrix", async ({ page }) => {
    await visitAndCapture(page, "/settings/permissions", "permisos");
    await expect(page.getByRole("heading", { name: "Permisos" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Matriz por rol" })).toBeVisible();
  });

  test("WhatsApp renders integration settings", async ({ page }) => {
    await visitAndCapture(page, "/settings/whatsapp", "whatsapp");
    await expect(page.getByRole("heading", { name: "WhatsApp" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Conexion WhatsApp Business" })).toBeVisible();
  });

  test("RoomsPage renders the bloqueos section", async ({ page }) => {
    await visitAndCapture(page, "/habitaciones", "habitaciones-bloqueos");
    await expect(page.getByRole("heading", { name: "Habitaciones" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Bloqueos activos \(/ })).toBeVisible();
  });

  test("ReservationsPage renders the asignacion section", async ({ page }) => {
    await visitAndCapture(page, "/reservas", "reservas-asignacion");
    await expect(page.getByRole("heading", { name: "Reservas" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Recalculo y movimientos" })).toBeVisible();
  });

  test("GuestsPage renders guest tags", async ({ page }) => {
    await visitAndCapture(page, "/huespedes", "huespedes-tags");
    await expect(page.getByRole("heading", { name: "Ficha de huéspedes" })).toBeVisible();
    await expect(page.getByText("Etiquetas activas")).toBeVisible();
  });
});
