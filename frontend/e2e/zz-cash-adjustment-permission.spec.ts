import { expect, test, type Page } from "@playwright/test";

import {
  completeStepUpPrompt,
  issueStepUpTicket,
  loginAsStepUpOwner,
  stepUpAuthHeaders
} from "./support/step-up-owner";

const backendURL = (process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040").replace(/\/$/, "");
const receptionist = {
  email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
  password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!"
};
const manager = {
  email: process.env.E2E_MANAGER_EMAIL || "manager@e2e.com",
  password: process.env.E2E_MANAGER_PASSWORD || "E2eManager1234!"
};

async function login(page: Page, credentials: { email: string; password: string }) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

async function showCashMovementForm(page: Page) {
  await page.goto("/caja");
  await expect(page.getByRole("heading", { name: "Caja", exact: true })).toBeVisible();
  const movementForm = page.locator("form").filter({ hasText: "Registrar movimiento" });
  await expect(movementForm).toBeVisible();
  return movementForm;
}

async function stubOpenSessionRead(page: Page) {
  // The permission flow needs a real authenticated browser and real effective
  // permissions. Stub only the unrelated cash-session read so this RBAC test
  // does not create a session or mutate the shared E2E hotel's cash ledger.
  await page.route("**/api/cash-register/sessions*", async (route) => {
    const url = new URL(route.request().url());
    if (
      route.request().method() === "GET" &&
      url.pathname === "/api/cash-register/sessions/9001/summary"
    ) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: 9001,
          status: "open",
          currency_code: "ARS",
          opening_balance: "100.00",
          income_total: "0.00",
          expense_total: "0.00",
          adjustment_total: "0.00",
          confirmed_cash_total: "0.00",
          expected_balance: "100.00",
          movements_count: 0
        })
      });
      return;
    }
    if (route.request().method() !== "GET" || url.pathname !== "/api/cash-register/sessions") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: 9001,
          hotel_id: 1,
          opened_by_user_id: 1,
          closed_by_user_id: null,
          status: "open",
          opening_balance: "100.00",
          currency_code: "ARS",
          opened_at: new Date().toISOString(),
          closed_at: null,
          notes: null
        }
      ])
    });
  });
}

test("reception can keep using income movements but cannot choose a manual adjustment", async ({ page }) => {
  await login(page, receptionist);
  await stubOpenSessionRead(page);
  const movementForm = await showCashMovementForm(page);
  const type = movementForm.locator("select").first();

  await expect(type.locator('option[value="income"]')).toBeEnabled();
  await expect(type.locator('option[value="adjustment"]')).toHaveAttribute("disabled", "");
});

test("owner can delegate cash adjustments and the permitted role sees the adjustment control", async ({ page, request }, testInfo) => {
  test.setTimeout(120_000);
  const ownerSession = await loginAsStepUpOwner(page, "rbac", testInfo.project.name);
  let lastTotpStep = ownerSession.lastTotpStep;

  const catalogResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/permissions/catalog" && response.ok();
  });
  await page.goto("/settings/permissions");
  lastTotpStep = await completeStepUpPrompt(page, lastTotpStep, ownerSession.auth.user.email);
  await catalogResponse;

  const managerToggle = page.getByTestId("permission-toggle-manager-cash:adjustment_manage");
  await expect(managerToggle).toBeVisible();
  await expect(managerToggle).toBeEnabled();
  await expect(managerToggle).not.toBeChecked();

  let grantVersion: number | null = null;
  try {
    const grantResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname === "/api/permissions/override" && response.request().method() === "PUT" && response.ok();
    });
    await managerToggle.click();
    lastTotpStep = await completeStepUpPrompt(page, lastTotpStep, ownerSession.auth.user.email);
    const grantResponse = await grantResponsePromise;
    grantVersion = ((await grantResponse.json()) as { version: number }).version;
    await expect(managerToggle).toBeChecked();
    const managerPermissionRow = page.getByTestId("permissions-matrix").getByRole("row").filter({
      has: page.getByText("cash:adjustment_manage", { exact: true })
    });
    await expect(managerPermissionRow).toContainText("Override de rol");

    await page.context().clearCookies();
    await login(page, manager);
    await stubOpenSessionRead(page);
    const movementForm = await showCashMovementForm(page);
    await expect(movementForm.locator('option[value="adjustment"]')).toBeEnabled();
  } finally {
    if (grantVersion !== null) {
      const restorePath = "/api/permissions/role-overrides/manager/cash:adjustment_manage";
      const restoreTicket = await issueStepUpTicket(request, ownerSession.auth, {
        permissionCode: "permissions:manage",
        method: "DELETE",
        path: restorePath
      }, lastTotpStep);
      const restored = await request.delete(
        `${backendURL}${restorePath}?expected_version=${grantVersion}`,
        {
          headers: {
            ...stepUpAuthHeaders(ownerSession.auth),
            "X-Action-Step-Up-Ticket": restoreTicket.ticket
          }
        }
      );
      expect(restored.ok()).toBeTruthy();
    }
  }
});
