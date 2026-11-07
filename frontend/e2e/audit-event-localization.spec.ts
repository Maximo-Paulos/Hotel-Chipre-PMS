import { expect, test, type Page } from "@playwright/test";

declare const process: { env: Record<string, string | undefined> };

const ownerCredentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(ownerCredentials.email);
  await page.locator('input[type="password"]').fill(ownerCredentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

test("notification titles localize English backend templates and keep reservation references", async ({ page }) => {
  await page.route("**/api/notifications?*", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      unread_count: 3,
      items: [
        { id: 1, hotel_id: 1, recipient_user_id: 1, event_type: "reservation.created", severity: "info", title: "New reservation RES-QA123", body: null, entity_type: "reservation", entity_id: 1, is_read: false, read_at: null, created_at: "2026-11-07T12:00:00Z", expires_at: null },
        { id: 2, hotel_id: 1, recipient_user_id: 1, event_type: "reservation.cancelled", severity: "warning", title: "Reservation RES-QA456 cancelled", body: null, entity_type: "reservation", entity_id: 2, is_read: false, read_at: null, created_at: "2026-11-07T12:00:00Z", expires_at: null },
        { id: 3, hotel_id: 1, recipient_user_id: 1, event_type: "report.daily", severity: "info", title: "Daily operational report - 2026-11-07", body: "Daily operational report - 2026-11-07\nOccupancy: 1/39 rooms (2.6%)\nArrivals: 0\nDepartures: 0\nPending payments: 0\nPending balance total: ARS 100.00 · USD 20.00\nLate arrivals: 0\nActive room blocks: 0\nCash session: open\nLow stock items: 0\nLaundry outbound remitos (last 14 days): 0\nAlerts: 0", entity_type: null, entity_id: null, is_read: false, read_at: null, created_at: "2026-11-07T12:00:00Z", expires_at: null }
      ]
    })
  }));

  await login(page);
  await page.getByRole("button", { name: /Ver alertas/ }).click();

  await expect(page.getByTestId("notification-item-1")).toContainText("Nueva reserva RES-QA123");
  await expect(page.getByTestId("notification-item-2")).toContainText("Reserva RES-QA456 cancelada");
  const dailyReport = page.getByTestId("notification-item-3");
  await expect(dailyReport).toContainText("Reporte operativo diario 2026-11-07");
  await expect(dailyReport).toContainText("Ocupación: 1/39 habitaciones (2.6%)");
  await expect(dailyReport).toContainText("Llegadas: 0");
  await expect(dailyReport).toContainText("Salidas: 0");
  await expect(dailyReport).toContainText("Pagos pendientes: 0");
  await expect(dailyReport).toContainText("Saldo pendiente total: ARS 100.00 · USD 20.00");
  await expect(dailyReport).toContainText("Llegadas tardías: 0");
  await expect(dailyReport).toContainText("Bloqueos activos de habitaciones: 0");
  await expect(dailyReport).toContainText("Estado de caja: abierta");
  await expect(dailyReport).toContainText("Artículos con stock bajo: 0");
  await expect(dailyReport).toContainText("Remitos salientes de lavandería (últimos 14 días): 0");
  await expect(dailyReport).toContainText("Alertas: 0");
  await expect(dailyReport).not.toContainText(/Daily operational report|Occupancy:|Arrivals:|Departures:|Pending payments:|Pending balance total:|Late arrivals:|Active room blocks:|Cash session:|Low stock items:|Laundry outbound remitos|Alerts:/);
  await expect(page.getByRole("dialog")).not.toContainText(/New reservation|Reservation .* cancelled|Daily operational report/);
});

test("operational audit localizes areas and action codes while retaining technical detail", async ({ page }) => {
  await page.route("**/api/operations/audit?*", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      hotel_id: 1,
      items: [{
        source: "business_event",
        source_id: 43,
        area: "rooms",
        action: "status_change",
        summary: "status_change (rooms #2)",
        actor_user_id: 1,
        actor_name: "QA Owner",
        occurred_at: "2026-11-07T12:00:00Z",
        room_id: 2,
        details: {}
      }, {
        source: "row_mutation",
        source_id: 44,
        area: "housekeeping_checklist_items",
        action: "status_change",
        summary: "housekeeping_checklist_items: status_change #5",
        actor_user_id: 2,
        actor_name: "QA Housekeeping",
        occurred_at: "2026-11-07T12:01:00Z",
        details: {}
      }],
      total: 2,
      limit: 50,
      offset: 0,
      has_more: false
    })
  }));

  await login(page);
  await page.goto("/operacion/auditoria");
  const auditPage = page.getByTestId("operational-audit-page");
  const row = auditPage.locator("article").filter({ hasText: "QA Owner" });

  await expect(row.getByText("Habitaciones", { exact: true })).toBeVisible();
  await expect(row.getByText("Cambio de estado", { exact: true })).toBeVisible();
  const technicalDetails = row.getByTestId("audit-technical-details-43");
  await expect(technicalDetails.getByText("Código de área: rooms", { exact: true })).toBeHidden();
  await technicalDetails.locator("summary").click();
  await expect(technicalDetails.getByText("Código de área: rooms", { exact: true })).toBeVisible();
  await expect(technicalDetails.getByText("Código de acción: status_change", { exact: true })).toBeVisible();
  await expect(technicalDetails.getByText("Resumen original: status_change (rooms #2)", { exact: true })).toBeVisible();
  const housekeepingRow = auditPage.locator("article").filter({ hasText: "QA Housekeeping" });
  await expect(housekeepingRow.getByText("Limpieza", { exact: true })).toBeVisible();
});
