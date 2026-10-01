import { expect, test, type Page } from "@playwright/test";

import { nextTotpAfter } from "./support/totp";

test.use({ trace: "off", screenshot: "off", video: "off" });

const owner = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

const firstRecoveryCodes = ["ABCD-EFGH", "JKLM-NPQR", "STUV-WXYZ"];
const regeneratedRecoveryCodes = ["1234-5678", "2345-6789", "3456-7890"];
const enrollmentSecret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP";

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(owner.email);
  await page.locator('input[type="password"]').fill(owner.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

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
