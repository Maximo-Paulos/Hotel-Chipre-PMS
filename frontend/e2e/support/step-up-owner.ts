import { expect, type APIRequestContext, type Page } from "@playwright/test";

import { nextTotpAfter } from "./totp";

const backendURL = (process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040").replace(/\/$/, "");
const lastUsedTotpStepByUser = new Map<string, number>();

export type StepUpOwnerAuth = {
  hotel_id: number;
  access_token: string;
  csrf_token?: string;
  user: { email: string };
};

export type StepUpChallenge = {
  permissionCode: string;
  method: "GET" | "HEAD" | "POST" | "PUT" | "PATCH" | "DELETE";
  path: string;
};

export function stepUpOwnerCredentials(purpose: "cash" | "rbac", projectName: string) {
  return {
    email: `owner-stepup-${purpose}+${projectName}@e2e.com`,
    password: process.env.E2E_STEP_UP_OWNER_PASSWORD || "E2eStepUp1234!"
  };
}

export async function loginAsStepUpOwner(
  page: Page,
  purpose: "cash" | "rbac",
  projectName: string
): Promise<{ auth: StepUpOwnerAuth; lastTotpStep: number }> {
  const credentials = stepUpOwnerCredentials(purpose, projectName);
  await page.goto("/login");
  await page.getByLabel("Email").fill(credentials.email);
  await page.locator("#login-password").fill(credentials.password);
  const loginResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/auth/login" && response.request().method() === "POST";
  });
  await page.getByTestId("login-submit").click();
  const loginResponse = await loginResponsePromise;
  expect(loginResponse.ok()).toBeTruthy();
  const challenge = await loginResponse.json() as { requires_mfa?: boolean };
  expect(challenge.requires_mfa).toBe(true);

  const codeInput = page.getByLabel("Código de la app autenticadora o de recuperación");
  await codeInput.waitFor({ state: "visible" });
  let lastTotpStep = lastUsedTotpStepByUser.get(credentials.email) ?? -1;
  let auth: StepUpOwnerAuth | null = null;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const loginCode = await nextTotpAfter(lastTotpStep);
    await codeInput.fill(loginCode.code);
    const mfaResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname === "/api/auth/login/mfa" && response.request().method() === "POST";
    });
    await page.getByRole("button", { name: "Verificar y continuar", exact: true }).click();
    const mfaResponse = await mfaResponsePromise;
    if (mfaResponse.ok()) {
      auth = await mfaResponse.json() as StepUpOwnerAuth;
      lastTotpStep = loginCode.step;
      lastUsedTotpStepByUser.set(auth.user.email, lastTotpStep);
      break;
    }
    const failure = await mfaResponse.json() as { detail?: string };
    if (mfaResponse.status() !== 401 || !failure.detail?.includes("Codigo MFA invalido o ya utilizado")) {
      throw new Error("Synthetic MFA login failed for a reason other than TOTP replay");
    }
    lastTotpStep = loginCode.step;
    lastUsedTotpStepByUser.set(credentials.email, lastTotpStep);
  }
  if (!auth) throw new Error("Could not obtain a fresh synthetic MFA code for login");
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
  return { auth, lastTotpStep };
}

export async function completeStepUpPrompt(
  page: Page,
  lastTotpStep: number,
  ownerEmail?: string
): Promise<number> {
  const dialog = page.getByRole("dialog", { name: "Confirmá que sos vos" });
  await expect(dialog).toBeVisible({ timeout: 20_000 });
  let consumedStep = Math.max(lastTotpStep, ownerEmail ? lastUsedTotpStepByUser.get(ownerEmail) ?? -1 : -1);
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const code = await nextTotpAfter(consumedStep);
    await dialog.getByLabel("Código de autenticación").fill(code.code);
    const stepUpResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname === "/api/auth/step-up" && response.request().method() === "POST";
    });
    await dialog.getByRole("button", { name: "Verificar y continuar", exact: true }).click();
    const response = await stepUpResponsePromise;
    if (response.ok()) {
      await expect(dialog).not.toBeVisible({ timeout: 20_000 });
      if (ownerEmail) lastUsedTotpStepByUser.set(ownerEmail, code.step);
      return code.step;
    }
    const failure = await response.json() as { detail?: string };
    if (response.status() !== 401 || !failure.detail?.includes("Codigo MFA invalido o ya utilizado")) {
      throw new Error("Synthetic action step-up failed for a reason other than TOTP replay");
    }
    consumedStep = code.step;
    if (ownerEmail) lastUsedTotpStepByUser.set(ownerEmail, consumedStep);
  }
  throw new Error("Could not obtain a fresh synthetic MFA code for action step-up");
}

export function stepUpAuthHeaders(auth: StepUpOwnerAuth): Record<string, string> {
  return {
    "X-Hotel-Id": String(auth.hotel_id),
    "X-User-Id": auth.user.email,
    Authorization: `Bearer ${auth.access_token}`,
    "X-CSRF-Token": String(auth.csrf_token || ""),
    "Content-Type": "application/json"
  };
}

export async function issueStepUpTicket(
  request: APIRequestContext,
  auth: StepUpOwnerAuth,
  challenge: StepUpChallenge,
  lastTotpStep: number
): Promise<{ ticket: string; lastTotpStep: number }> {
  let consumedStep = Math.max(lastTotpStep, lastUsedTotpStepByUser.get(auth.user.email) ?? -1);
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const code = await nextTotpAfter(consumedStep);
    const response = await request.post(`${backendURL}/api/auth/step-up`, {
      headers: stepUpAuthHeaders(auth),
      data: {
        code: code.code,
        permission_code: challenge.permissionCode,
        method: challenge.method,
        path: challenge.path
      }
    });
    if (response.ok()) {
      const result = await response.json() as { ticket: string };
      expect(result.ticket).toBeTruthy();
      lastUsedTotpStepByUser.set(auth.user.email, code.step);
      return { ticket: result.ticket, lastTotpStep: code.step };
    }
    const failure = await response.json() as { detail?: string };
    if (response.status() !== 401 || !failure.detail?.includes("Codigo MFA invalido o ya utilizado")) {
      throw new Error("Synthetic action ticket issuance failed for a reason other than TOTP replay");
    }
    consumedStep = code.step;
    lastUsedTotpStepByUser.set(auth.user.email, consumedStep);
  }
  throw new Error("Could not obtain a fresh synthetic MFA code for an action ticket");
}
