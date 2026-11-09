import { expect, test, type Page } from "@playwright/test";

const ownerEmail = process.env.E2E_OWNER_EMAIL || "owner@e2e.com";
const ownerPassword = process.env.E2E_OWNER_PASSWORD || "E2ePass1234!";

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(ownerEmail);
  await page.locator('input[type="password"]').fill(ownerPassword);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

async function mockInterfaceLanguage(page: Page, language: "en" | "es") {
  await page.route("**/api/config/**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith("/interface-language")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ interface_language: language })
      });
      return;
    }
    const response = await route.fetch();
    const config = await response.json();
    await route.fulfill({ response, body: JSON.stringify({ ...config, interface_language: language }) });
  });
}

test("owner opens analytics summary with an explicit unavailable freshness state", async ({ page }) => {
  await login(page);
  await page.goto("/analytics");

  await expect(page.getByRole("heading", { name: "Analítica", exact: true })).toBeVisible();
  await expect(page.getByRole("status", { name: /Fuente PostgreSQL\. Fecha del dato incluido más antiguo no disponible/ })).toBeVisible();
  await expect(page.getByText("Cargando analytics...", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("analytics freshness label explains the oldest included data timestamp in English", async ({ page }) => {
  await mockInterfaceLanguage(page, "en");
  await page.route("**/api/analytics/home**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        hotel_id: 1,
        date_from: "2026-07-01",
        date_to: "2026-07-31",
        generated_at: "2026-07-31T12:00:00Z",
        data_as_of: "2026-07-24T10:00:00Z",
        source_lag_seconds: 604800,
        data_source: "postgresql",
        data: { cards: [] }
      })
    });
  });

  await login(page);
  await page.goto("/analytics");

  const freshness = page.getByRole("status", { name: /Source PostgreSQL/ });
  await expect(freshness).toContainText("Oldest included data was updated");
  await expect(freshness).not.toContainText(/lag|behind|delayed|out of date/i);
});

test("operations keeps rendering when a legacy analytics response omits data_source", async ({ page }) => {
  await page.route("**/api/analytics/operations**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        hotel_id: 1,
        date_from: "2026-07-01",
        date_to: "2026-07-24",
        generated_at: "2026-07-24T12:00:00Z",
        data_as_of: "2026-07-24T12:00:00Z",
        source_lag_seconds: 0,
        data: { cards: [] }
      })
    });
  });

  await login(page);
  await page.goto("/analytics/operations");

  await expect(page.getByRole("heading", { name: "Operaciones", exact: true })).toBeVisible();
  await expect(page.getByRole("status", { name: /Fuente PostgreSQL\. Dato incluido más antiguo actualizado el/ })).toBeVisible();
  await expect(page.getByText("Unexpected Application Error!", { exact: true })).toHaveCount(0);
});

test("operations renders room event labels in Spanish", async ({ page }) => {
  await mockInterfaceLanguage(page, "es");
  await page.route("**/api/analytics/operations**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        hotel_id: 1,
        date_from: "2026-11-01",
        date_to: "2026-11-08",
        generated_at: "2026-11-08T12:00:00Z",
        data_as_of: "2026-11-08T12:00:00Z",
        source_lag_seconds: 0,
        data_source: "postgresql",
        data: {
          cards: [],
          room_events_open: [{
            room_id: 42,
            event_type: "maintenance",
            reason_code: "inspection",
            created_by_user_id: 7,
            closed_by_user_id: 8,
            row_kind: "room_state_event"
          }]
        }
      })
    });
  });

  await login(page);
  await page.goto("/analytics/operations");

  await expect(page.getByRole("heading", { name: "Eventos de habitación abiertos", exact: true })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "ID habitación", exact: true })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "ID de usuario creador", exact: true })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "ID de usuario que cerró", exact: true })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Tipo de registro", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Mantenimiento", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Inspección", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "maintenance", exact: true })).toHaveCount(0);
  await expect(page.getByRole("cell", { name: "inspection", exact: true })).toHaveCount(0);
  await expect(page.getByText(/Room Events Open|Created By User Id|Closed By User Id|Row Kind/)).toHaveCount(0);
});

test("analytics marks a missing historical currency quote as unavailable without changing other metrics", async ({ page }) => {
  await mockInterfaceLanguage(page, "es");
  await page.route("**/api/analytics/home**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        hotel_id: 1,
        date_from: "2026-01-01",
        date_to: "2026-01-31",
        generated_at: "2026-01-31T12:00:00Z",
        data_as_of: "2026-01-31T12:00:00Z",
        source_lag_seconds: 0,
        data_source: "postgresql",
        data: {
          cards: [{ card_code: "test_nights", label: "Noches", value_count: 42 }],
          top_channels: [{
            channel_code: "booking",
            revenue_gross_usd: "100.00",
            source_currency: "ARS",
            fx_rate_snapshot: null,
            unavailable_currencies: ["USD"]
          }]
        }
      })
    });
  });

  await login(page);
  await page.goto("/analytics");

  await expect(page.getByRole("heading", { name: "Analítica", exact: true })).toBeVisible();
  await expect(page.getByText("No disponible", { exact: true })).toHaveCount(0);
  await page.getByLabel("Moneda").selectOption("USD");
  await expect(page.getByText("No disponible", { exact: true })).toBeVisible();
  await expect(page.getByText("42", { exact: true })).toBeVisible();
  await expect(page.getByText("Sin cotización histórica", { exact: true })).toHaveCount(0);
});

