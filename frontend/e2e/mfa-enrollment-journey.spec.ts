import { expect, test, type Page } from "@playwright/test";

import { nextTotpAfter } from "./support/totp";

test.use({ trace: "off", screenshot: "off", video: "off" });

const owner = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

const firstRecoveryCodes = ["ABCD-EFGH", "JKLM-NPQR", "STUV-WXYZ"];
const enrollmentSecret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP";

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(owner.email);
  await page.locator('input[type="password"]').fill(owner.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("MFA enrollment renders its QR without a React runtime error", async ({ page }) => {
  const pageErrors: string[] = [];
  const syntheticPassword = "SyntheticOnlyPassword123!";
  let enrollmentProof: Record<string, unknown> | null = null;
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.route(/^https?:\/\/[^/]+\/api\//, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    let payload: unknown = {};

    if (pathname === "/api/auth/session/refresh") {
      payload = {
        access_token: "synthetic-only-access-token",
        hotel_id: 1,
        user: {
          id: 1,
          email: "mfa-qr-owner@example.test",
          role: "owner",
          is_verified: true,
          is_active: true,
          password_login_enabled: true,
          google_login_enabled: false
        },
        permissions: ["settings:security:view"]
      };
    } else if (pathname === "/api/permissions/effective") {
      payload = { hotel_id: 1, role: "owner", permissions: ["settings:security:view"] };
    } else if (pathname === "/api/settings/security/overview") {
      payload = {
        hotel_id: 1,
        active_members: 1,
        pending_invitations: 0,
        security_events_24h: 0,
        permission_denials_24h: 0,
        session_timeout_minutes: 60,
        current_user: { id: 1, email: "mfa-qr-owner@example.test", role: "owner", token_version: 1 }
      };
    } else if (pathname === "/api/settings/security/events") {
      payload = { hotel_id: 1, events: [] };
    } else if (pathname === "/api/auth/providers") {
      payload = { google: { enabled: false, client_id: null, self_signup_enabled: false, allowed_domains: [] } };
    } else if (pathname === "/api/auth/me") {
      payload = {
        id: 1,
        email: "mfa-qr-owner@example.test",
        role: "owner",
        is_verified: true,
        is_active: true,
        password_login_enabled: true,
        google_login_enabled: false
      };
    } else if (pathname === "/api/auth/mfa/status") {
      payload = { enabled: false };
    } else if (pathname === "/api/auth/mfa/enroll") {
      enrollmentProof = request.postDataJSON() as Record<string, unknown>;
      payload = {
        status: "pending",
        secret: enrollmentSecret,
        otpauth_uri: `otpauth://totp/Hotel%20Chipre:mfa-qr-owner%40example.test?secret=${enrollmentSecret}&issuer=Hotel%20Chipre&digits=6&period=30`
      };
    }

    await route.fulfill({ status: 200, json: payload });
  });

  await page.goto("/settings/security");
  await expect(page.getByTestId("mfa-settings-card")).toBeVisible();
  await expect(page.getByTestId("mfa-start-enrollment")).toBeVisible();
  await page.getByTestId("mfa-start-enrollment").click();
  await page.locator("#mfa-enrollment-password").fill(syntheticPassword);
  await page.getByTestId("mfa-submit-enrollment-proof").click();

  const qr = page.getByTestId("mfa-enrollment-qr");
  await expect(qr).toBeVisible();
  await expect(qr.locator("svg")).toBeVisible();
  await expect(qr.locator("path").nth(1)).toHaveAttribute("d", /^[Mm]/);
  expect(enrollmentProof).toEqual({ current_password: syntheticPassword });
  expect(pageErrors).toEqual([]);
});

