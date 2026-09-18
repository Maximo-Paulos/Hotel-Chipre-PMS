import { expect, test } from "@playwright/test";

test("password recovery completes MFA instead of treating its challenge as an invalid login response", async ({ page }) => {
  const calls: Array<{ path: string; body: Record<string, unknown> | null }> = [];

  await page.route("**/api/auth/request-reset", async (route) => {
    calls.push({ path: "/api/auth/request-reset", body: route.request().postDataJSON() });
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ sent: true }) });
  });
  await page.route("**/api/auth/reset-password", async (route) => {
    calls.push({ path: "/api/auth/reset-password", body: route.request().postDataJSON() });
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ requires_mfa: true, mfa_token: "synthetic-reset-mfa", expires_in: 300 })
    });
  });
  await page.route("**/api/auth/login/mfa", async (route) => {
    calls.push({ path: "/api/auth/login/mfa", body: route.request().postDataJSON() });
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: "synthetic-access-token",
        token_type: "bearer",
        hotel_id: 1,
        hotel_ids: [1],
        csrf_token: "synthetic-csrf-token",
        requires_verification: false,
        permissions: ["dashboard:view"],
        user: {
          id: 17,
          email: "google-only@example.test",
          role: "owner",
          is_verified: true,
          is_active: true,
          password_login_enabled: true,
          permissions: ["dashboard:view"]
        }
      })
    });
  });

  await page.goto("/reset-password");
  await page.getByLabel("Email", { exact: true }).fill("google-only@example.test");
  await page.getByRole("button", { name: "Enviar código" }).click();
  await expect(page.getByText("Enviamos el código si el correo existe.")).toBeVisible();

  await page.getByLabel("Código recibido").fill("123456");
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.getByLabel("Nueva contraseña").fill("NewHotelsPmsPass123!");
  await page.getByLabel("Confirmar contraseña").fill("NewHotelsPmsPass123!");
  await page.getByRole("button", { name: "Guardar nueva contraseña" }).click();

  await expect(page.getByText(/La contraseña quedó actualizada/)).toBeVisible();
  await expect(page.getByText(/Abrí la app autenticadora que vinculaste/)).toBeVisible();
  await page.getByLabel("Código de la app autenticadora o de recuperación").fill("654321");
  await page.getByRole("button", { name: "Verificar y continuar" }).click();
  await expect(page.getByText("Contraseña actualizada. Redirigiendo al login.", { exact: true })).toBeVisible();

  expect(calls).toEqual([
    { path: "/api/auth/request-reset", body: { email: "google-only@example.test" } },
    {
      path: "/api/auth/reset-password",
      body: { email: "google-only@example.test", code: "123456", new_password: "NewHotelsPmsPass123!" }
    },
    { path: "/api/auth/login/mfa", body: { mfa_token: "synthetic-reset-mfa", code: "654321" } }
  ]);
});

test("an incorrect reset MFA code preserves the current session and accepts an alphanumeric recovery code", async ({ page }) => {
  const calls: string[] = [];

  await page.route("**/api/auth/request-reset", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ sent: true }) });
  });
  await page.route("**/api/auth/reset-password", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ requires_mfa: true, mfa_token: "synthetic-reset-mfa", expires_in: 300 })
    });
  });
  await page.route("**/api/auth/login/mfa", async (route) => {
    calls.push("mfa");
    await route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Código inválido" }) });
  });
  await page.route("**/api/auth/session/refresh", async (route) => {
    calls.push("refresh");
    await route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Sesión expirada" }) });
  });

  await page.goto("/reset-password");
  await page.getByLabel("Email", { exact: true }).fill("google-only@example.test");
  await page.getByRole("button", { name: "Enviar código" }).click();
  await page.getByLabel("Código recibido").fill("123456");
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.getByLabel("Nueva contraseña").fill("NewHotelsPmsPass123!");
  await page.getByLabel("Confirmar contraseña").fill("NewHotelsPmsPass123!");
  await page.getByRole("button", { name: "Guardar nueva contraseña" }).click();
  await expect(page.getByText(/La contraseña quedó actualizada/)).toBeVisible();
  calls.length = 0;

  await page.evaluate(async () => {
    const moduleUrl = new URL("/src/api/client.ts", window.location.origin).toString();
    const client = await import(moduleUrl);
    client.setClientSession({
      hotelId: 1,
      userId: "existing@example.test",
      accessToken: "synthetic-existing-session",
      csrfToken: "synthetic-csrf-token"
    });
  });

  const mfaCode = page.getByLabel("Código de la app autenticadora o de recuperación");
  await expect(mfaCode).toHaveAttribute("inputmode", "text");
  await mfaCode.fill("ABCDEF123456");
  await page.getByRole("button", { name: "Verificar y continuar" }).click();

  await expect(page.getByRole("alert")).toHaveText("Código inválido");
  await expect(page).toHaveURL(/\/reset-password$/);
  expect(calls).toEqual(["mfa"]);
});