test("analytics home switches monetary cards between stored ARS and USD values", async ({ page }) => {
  await page.route("**/api/analytics/home**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        hotel_id: 1,
        date_from: "2026-11-01",
        date_to: "2026-11-05",
        generated_at: "2026-11-05T12:00:00Z",
        data_as_of: "2026-11-05T12:00:00Z",
        source_lag_seconds: 0,
        data_source: "postgresql",
        data: {
          cards: [
            {
              card_code: "home_revenue_gross",
              label: "Revenue bruto",
              value_ars: "1000000.00",
              value_ars_available: true,
              value_usd: "1000.00",
              value_usd_available: true
            },
            {
              card_code: "home_adr",
              label: "ADR",
              value_ars: "250000.00",
              value_ars_available: true,
              value_usd_available: false
            },
            { card_code: "home_no_shows", label: "No-shows", value_count: 2 }
          ],
          top_channels: [],
          segments: []
        }
      })
    });
  });

  await login(page);
  await page.goto("/analytics");

  const grossCard = page.getByText("Revenue bruto").locator("..");
  await expect(grossCard).toContainText(/1\.000\.000/);
  await page.getByLabel("Moneda").selectOption("USD");
  await expect(grossCard).toContainText("US$");
  await expect(grossCard).toContainText(/1\.000/);
  await expect(grossCard).not.toContainText(/1\.000\.000/);
  await expect(page.getByText("ADR").locator("..")).toContainText("No disponible");

  await page.getByLabel("Moneda").selectOption("BOTH");
  await expect(grossCard).toContainText("ARS");
  await expect(grossCard).toContainText("USD");
  await expect(grossCard).toContainText(/1\.000\.000/);
  await expect(grossCard).toContainText("US$");
  await expect(page.getByText("No-shows").locator("..")).toContainText("2");
});

test("analytics renders requested period comparisons and explicit unavailable states", async ({ page }) => {
  await page.route("**/api/analytics/home**", async (route) => {
    const url = new URL(route.request().url());
    const comparePrevious = url.searchParams.get("compare_previous") === "true";
    const compareYoy = url.searchParams.get("compare_yoy") === "true";
    const previousMetrics = [
      {
        card_code: "home_revenue_gross",
        label: "Revenue bruto",
        value_ars: "100000.00",
        value_ars_available: true,
        value_usd: "1000.00",
        value_usd_available: true
      },
      { card_code: "home_occupancy", label: "Ocupación promedio", value_pct: 40 },
      { card_code: "home_no_shows", label: "No-shows", value_count: 1 }
    ];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        hotel_id: 1,
        date_from: "2026-11-01",
        date_to: "2026-11-05",
        generated_at: "2026-11-05T12:00:00Z",
        data_as_of: "2026-11-05T12:00:00Z",
        source_lag_seconds: 0,
        data_source: "postgresql",
        comparison: {
          previous: {
            requested: comparePrevious,
            available: comparePrevious,
            metrics_available: comparePrevious,
            date_from: comparePrevious ? "2026-10-27" : null,
            date_to: comparePrevious ? "2026-10-31" : null,
            metrics: comparePrevious ? previousMetrics : []
          },
          yoy: {
            requested: compareYoy,
            available: false,
            metrics_available: false,
            date_from: compareYoy ? "2025-11-01" : null,
            date_to: compareYoy ? "2025-11-05" : null,
            metrics: []
          }
        },
        data: {
          cards: [
            {
              card_code: "home_revenue_gross",
              label: "Revenue bruto",
              value_ars: "200000.00",
              value_ars_available: true,
              value_usd: "2000.00",
              value_usd_available: true
            },
            { card_code: "home_occupancy", label: "Ocupación promedio", value_pct: 50 },
            { card_code: "home_no_shows", label: "No-shows", value_count: 2 }
          ],
          top_channels: [],
          segments: []
        }
      })
    });
  });

  await page.route("**/api/analytics/**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith("/home")) {
      await route.fallback();
      return;
    }
    const url = new URL(route.request().url());
    const comparePrevious = url.searchParams.get("compare_previous") === "true";
    const compareYoy = url.searchParams.get("compare_yoy") === "true";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        hotel_id: 1,
        date_from: "2026-11-01",
        date_to: "2026-11-05",
        generated_at: "2026-11-05T12:00:00Z",
        data_as_of: "2026-11-05T12:00:00Z",
        source_lag_seconds: 0,
        data_source: "postgresql",
        comparison: {
          previous: {
            requested: comparePrevious,
            available: comparePrevious,
            metrics_available: comparePrevious,
            date_from: comparePrevious ? "2026-10-27" : null,
            date_to: comparePrevious ? "2026-10-31" : null,
            metrics: comparePrevious ? [{ card_code: "report_occupancy", label: "Ocupación", value_pct: 39 }] : []
          },
          yoy: { requested: compareYoy, available: false, metrics_available: false, metrics: [] }
        },
        data: { cards: [{ card_code: "report_occupancy", label: "Ocupación", value_pct: 42 }] }
      })
    });
  });

  await login(page);
  await page.goto("/analytics");

  const previousComparison = page.getByTestId("analytics-comparison-previous");
  await expect(previousComparison).toContainText("Comparación con el período anterior");
  await expect(previousComparison).toContainText("Período de referencia:");
  await expect(previousComparison).toContainText("100.000");
  await expect(previousComparison).toContainText("Cambio:");
  await expect(previousComparison).toContainText("100%");
  await expect(previousComparison).toContainText("+10 pp");
  await expect(previousComparison).toContainText("+1");

  await page.getByLabel("Moneda").selectOption("USD");
  await expect(previousComparison).toContainText("USD:");
  await expect(previousComparison).toContainText("1.000");
  await page.getByLabel("Moneda").selectOption("BOTH");
  await expect(previousComparison).toContainText("ARS:");
  await expect(previousComparison).toContainText("USD:");

  await page.getByLabel("Comparar interanual").check();
  const yoyComparison = page.getByTestId("analytics-comparison-yoy");
  await expect(yoyComparison).toContainText("Comparación interanual");
  await expect(yoyComparison).toContainText("No hay datos disponibles para comparar este período.");

  await page.getByLabel("Comparar con el período anterior").uncheck();
  await page.getByLabel("Comparar interanual").uncheck();
  await expect(page.getByText("No solicitada. Activá esta comparación arriba para cargar valores de referencia.")).toHaveCount(2);

  for (const path of [
    "/analytics/rooms",
    "/analytics/rooms/1",
    "/analytics/categories/1",
    "/analytics/segments",
    "/analytics/companies/1",
    "/analytics/channels",
    "/analytics/operations"
  ]) {
    await page.goto(path);
    const routeComparison = page.getByTestId("analytics-comparison-previous");
    await expect(routeComparison).toContainText("Comparación con el período anterior");
    await expect(routeComparison).toContainText("Ocupación");
    await expect(routeComparison).toContainText("39%");
    await expect(routeComparison).toContainText("+3 pp");
  }
});