test("owner can enroll, manage recovery codes, and disable MFA from security settings", async ({ page }) => {
  await login(page);
  await page.goto("/settings/security");
  await expect(page.getByTestId("mfa-settings-card")).toBeVisible();
  await expect(page.getByTestId("mfa-start-enrollment")).toBeVisible();
  await page.getByTestId("mfa-start-enrollment").click();
  await page.locator("#mfa-enrollment-password").fill(owner.password);
  await page.getByTestId("mfa-submit-enrollment-proof").click();

  await expect(page.getByTestId("mfa-enrollment-qr")).toBeVisible();
  const secret = (await page.getByTestId("mfa-enrollment-secret").innerText()).trim();
  let lastTotpStep = -1;
  const enrollmentCode = await nextTotpAfter(lastTotpStep, secret);
  await page.locator("#mfa-enrollment-code").fill(enrollmentCode.code);
  await page.getByTestId("mfa-confirm-enrollment").click();
  lastTotpStep = enrollmentCode.step;
  await expect(page.getByTestId("mfa-recovery-codes")).toBeVisible();
  await expect(page.getByTestId("mfa-recovery-codes").getByRole("listitem")).toHaveCount(10);
  await page.getByTestId("mfa-finish-recovery-codes").click();
  await expect(page.getByTestId("mfa-enabled-status")).toBeVisible();

  await page.getByTestId("mfa-regenerate-codes").click();
  const regenerateCode = await nextTotpAfter(lastTotpStep, secret);
  lastTotpStep = regenerateCode.step;
  await page.locator("#mfa-regenerate-code").fill(regenerateCode.code);
  await page.getByRole("button", { name: "Confirmar regeneración" }).click();
  await expect(page.getByTestId("mfa-recovery-codes")).toBeVisible();
  await expect(page.getByTestId("mfa-recovery-codes").getByRole("listitem")).toHaveCount(10);
  await page.getByTestId("mfa-finish-recovery-codes").click();

  await page.getByTestId("mfa-start-disable").click();
  await page.locator("#mfa-disable-password").fill(owner.password);
  const disableCode = await nextTotpAfter(lastTotpStep, secret);
  await page.locator("#mfa-disable-code").fill(disableCode.code);
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("mfa-confirm-disable").click();
  await expect(page.getByTestId("mfa-start-enrollment")).toBeVisible();
});

test("step-up prompt sends an unenrolled owner to MFA enrollment", async ({ page }) => {
  let mfaEnabled = false;
  await page.route("**/api/auth/mfa/status", async (route) => {
    await route.fulfill({ json: { enabled: mfaEnabled } });
  });
  await page.route("**/api/auth/mfa/enroll", async (route) => {
    await route.fulfill({
      json: {
        status: "pending",
        secret: enrollmentSecret,
        otpauth_uri: `otpauth://totp/Hotel%20Chipre:${encodeURIComponent(owner.email)}?secret=${enrollmentSecret}&issuer=Hotel%20Chipre&digits=6&period=30`
      }
    });
  });
  await page.route("**/api/auth/mfa/enroll/confirm", async (route) => {
    mfaEnabled = true;
    await route.fulfill({ json: { recovery_codes: firstRecoveryCodes } });
  });
  await page.route("**/api/permissions/catalog", async (route) => {
    await route.fulfill({
      status: 428,
      json: {
        detail: {
          code: "STEP_UP_REQUIRED",
          permission_code: "permissions:manage",
          method: "GET",
          path: "/api/permissions/catalog"
        }
      }
    });
  });

  await login(page);
  await page.goto("/settings/permissions");
  const dialog = page.getByRole("dialog", { name: "Confirmá que sos vos" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(/todavía no tiene un autenticador activo/i)).toBeVisible();
  await dialog.getByTestId("step-up-activate-mfa").click();

  await page.waitForURL((url) => url.pathname === "/settings/security" && url.searchParams.has("mfaReturnTo"));
  await expect(page.getByTestId("mfa-settings-card")).toBeVisible();
  await page.getByTestId("mfa-start-enrollment").click();
  await page.locator("#mfa-enrollment-password").fill(owner.password);
  await page.getByTestId("mfa-submit-enrollment-proof").click();
  await expect(page.getByTestId("mfa-enrollment-qr")).toBeVisible();
  await page.locator("#mfa-enrollment-code").fill("123456");
  await page.getByTestId("mfa-confirm-enrollment").click();
  await expect(page.getByTestId("mfa-recovery-codes")).toBeVisible();
  await page.getByTestId("mfa-finish-recovery-codes").click();

  await page.waitForURL((url) => url.pathname === "/settings/permissions");
  const resumedPrompt = page.getByRole("dialog", { name: "Confirmá que sos vos" });
  await expect(resumedPrompt).toBeVisible();
  await expect(resumedPrompt.getByLabel("Código de autenticación o recuperación")).toBeVisible();
});
