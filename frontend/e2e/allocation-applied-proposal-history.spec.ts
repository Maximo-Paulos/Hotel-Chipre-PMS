import { expect, test, type Page } from "@playwright/test";

const receptionist = {
  email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
  password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!"
};

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(receptionist.email);
  await page.locator('input[type="password"]').fill(receptionist.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("an applied allocation proposal is shown as reviewed with historical source and assigned rooms", async ({ page }) => {
  await login(page);

  await page.route("**/api/allocation/policy/runs/latest", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: 48,
        status: "succeeded",
        trigger_type: "manual_api_recalculate",
        objective_score: 1,
        solver_summary: "Allocation run moved 1 reservation(s)",
        error_message: null,
        policy_version_id: 2,
        horizon_start: "2026-11-05",
        horizon_end: "2027-01-17",
        created_at: "2026-11-06T00:26:00Z",
        explanations: [],
        metrics: [],
        assignments: [{
          id: 100,
          reservation_id: 58,
          source_room_id: 1,
          room_id: 3,
          status: "applied",
          explanation_summary: "Optimizes room use",
          requires_explicit_approval: false
        }]
      })
    });
  });

  await page.goto("/operacion/asignacion");

  await expect(page.getByText("Propuesta revisada", { exact: true })).toBeVisible();
  await expect(page.getByText("Esta propuesta ya no tiene movimientos pendientes.", { exact: true })).toBeVisible();
  await expect(page.getByText("Habitación de origen", { exact: true })).toBeVisible();
  await expect(page.getByText("Habitación asignada", { exact: true })).toBeVisible();
  await expect(page.getByText("Sugerencias listas para revisar", { exact: true })).toHaveCount(0);
  await expect(page.getByText("No hay cambios sugeridos. Las habitaciones actuales se conservan.", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Aceptar propuesta" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Rechazar propuesta" })).toHaveCount(0);
});
