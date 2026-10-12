import { expect, test, type Page } from "@playwright/test";

const owner = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(owner.email);
  await page.locator('input[type="password"]').fill(owner.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

function revenueFixture(startDate: string, endDate: string, withData: boolean) {
  const collectedByCurrency = withData ? [
    { currency_code: "ARS", gross_collected: 1250, refunds: 250, net_collected: 1000, transaction_count: 2 },
    { currency_code: "USD", gross_collected: 50, refunds: 0, net_collected: 50, transaction_count: 1 }
  ] : [];
  const byMethod = withData ? [
    { payment_method: "cash", currency_code: "ARS", gross_collected: 1250, refunds: 250, net_collected: 1000, transaction_count: 2 },
    { payment_method: "credit_card", currency_code: "USD", gross_collected: 50, refunds: 0, net_collected: 50, transaction_count: 1 }
  ] : [];
  const byCategory = withData ? [
    { category_id: "1", category_name: "Standard", currency_code: "ARS", gross_collected: 1250, refunds: 250, net_collected: 1000, transaction_count: 2 }
  ] : [];
  const byChannel = withData ? [
    { channel_code: "manual_recepcion", channel_label: "Recepción", currency_code: "ARS", gross_collected: 1250, refunds: 250, net_collected: 1000, transaction_count: 2 }
  ] : [];
  return {
    start_date: startDate,
    end_date: endDate,
    timezone: "America/Argentina/Buenos_Aires",
    receivables_as_of: "2026-10-05",
    collected: {
      currency_code: null,
      total: null,
      by_method: {},
      by_day: {},
      by_currency: collectedByCurrency,
      by_method_by_currency: byMethod,
      by_category: byCategory,
      by_channel: byChannel,
      by_day_by_currency: withData ? [
        { date: startDate, currency_code: "ARS", net_collected: 1000 },
        { date: endDate, currency_code: "USD", net_collected: 50 }
      ] : [],
      by_combination: [],
      transactions_count: withData ? 3 : 0
    },
    expected: { total: null, pending: null, reservations_count: 0, currency_code: null, by_currency: [] },
    booked_value: {
      total: withData ? 1500 : 0,
      currency_code: withData ? "ARS" : null,
      by_currency: withData ? [
        { currency_code: "ARS", amount: 1500, reservation_count: 1, booked_night_count: 2 }
      ] : []
    },
    external_ota_collected: {
      by_currency: withData ? [{ currency_code: "USD", amount: 20 }] : [],
      by_channel: withData ? [{ channel_code: "booking_manual", currency_code: "USD", amount: 20 }] : [],
      by_category: [],
      by_combination: []
    },
    receivables: { by_currency: [] }
  };
}

test("owner sees the selected date's weekly revenue states and can export an empty week", async ({ page }) => {
  const revenuePeriods: Array<{ start: string | null; end: string | null }> = [];
  let csvPeriod: { start: string | null; end: string | null } | null = null;
  const weeklyResponseGate: { release?: () => void } = {};

  await page.route("**/api/reports/revenue?*", async (route) => {
    const url = new URL(route.request().url());
    const start = url.searchParams.get("start_date");
    const end = url.searchParams.get("end_date");
    revenuePeriods.push({ start, end });
    if (start === "2026-10-19") {
      await new Promise<void>((resolve) => { weeklyResponseGate.release = resolve; });
    }
    if (start === "2026-10-26") {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Report unavailable" }) });
      return;
    }
    const withData = start !== "2026-10-12";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(revenueFixture(start ?? "", end ?? "", withData))
    });
  });
  await page.route("**/api/reports/revenue/export.csv?*", async (route) => {
    const url = new URL(route.request().url());
    csvPeriod = { start: url.searchParams.get("start_date"), end: url.searchParams.get("end_date") };
    await route.fulfill({
      status: 200,
      contentType: "text/csv",
      body: "tipo,medio_de_pago,categoria,canal,moneda,cobrado_bruto,devoluciones,cobrado_neto,operaciones\n"
    });
  });

  await login(page);
  await page.goto("/reportes");
  const weeklyReport = page.getByTestId("financial-weekly-report");
  await expect(weeklyReport).toBeVisible();
  await expect(page.getByTestId("financial-report").getByRole("heading", { name: "Resumen del día" })).toBeVisible();

  await page.getByLabel("Fecha", { exact: true }).fill("2026-10-07");
  await expect(weeklyReport).toContainText("Período: 2026-10-05 a 2026-10-11 · Lunes a domingo");
  await expect(weeklyReport).toContainText("Zona horaria: America/Argentina/Buenos_Aires");
  await expect(weeklyReport.getByRole("heading", { name: "Cobro neto por día y moneda" })).toBeVisible();
  const dailyCollections = weeklyReport
    .getByRole("heading", { name: "Cobro neto por día y moneda" })
    .locator("xpath=ancestor::section[1]");
  await expect(dailyCollections).toContainText("ARS");
  await expect(dailyCollections).toContainText("USD");
  await expect.poll(() => revenuePeriods.some(({ start, end }) => start === "2026-10-07" && end === "2026-10-07")).toBe(true);
  await expect.poll(() => revenuePeriods.some(({ start, end }) => start === "2026-10-05" && end === "2026-10-11")).toBe(true);

  await page.getByLabel("Fecha", { exact: true }).fill("2026-10-21");
  await expect(weeklyReport).toContainText("Período: 2026-10-19 a 2026-10-25 · Lunes a domingo");
  await expect(page.getByTestId("weekly-revenue-loading")).toBeVisible();
  weeklyResponseGate.release?.();
  await expect(weeklyReport.getByRole("heading", { name: "Cobro neto por día y moneda" })).toBeVisible();

  await page.getByLabel("Fecha", { exact: true }).fill("2026-10-28");
  await expect(page.getByTestId("weekly-revenue-error")).toContainText("No se pudo cargar el reporte financiero semanal");
  let attemptsForFailedWeek = revenuePeriods.filter(({ start }) => start === "2026-10-26").length;
  await page.getByRole("button", { name: "Reintentar semana", exact: true }).click();
  await expect.poll(() => revenuePeriods.filter(({ start }) => start === "2026-10-26").length).toBeGreaterThan(attemptsForFailedWeek);

  await page.getByLabel("Fecha", { exact: true }).fill("2026-10-14");
  await expect(weeklyReport).toContainText("Período: 2026-10-12 a 2026-10-18 · Lunes a domingo");
  await expect(page.getByTestId("weekly-revenue-empty")).toBeVisible();
  const exportButton = page.getByTestId("weekly-revenue-export");
  await expect(exportButton).toBeEnabled();
  const downloadPromise = page.waitForEvent("download");
  await exportButton.click();
  await downloadPromise;
  await expect.poll(() => csvPeriod).toEqual({ start: "2026-10-12", end: "2026-10-18" });
});
