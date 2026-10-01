import { expect, test, type Page } from "@playwright/test";

const invitationToken = "qa-invite-token";
const invitedEmail = "invitee@example.test";
const syntheticGoogleIdToken = "synthetic-google-id-token";

const authResponse = {
  access_token: "synthetic-access-token",
  token_type: "bearer",
  hotel_id: 42,
  hotel_ids: [42],
  user: {
    id: 7,
    email: invitedEmail,
    role: "manager",
    is_verified: true,
    is_active: true,
    password_login_enabled: false,
    permissions: ["dashboard:view"]
  },
  permissions: ["dashboard:view"],
  csrf_token: "synthetic-csrf-token"
};

const installGoogleStub = async (page: Page) => {
  await page.route("https://accounts.google.com/gsi/client", (route) => route.fulfill({
    status: 200,
    contentType: "application/javascript",
    body: `
      window.__qaGoogleCallback = null;
      window.google = { accounts: { id: {
        initialize: function (config) { window.__qaGoogleCallback = config.callback; },
        renderButton: function (parent) {
          var button = document.createElement("button");
          button.type = "button";
          button.textContent = "Continue with Google";
          button.addEventListener("click", function () {
            window.__qaGoogleCallback({ credential: "${syntheticGoogleIdToken}" });
          });
          parent.appendChild(button);
        }
      }}};
    `
  }));
};

const installApiMocks = async (
  page: Page,
  initialLogin = false,
  googleEnabled = Boolean(process.env.E2E_GOOGLE_CLIENT_ID)
) => {
  const calls: Array<{ path: string; body: Record<string, unknown> | null }> = [];
  const backendURL = process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040";

  await page.route(`${backendURL}/api/**`, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const body = method === "POST" || method === "PATCH" ? request.postDataJSON() as Record<string, unknown> : null;
    const json = (data: unknown, status = 200) => route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(data)
    });

    if (method === "GET" && path === "/api/auth/providers") {
      const clientId = googleEnabled ? process.env.E2E_GOOGLE_CLIENT_ID || null : null;
      return json({
        google: {
          enabled: Boolean(googleEnabled && clientId),
          client_id: clientId,
          self_signup_enabled: Boolean(clientId),
          allowed_domains: []
        }
      });
    }
    if (method === "POST" && path.endsWith("/api/auth/session/refresh")) {
      return json({ detail: "No active test session" }, 401);
    }
    if (method === "POST" && path === "/api/invitations/preview") {
      return json({ email: invitedEmail, role: "manager", hotel_name: "Hotel de prueba", inviter_email: "owner@example.test" });
    }
    if (method === "POST" && path === "/api/invitations/accept/google") {
      calls.push({ path, body });
      return json({ requires_mfa: true, mfa_token: "synthetic-mfa-challenge", expires_in: 300 });
    }
    if (method === "POST" && path === "/api/auth/login") {
      calls.push({ path, body });
      if (!initialLogin) return json({ detail: "Unexpected password login" }, 400);
      return json({ requires_mfa: true, mfa_token: "synthetic-mfa-challenge", expires_in: 300 });
    }
    if (method === "POST" && path === "/api/auth/login/mfa") {
      calls.push({ path, body });
      return json(authResponse);
    }
    if (method === "POST" && path === "/api/invitations/accept") {
      calls.push({ path, body });
      return json(authResponse);
    }
    if (method === "GET" && path === "/api/permissions/effective") {
      return json({ hotel_id: 42, role: "manager", permissions: ["dashboard:view"] });
    }
    if (method === "GET" && path.startsWith("/api/reservations/actions/pending")) {
      return json([]);
    }
    if (method === "GET" && path.startsWith("/api/reservations/")) {
      return json([]);
    }
    if (method === "GET" && path.startsWith("/api/rooms/")) {
      return json([]);
    }
    if (method === "GET" && path === "/api/config/") {
      return json({ id: 42, hotel_name: "Hotel de prueba", interface_language: "es", languages: ["es"] });
    }
    if (method === "GET" && path === "/api/subscription/status") {
      return json({ hotel_id: 42, status: "active", plan: "starter", room_limit: 15, rooms_in_use: 0, available_plans: [] });
    }
    if (path.includes("/api/notifications")) {
      return json({ items: [], unread_count: 0 });
    }
    return json({});
  });

  return calls;
};