test("analytics count comparisons subtract the reference period", async ({ page }) => {
  await page.route("**/api/analytics/rooms**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        hotel_id: 1,
        date_from: "2026-11-08",
        date_to: "2026-11-08",
        generated_at: "2026-11-08T12:00:00Z",
        data_as_of: "2026-11-08T12:00:00Z",
        data_source: "postgresql",
        comparison: {
          previous: {
            requested: true,
            available: true,
            metrics_available: true,
            date_from: "2026-11-07",
            date_to: "2026-11-07",
            metrics: [
              { card_code: "rooms_total", label: "Habitaciones activas", value_count: 39 },
              { card_code: "rooms_occupied", label: "Noches ocupadas", value_count: 1 },
              { card_code: "rooms_maintenance", label: "Habitaciones en mantenimiento", value_count: 5 },
              { card_code: "rooms_zero", label: "Conteo cero", value_count: 0 },
              { card_code: "rooms_missing", label: "Sin referencia", value_count: null }
            ]
          },
          yoy: { requested: false, available: false, metrics: [] }
        },
        data: {
          cards: [
            { card_code: "rooms_total", label: "Habitaciones activas", value_count: 39 },
            { card_code: "rooms_occupied", label: "Noches ocupadas", value_count: 7 },
            { card_code: "rooms_maintenance", label: "Habitaciones en mantenimiento", value_count: 2 },
            { card_code: "rooms_zero", label: "Conteo cero", value_count: 0 },
            { card_code: "rooms_missing", label: "Sin referencia", value_count: 5 }
          ],
          rooms: []
        }
      })
    });
  });

  await login(page);
  await page.goto("/analytics/rooms");

  const previousComparison = page.getByTestId("analytics-comparison-previous");
  const rows = previousComparison.getByRole("listitem");
  const activeRooms = rows.filter({ hasText: "Habitaciones activas" });
  const occupiedNights = rows.filter({ hasText: "Noches ocupadas" });
  const maintenanceRooms = rows.filter({ hasText: "Habitaciones en mantenimiento" });
  const zeroCount = rows.filter({ hasText: "Conteo cero" });
  const missingReference = rows.filter({ hasText: "Sin referencia" });

  await expect(activeRooms).toContainText("39");
  await expect(activeRooms).toContainText("Cambio: 0");
  await expect(activeRooms).not.toContainText("+39");
  await expect(occupiedNights).toContainText("1");
  await expect(occupiedNights).toContainText("+6");
  await expect(occupiedNights).not.toContainText("+7");
  await expect(maintenanceRooms).toContainText("−3");
  await expect(zeroCount).toContainText("0");
  await expect(zeroCount).toContainText("Cambio: 0");
  await expect(zeroCount).not.toContainText("+0");
  await expect(missingReference).toContainText("No disponible");
});
