import { expect, test } from "@playwright/test";
import { readFileSync, rmSync, unlinkSync } from "node:fs";
import os from "node:os";
import path from "node:path";

const emailOutboxPath = path.join(os.tmpdir(), "hotel-chipre-e2e-email-outbox.jsonl");

function readLatestCode(email: string, subjectPattern: RegExp): string {
  if (!emailOutboxPath) throw new Error("El outbox local de E2E no está configurado");

  let raw = "";
  try {
    raw = readFileSync(emailOutboxPath, "utf8");
  } catch {
    return "";
  }
  const messages = raw
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line) as { to?: string[]; subject?: string; body?: string })
    .filter((message) => message.to?.includes(email) && subjectPattern.test(message.subject ?? ""));
  const body = messages.at(-1)?.body ?? "";
  const code = body.match(/\b\d{6}\b/)?.[0];
  return code ?? "";
}

async function waitForCode(email: string, subjectPattern: RegExp): Promise<string> {
  await expect.poll(() => readLatestCode(email, subjectPattern), { timeout: 10_000 }).toMatch(/^\d{6}$/);
  return readLatestCode(email, subjectPattern);
}

async function saveAndExpectPath(page: Page, path: string) {
  await page.getByRole("button", { name: "Guardar y seguir", exact: true }).click();
  await page.waitForURL(`**${path}`, { timeout: 15_000 });
}

test.beforeAll(() => {
  if (emailOutboxPath) rmSync(emailOutboxPath, { force: true });
});

test.afterAll(() => {
  if (emailOutboxPath) {
    try {
      unlinkSync(emailOutboxPath);
    } catch {
      // The file may not exist when the test was interrupted before email delivery.
    }
  }
});

test("owner can register, verify, recover access and complete onboarding through the UI", async ({ page }) => {
  const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const email = `qa-onboarding-${suffix}@example.test`;
  const initialPassword = "QaOnboarding1234!";
  const recoveredPassword = "QaRecovered1234!";
  const hotelName = `Hotel QA ${suffix}`;
  const categoryCode = `QA${suffix.replace(/[^a-z0-9]/gi, "").slice(-8).toUpperCase()}`;
  const roomNumber = `9${suffix.replace(/[^0-9]/g, "").slice(-3)}`;

  await page.goto("/register-owner");
  await page.getByLabel("Nombre", { exact: true }).fill("Luna");
  await page.getByLabel("Apellido", { exact: true }).fill("QA");
  await page.getByLabel("Email corporativo", { exact: true }).fill(email);
  await page.getByLabel("Teléfono", { exact: true }).fill("+54 9 11 5555 0101");
  await page.getByLabel("Contraseña", { exact: true }).fill(initialPassword);
  await page.getByRole("button", { name: "Crear cuenta y verificar email", exact: true }).click();
  await page.waitForURL("**/verify-email", { timeout: 15_000 });

  const verificationCode = await waitForCode(email, /Verifica tu cuenta/i);
  await page.getByLabel("Codigo", { exact: true }).fill(verificationCode);
  await page.getByRole("button", { name: "Verificar codigo", exact: true }).click();
  await page.waitForURL("**/onboarding", { timeout: 15_000 });

  await saveAndExpectPath(page, "/onboarding/identity");

  await page.getByLabel("Nombre del hotel", { exact: true }).fill(hotelName);
  await saveAndExpectPath(page, "/onboarding/categories");

  await page.getByRole("button", { name: "+ Agregar categoría", exact: true }).click();
  await page.getByLabel("Nombre de categoría", { exact: true }).fill("Standard QA");
  await page.getByLabel("Código interno", { exact: true }).fill(categoryCode);
  await page.getByLabel("Amenities", { exact: true }).fill("wifi, aire acondicionado");
  await page.getByLabel("Precio base por noche", { exact: true }).fill("65000");
  await page.getByLabel("Ocupación máxima", { exact: true }).fill("2");
  await page.getByLabel("Descripción breve", { exact: true }).fill("Categoría de prueba sintética");
  await saveAndExpectPath(page, "/onboarding/rooms");

  await page.getByRole("button", { name: "+ Agregar habitación", exact: true }).click();
  await page.getByLabel("Número de habitación", { exact: true }).fill(roomNumber);
  await page.getByLabel("Piso", { exact: true }).fill("1");
  await page.getByRole("combobox", { name: "Categoría", exact: true }).selectOption({
    label: `Standard QA (${categoryCode})`
  });
  await saveAndExpectPath(page, "/onboarding/policy");

  await saveAndExpectPath(page, "/onboarding/payments");

  const mercadoPagoCheckbox = page.getByRole("checkbox", { name: "Mercado Pago", exact: true });
  if (!(await mercadoPagoCheckbox.isChecked())) {
    await mercadoPagoCheckbox.check();
  }
  await expect(mercadoPagoCheckbox).toBeChecked();
  await saveAndExpectPath(page, "/onboarding/ota");

  await saveAndExpectPath(page, "/onboarding/subscription");
  await saveAndExpectPath(page, "/onboarding/staff");

  await page.getByRole("button", { name: "+ Agregar staff", exact: true }).click();
  await page.getByLabel("Nombre", { exact: true }).fill("Recepción QA");
  await page.getByLabel("Rol", { exact: true }).fill("Reception");
  await page.getByLabel("Email", { exact: true }).fill(`reception-${suffix}@example.test`);
  await saveAndExpectPath(page, "/onboarding/finish");

  await expect(page.getByRole("button", { name: "Marcar onboarding como completo", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Marcar onboarding como completo", exact: true }).click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
  await expect(page.getByText(`Usuario ${email}`, { exact: true })).toBeVisible();

  await page.getByTestId("logout-btn").click();
  await page.waitForURL("**/login", { timeout: 15_000 });
  await page.getByRole("link", { name: /Olvidé mi contraseña/i }).click();
  await page.waitForURL("**/reset-password", { timeout: 15_000 });
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByRole("button", { name: "Enviar código", exact: true }).click();

  const resetCode = await waitForCode(email, /Recupera tu acceso/i);
  await page.getByLabel("Código recibido", { exact: true }).fill(resetCode);
  await page.getByRole("button", { name: "Continuar", exact: true }).click();
  await page.getByLabel("Nueva contraseña", { exact: true }).fill(recoveredPassword);
  await page.getByLabel("Confirmar contraseña", { exact: true }).fill(recoveredPassword);
  await page.getByRole("button", { name: "Guardar nueva contraseña", exact: true }).click();
  await expect(page.getByText("Contraseña actualizada. Redirigiendo al login.", { exact: true })).toBeVisible();
  await page.waitForURL("**/login", { timeout: 15_000 });

  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(recoveredPassword);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
  await expect(page.getByText(`Usuario ${email}`, { exact: true })).toBeVisible();
});
