import { expect, test, type Page } from "@playwright/test";

const syntheticGoogleIdToken = "synthetic-google-link-id-token";

async function installGoogleButton(page: Page) {
  await page.route("**/api/auth/providers", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      google: {
        enabled: true,
        client_id: "e2e.apps.googleusercontent.com",
        self_signup_enabled: true,
        allowed_domains: []
      }
    })
  }));
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
}

async function installSecurityMocks(
  page: Page,
  initialState: { googleLinked?: boolean; passwordEnabled?: boolean } = {}
) {
  const backendURL = process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040";
  const calls: Array<{ path: string; body: Record<string, unknown> | null; authorization?: string | null }> = [];
  let googleLinked = initialState.googleLinked ?? false;
  let passwordEnabled = initialState.passwordEnabled ?? true;
  let googleLinkAttempts = 0;
  const email = "owner@e2e.example";
  const permissions = ["dashboard:view", "settings:security:view"];
  const authResponse = {
    access_token: "synthetic-owner-access-token",
    token_type: "bearer",
    hotel_id: 42,
    hotel_ids: [42],
    user: {
      id: 7,
      email,
      role: "owner",
      is_verified: true,
      is_active: true,
      password_login_enabled: passwordEnabled,
      google_login_enabled: googleLinked,
      permissions
    },
    permissions,
    csrf_token: "synthetic-csrf-token"
  };

  await page.route(`${backendURL}/api/**`, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const body = method === "POST" || method === "PATCH"
      ? request.postDataJSON() as Record<string, unknown>
      : null;
    const json = (data: unknown, status = 200) => route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(data)
    });

    if (body || method === "POST") {
      calls.push({ path, body, authorization: request.headers()["authorization"] ?? null });
    }
    if (method === "GET" && path.endsWith("/api/auth/providers")) {
      return json({
        google: {
          enabled: true,
          client_id: "e2e.apps.googleusercontent.com",
          self_signup_enabled: true,
          allowed_domains: []
        }
      });
    }
    if (method === "POST" && path.endsWith("/api/auth/session/refresh")) return json(authResponse);
    if (method === "GET" && path.endsWith("/api/onboarding/status")) {
      return json({ completed: true, missing_steps: [] });
    }
    if (method === "GET" && path.endsWith("/api/auth/me")) {
      return json({
        id: 7,
        email,
        role: "owner",
        is_verified: true,
        is_active: true,
        password_login_enabled: passwordEnabled,
        google_login_enabled: googleLinked,
        permissions
      });
    }
    if (method === "GET" && path.endsWith("/api/settings/security/overview")) {
      return json({
        hotel_id: 42,
        active_members: 1,
        pending_invitations: 0,
        security_events_24h: 0,
        permission_denials_24h: 0,
        session_timeout_minutes: 60,
        current_user: { id: 7, email, role: "owner", last_login: null, token_version: 0 }
      });
    }
    if (method === "GET" && path.startsWith("/api/settings/security/events")) {
      return json({ hotel_id: 42, events: [] });
    }
    if (method === "POST" && path.endsWith("/api/auth/google/link")) {
      googleLinkAttempts += 1;
      if (googleLinkAttempts === 1) return json({ detail: "Reautenticacion invalida" }, 403);
      googleLinked = true;
      return json({ linked: true });
    }
    if (method === "POST" && path.endsWith("/api/auth/password/set")) {
      passwordEnabled = true;
      return json({ password_login_enabled: true });
    }
    return json({});
  });

  return calls;
}

test("existing password user links Google only after confirming both identities", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await installGoogleButton(page);
  const calls = await installSecurityMocks(page);

  await page.goto("/settings/security");
  expect(pageErrors, `Browser errors at ${page.url()}`).toEqual([]);
  expect(page.url()).toContain("/settings/security");
  await expect(page.getByRole("heading", { name: "Seguridad", exact: true })).toBeVisible();
  await expect(page.getByTestId("google-link-card")).toBeVisible();
  await page.getByRole("button", { name: "Continue with Google" }).click();
  await page.getByLabel("Contraseña actual de Hotels-PMS").fill("IncorrectPassphrase123!");
  await page.getByTestId("google-link-submit").click();
  await expect(page.getByRole("alert")).toHaveText("Reautenticacion invalida");
  await expect(page.getByRole("button", { name: "Continue with Google" })).toBeVisible();

  await page.getByRole("button", { name: "Continue with Google" }).click();
  await page.getByLabel("Contraseña actual de Hotels-PMS").fill("LocalPassphrase!123");
  await page.getByTestId("google-link-submit").click();

  await expect(page.getByText("Google quedó vinculado. Tu contraseña de Hotels-PMS sigue activa.")).toBeVisible();
  await expect(page.getByText("Esta cuenta permite ingresar con Google o con tu contraseña de Hotels-PMS.")).toBeVisible();
  await expect(page.getByTestId("google-link-card")).toHaveCount(0);
  expect(calls).toContainEqual({
    path: "/api/auth/google/link",
    body: { id_token: syntheticGoogleIdToken, password: "LocalPassphrase!123" },
    authorization: "Bearer synthetic-owner-access-token"
  });
  expect(calls).toContainEqual({
    path: "/api/auth/google/link",
    body: { id_token: syntheticGoogleIdToken, password: "IncorrectPassphrase123!" },
    authorization: "Bearer synthetic-owner-access-token"
  });
});

test("Google-only user can add a Hotels-PMS password without email recovery", async ({ page }) => {
  await installGoogleButton(page);
  const calls = await installSecurityMocks(page, { googleLinked: true, passwordEnabled: false });

  await page.goto("/settings/security");
  await expect(page.getByRole("heading", { name: "Seguridad", exact: true })).toBeVisible();
  await expect(page.getByText("Esta cuenta no tiene habilitado el ingreso con contraseña.")).toBeVisible();
  await page.getByRole("button", { name: "Continue with Google" }).click();
  await page.locator("#security-new-password").fill("NewLocalPassphrase!123");
  await page.locator("#security-new-password-confirm").fill("NewLocalPassphrase!123");
  await page.getByRole("button", { name: "Crear contraseña" }).click();

  await expect(page.getByText("Contraseña creada. Ya podés ingresar con Google o con email y contraseña.")).toBeVisible();
  expect(calls).toContainEqual({
    path: "/api/auth/password/set",
    body: { id_token: syntheticGoogleIdToken, new_password: "NewLocalPassphrase!123" },
    authorization: "Bearer synthetic-owner-access-token"
  });
});