test("Google invitation waits for MFA, then accepts the original invitation with the verified email", async ({ page }) => {
  test.skip(!process.env.E2E_GOOGLE_CLIENT_ID, "Set E2E_GOOGLE_CLIENT_ID to exercise the mocked Google button.");
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await installGoogleStub(page);
  const calls = await installApiMocks(page);

  await page.goto(`/invitations/accept#token=${invitationToken}`);
  expect(new URL(page.url()).search).toBe("");
  expect(new URL(page.url()).hash).toContain(invitationToken);
  await expect(page.getByText("Hotel de prueba")).toBeVisible();
  await expect(page.getByTestId("google-signin-button")).toBeVisible();
  await page.getByRole("button", { name: "Continue with Google" }).click();
  await expect(page.getByText(/Esta cuenta tiene activada la verificación en dos pasos/)).toBeVisible();
  await expect(page.getByText(/No te llegará por email/)).toBeVisible();
  await expect(page.getByLabel("Código de la app autenticadora o de recuperación")).toBeVisible();
  await expect(page.getByText(/La invitación seguirá pendiente hasta verificarlo/)).toBeVisible();

  await test.info().attach("google-invitation-mfa.png", {
    body: await page.screenshot(),
    contentType: "image/png"
  });

  await page.getByLabel("Código de la app autenticadora o de recuperación").fill("123456");
  await page.getByRole("button", { name: "Verificar y aceptar invitación" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  expect(calls.map((call) => call.path)).toEqual([
    "/api/invitations/accept/google",
    "/api/auth/login/mfa",
    "/api/invitations/accept"
  ]);
  expect(calls.every((call) => !call.path.includes(invitationToken))).toBe(true);
  expect(calls[0]?.body).toEqual({ token: invitationToken, id_token: syntheticGoogleIdToken });
  expect(calls[1]?.body).toEqual({ mfa_token: "synthetic-mfa-challenge", code: "123456" });
  expect(calls[2]?.body).toEqual({ token: invitationToken, email: invitedEmail });
  expect(pageErrors).toEqual([]);
});

test("password login returns to the invitation after MFA and accepts it automatically", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  const calls = await installApiMocks(page, true);

  await page.goto(`/invitations/accept#token=${invitationToken}`);
  await page.getByRole("link", { name: "Ingresá y aceptá" }).click();
  await expect(page).toHaveURL(/\/login#/);
  const loginUrl = new URL(page.url());
  expect(new URLSearchParams(loginUrl.hash.slice(1)).get("invitation")).toBe(invitationToken);

  await page.getByLabel("Email").fill(invitedEmail);
  await page.locator("#login-password").fill("synthetic-password-value");
  await page.getByTestId("login-submit").click();
  await expect(page.getByLabel("Código de la app autenticadora o de recuperación")).toBeVisible();
  await page.getByLabel("Código de la app autenticadora o de recuperación").fill("654321");
  await page.getByRole("button", { name: "Verificar y continuar" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  expect(calls.map((call) => call.path)).toEqual([
    "/api/auth/login",
    "/api/auth/login/mfa",
    "/api/invitations/accept"
  ]);
  expect(calls[0]?.body).toMatchObject({ email: invitedEmail, password: "synthetic-password-value" });
  expect(calls[1]?.body).toEqual({ mfa_token: "synthetic-mfa-challenge", code: "654321" });
  expect(calls[2]?.body).toEqual({ token: invitationToken, email: invitedEmail });
  expect(pageErrors).toEqual([]);
});

test("invitation acceptance hides Google instructions when Google login is disabled", async ({ page }) => {
  await installApiMocks(page, false, false);

  await page.goto(`/invitations/accept#token=${invitationToken}`);
  await expect(page.getByText("Hotel de prueba")).toBeVisible();
  await expect(page.getByTestId("google-signin-button")).toHaveCount(0);
  await expect(page.getByText(/Google/i)).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Primer acceso" })).toBeVisible();
  await expect(page.getByLabel("Contraseña nueva")).toBeVisible();
});

test("co-owner can invite staff and cannot manage the primary owner row", async ({ page }) => {
  const ownerEmail = "owner@example.test";
  const coOwnerEmail = "co-owner@example.test";
  const staffEmail = "staff@example.test";
  const createdInvitationToken = "qa-new-invite-token";
  const permissions = ["dashboard:view", "settings:users:view", "settings:users:manage"];
  const testOrigin = process.env.E2E_BASE_URL || "http://127.0.0.1:5173";
  const invitationUrl = new URL(`/invitations/accept#token=${createdInvitationToken}`, testOrigin).toString();
  const resentInvitationToken = "qa-resent-invite-token";
  const resentInvitationUrl = new URL(`/invitations/accept#token=${resentInvitationToken}`, testOrigin).toString();
  const backendURL = process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040";
  const calls: Array<{ path: string; method: string; body: Record<string, unknown> | null }> = [];
  let staffAlias = "Turno noche";
  let pendingInviteOpen = true;

  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async (text: string) => window.localStorage.setItem("qa-copied-invitation", text),
        readText: async () => window.localStorage.getItem("qa-copied-invitation") ?? ""
      }
    });
  });

  await page.route(`${backendURL}/api/**`, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const body = method === "POST" || method === "PATCH"
      ? request.postDataJSON() as Record<string, unknown>
      : null;
    if (["POST", "PATCH", "DELETE"].includes(method)) calls.push({ path, method, body });
    const json = (data: unknown, status = 200) => route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(data)
    });

    if (method === "GET" && path === "/api/auth/providers") {
      return json({
        google: { enabled: false, client_id: null, self_signup_enabled: false, allowed_domains: [] }
      });
    }
    if (method === "POST" && path.endsWith("/api/auth/session/refresh")) {
      return json({ detail: "No active test session" }, 401);
    }
    if (method === "POST" && path === "/api/auth/login") {
      return json({
        access_token: "synthetic-co-owner-access-token",
        token_type: "bearer",
        hotel_id: 42,
        hotel_ids: [42],
        user: {
          id: 2,
          email: coOwnerEmail,
          role: "co_owner",
          is_verified: true,
          is_active: true,
          password_login_enabled: true,
          permissions
        },
        permissions,
        csrf_token: "synthetic-co-owner-csrf-token"
      });
    }
    if (method === "GET" && path === "/api/onboarding/status") {
      return json({ completed: true });
    }
    if (method === "GET" && path.startsWith("/api/reservations/actions/pending")) {
      return json([]);
    }
    if (method === "GET" && path.startsWith("/api/reservations/")) {
      return json([]);
    }
    if (method === "GET" && path.startsWith("/api/rooms/")) {
      return json([]);
    }
    if (method === "GET" && path === "/api/permissions/effective") {
      return json({ hotel_id: 42, role: "co_owner", permissions });
    }
    if (method === "GET" && path === "/api/users/") {
      return json([
        { id: 1, email: ownerEmail, role: "owner", is_verified: true, is_active: true, password_login_enabled: true, permissions },
        { id: 2, email: coOwnerEmail, role: "co_owner", is_verified: true, is_active: true, password_login_enabled: true, permissions },
        { id: 8, email: staffEmail, role: "manager", is_verified: true, is_active: true, password_login_enabled: true, permissions: ["dashboard:view"] }
      ]);
    }
    if (method === "GET" && path === "/api/users/aliases") {
      return json({ items: [
        { user_id: 1, email: ownerEmail, role: "owner", status: "active", alias: null },
        { user_id: 2, email: coOwnerEmail, role: "co_owner", status: "active", alias: null },
        { user_id: 8, email: staffEmail, role: "manager", status: "active", alias: staffAlias }
      ] });
    }
    if (method === "GET" && path === "/api/users/invitations") {
      return json(pendingInviteOpen ? [{
        invitation_id: 41,
        email: "pending-staff@example.test",
        role: "receptionist",
        inviter_email: coOwnerEmail,
        status: "pending",
        created_at: "2026-09-29T12:00:00Z",
        expires_at: "2026-10-06T12:00:00Z"
      }] : []);
    }
    if (method === "GET" && path === "/api/roles") {
      return json({ roles: [
        { code: "manager", name: "Gerencia", kind: "builtin", base_role: "manager", is_active: true },
        { code: "receptionist", name: "Recepción", kind: "builtin", base_role: "receptionist", is_active: true },
        { code: "housekeeping", name: "Limpieza", kind: "builtin", base_role: "housekeeping", is_active: true }
      ] });
    }
    if (method === "POST" && path === "/api/invitations/preview") {
      return json({ email: "new-staff@example.test", role: "receptionist", hotel_name: "Hotel de prueba", inviter_email: coOwnerEmail });
    }
    if (method === "POST" && path === "/api/users/invite") {
      return json({
        user: { id: 9, email: "new-staff@example.test", role: "receptionist", is_verified: false, is_active: false, password_login_enabled: false, permissions: [] },
        invitation_id: 19,
        invite_token: createdInvitationToken,
        accept_url: invitationUrl,
        email_delivery: "not_configured"
      });
    }
    if (method === "POST" && path === "/api/users/invitations/41/resend") {
      return json({
        user: { id: 10, email: "pending-staff@example.test", role: "receptionist", is_verified: false, is_active: false, permissions: [] },
        invitation_id: 41,
        invite_token: resentInvitationToken,
        accept_url: resentInvitationUrl,
        email_delivery: "not_configured"
      });
    }
    if (method === "DELETE" && path === "/api/users/invitations/41") {
      pendingInviteOpen = false;
      return route.fulfill({ status: 204, body: "" });
    }
    if (method === "PATCH" && path === "/api/users/8/alias") {
      staffAlias = String(body?.alias ?? "");
      return json({ user_id: 8, email: staffEmail, role: "manager", status: "active", alias: staffAlias });
    }
    return json({});
  });

  await page.goto("/login");
  await page.getByLabel("Email").fill(coOwnerEmail);
  await page.locator("#login-password").fill("synthetic-owner-password");
  await page.getByTestId("login-submit").click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.getByText("Configuración", { exact: true }).first().click();
  await page.getByRole("link", { name: "Usuarios", exact: true }).click();

  await expect(page.getByRole("heading", { name: "Usuarios y roles" })).toBeVisible();
  const primaryOwnerRow = page.locator("tbody tr").filter({ hasText: ownerEmail });
  await expect(primaryOwnerRow.getByLabel(`Rol de ${ownerEmail}`)).toHaveCount(0);
  await expect(primaryOwnerRow.getByRole("button", { name: "Revocar", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: `Editar alias de ${ownerEmail}` })).toHaveCount(0);
  await expect(page.getByLabel("Rol para invitar").locator('option[value="receptionist"]')).toHaveText("Recepción");
  await expect(page.getByRole("cell", { name: staffEmail, exact: true })).toBeVisible();
  await expect(page.getByText("Turno noche")).toBeVisible();
  await expect(page.getByText("pending-staff@example.test")).toBeVisible();

  await page.getByLabel("Email de invitación").fill("new-staff@example.test");
  await page.getByLabel("Alias del usuario (opcional)").fill("Recepción tarde");
  await page.getByLabel("Rol para invitar").selectOption("receptionist");
  await page.getByRole("button", { name: "Invitar" }).click();
  await expect(page.getByRole("alert")).toContainText("el envío de email no está configurado");
  expect(calls.find((call) => call.path === "/api/users/invite")?.body).toMatchObject({
    email: "new-staff@example.test",
    role: "receptionist",
    alias: "Recepción tarde"
  });

  await page.getByRole("button", { name: "Copiar enlace" }).click();
  await expect(page.getByRole("button", { name: "Enlace copiado" })).toBeVisible();
  const copiedInvitationUrl = await page.evaluate(() => navigator.clipboard.readText());
  expect(copiedInvitationUrl).toBe(invitationUrl);
  expect(new URL(copiedInvitationUrl).hash).toBe(`#token=${createdInvitationToken}`);

  await page.getByRole("button", { name: "Reenviar", exact: true }).click();
  await expect(page.getByRole("link", { name: "Abrir invitación" })).toBeVisible();
  await page.getByRole("button", { name: "Copiar enlace" }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(resentInvitationUrl);

  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Cancelar invitación", exact: true }).click();
  await expect(page.getByText("No hay invitaciones pendientes.")).toBeVisible();
  expect(calls.some((call) => call.path === "/api/users/invitations/41/resend")).toBe(true);
  expect(calls.some((call) => call.path === "/api/users/invitations/41" && call.method === "DELETE")).toBe(true);

  await page.getByRole("button", { name: `Editar alias de ${staffEmail}` }).click();
  await page.getByLabel(`Alias de ${staffEmail}`).fill("Recepción de noche");
  await page.getByRole("button", { name: "Guardar" }).click();
  await expect(page.getByText("Recepción de noche")).toBeVisible();
  expect(calls.find((call) => call.path === "/api/users/8/alias")?.body).toEqual({ alias: "Recepción de noche" });

  await page.goto(copiedInvitationUrl);
  await expect(page.getByText("new-staff@example.test")).toBeVisible();
  expect(calls.find((call) => call.path === "/api/invitations/preview")?.body).toEqual({ token: createdInvitationToken });
});
