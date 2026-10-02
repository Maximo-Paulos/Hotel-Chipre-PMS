import { expect, test, type Page } from "@playwright/test";

import { completeStepUpPrompt, loginAsStepUpOwner } from "./support/step-up-owner";

const receptionistCredentials = {
  email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
  password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!"
};

async function loginAsReceptionist(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(receptionistCredentials.email);
  await page.locator('input[type="password"]').fill(receptionistCredentials.password);
  const loginResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/auth/login" && response.request().method() === "POST"
  );
  await page.getByTestId("login-submit").click();
  expect((await loginResponse).ok()).toBeTruthy();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

function parseMoney(text: string) {
  return Number(text.replace(/[^0-9,.-]/g, "").replace(/\./g, "").replace(",", "."));
}

test("owner finds and approves a receptionist's pending close from another browser session", async ({ browser }, testInfo) => {
  test.setTimeout(120_000);
  const receptionContext = await browser.newContext();
  const ownerContext = await browser.newContext();
  try {
    const receptionPage = await receptionContext.newPage();
    await loginAsReceptionist(receptionPage);
    const sessionsResponsePromise = receptionPage.waitForResponse((response) =>
      response.url().includes("/api/cash-register/sessions") && response.request().method() === "GET"
    );
    await receptionPage.goto("/caja");
    await sessionsResponsePromise;

    const openButton = receptionPage.getByRole("button", { name: "Abrir caja", exact: true });
    if (await openButton.isVisible().catch(() => false)) {
      const openingForm = receptionPage.locator("form").filter({ hasText: "Saldo inicial" }).filter({ hasText: "Abrir caja" });
      await openingForm.getByText("Saldo inicial", { exact: true }).locator("..").locator("input").fill("100");
      await openButton.click();
      await expect(receptionPage.getByText("Caja abierta.", { exact: true })).toBeVisible();
    }

    const closeForm = receptionPage.locator("form").filter({ hasText: "Saldo esperado:" }).filter({ hasText: "Cerrar caja" });
    const expectedText = await closeForm.getByText(/Saldo esperado:/).innerText();
    const expectedBalance = parseMoney(expectedText);
    const countedBalance = expectedBalance > 50 ? expectedBalance - 1 : 51;
    await closeForm.getByText("Saldo contado", { exact: true }).locator("..").locator("input").fill(String(countedBalance));
    const closeResponsePromise = receptionPage.waitForResponse((response) =>
      response.url().includes("/api/cash-register/sessions/") &&
      response.url().endsWith("/close") &&
      response.request().method() === "POST" &&
      response.status() === 200
    );
    await closeForm.getByRole("button", { name: "Cerrar caja", exact: true }).click();
    const closeResponse = await closeResponsePromise;
    const pendingReport = await closeResponse.json() as {
      id: number;
      session_id: number;
      difference_approved: boolean;
      successor_opening_balance: string;
      custody_handoff: { delivered_amount: string };
    };
    expect(pendingReport.difference_approved).toBe(false);
    expect(pendingReport.successor_opening_balance).toBe("0.00");
    expect(Number(pendingReport.custody_handoff.delivered_amount)).toBeCloseTo(countedBalance, 2);
    // Closing a turn selects the closed session's report. Its arqueo form is
    // intentionally removed; the successor starts with its own empty form
    // when selected.
    await expect(closeForm).toHaveCount(0);
    await expect(receptionPage.getByText(/abierta con saldo.*0,00/)).toBeVisible();
    await expect(receptionPage.getByTestId("cash-pending-approvals")).toBeVisible();
    await expect(receptionPage.getByRole("button", { name: "Aprobar diferencia", exact: true })).toHaveCount(0);

    const ownerPage = await ownerContext.newPage();
    const ownerSession = await loginAsStepUpOwner(ownerPage, "cash", testInfo.project.name);
    await ownerPage.goto("/dashboard");
    await expect(ownerPage.getByTestId("dashboard-cash-approvals")).toBeVisible({ timeout: 20_000 });
    await ownerPage.goto("/caja");
    const approvals = ownerPage.getByTestId("cash-pending-approvals");
    await expect(approvals).toBeVisible({ timeout: 20_000 });
    const pendingItem = approvals.locator("li").filter({ hasText: `Caja #${pendingReport.session_id}` });
    await expect(pendingItem).toBeVisible();

    const approvalResponsePromise = ownerPage.waitForResponse((response) =>
      response.url().includes(`/api/cash-register/close-reports/${pendingReport.id}/approve`) &&
      response.request().method() === "POST" &&
      response.status() === 200
    );
    await pendingItem.getByRole("button", { name: "Aprobar diferencia", exact: true }).click();
    const consumedStep = await completeStepUpPrompt(ownerPage, ownerSession.lastTotpStep, ownerSession.auth.user.email);
    const approvalResponse = await approvalResponsePromise;
    const approvedReport = await approvalResponse.json() as {
      approved_by_user_id: number | null;
      difference_approved: boolean;
    };
    expect(approvedReport.difference_approved).toBe(true);
    expect(approvedReport.approved_by_user_id).not.toBeNull();
    expect(consumedStep).toBeGreaterThan(ownerSession.lastTotpStep);
    await expect(ownerPage.getByText("Diferencia aprobada.", { exact: true })).toBeVisible();
    await expect(pendingItem).toHaveCount(0, { timeout: 20_000 });
    await expect(ownerPage.getByText("Estado: diferencia aprobada", { exact: true })).toBeVisible();

    await ownerPage.reload();
    const pendingCustodies = ownerPage.getByTestId("cash-pending-custodies");
    await expect(pendingCustodies).toBeVisible({ timeout: 20_000 });
    const pendingCustody = pendingCustodies.locator("li").filter({
      hasText: `Caja #${pendingReport.session_id}`
    });
    await expect(pendingCustody).toBeVisible();
    await pendingCustody.locator('input[type="number"]').fill("50");
    const custodyResponsePromise = ownerPage.waitForResponse((response) =>
      response.url().includes(`/api/cash-register/close-reports/${pendingReport.id}/custody/confirm`) &&
      response.request().method() === "POST" &&
      response.status() === 200
    );
    await pendingCustody.getByRole("button", { name: "Confirmar custodia y cambio", exact: true }).click();
    const custodyTotpStep = await completeStepUpPrompt(
      ownerPage,
      consumedStep,
      ownerSession.auth.user.email
    );
    const custodyResponse = await custodyResponsePromise;
    const receivedReport = await custodyResponse.json() as {
      custody_handoff: { delivered_amount: string; status: string; received_by_user_id: number | null };
      successor_float_declared_amount: string;
      successor_opening_balance: string;
    };
    expect(receivedReport.custody_handoff.status).toBe("confirmed");
    expect(receivedReport.custody_handoff.received_by_user_id).toBe(ownerSession.auth.user.id);
    expect(Number(receivedReport.custody_handoff.delivered_amount)).toBeCloseTo(countedBalance, 2);
    expect(receivedReport.successor_float_declared_amount).toBe("50.00");
    expect(receivedReport.successor_opening_balance).toBe("50.00");
    expect(custodyTotpStep).toBeGreaterThan(consumedStep);
    await expect(ownerPage.getByText(/Recepción confirmada\. Fondo de cambio para la sucesora:/)).toBeVisible();
    await expect(pendingCustody).toHaveCount(0, { timeout: 20_000 });
  } finally {
    await Promise.all([receptionContext.close(), ownerContext.close()]);
  }
});
