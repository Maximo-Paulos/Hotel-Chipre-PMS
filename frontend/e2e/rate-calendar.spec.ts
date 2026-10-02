import { expect, test } from "@playwright/test";

import { revealCollapsedNavLink } from "./support/sidebar";

const ownerCredentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

const mockCategories = [
  {
    id: 7,
    name: "Suite Vista Mar",
    code: "SVM",
    base_price_per_night: 42000,
    max_occupancy: 2
  }
];

const mockCalendar = {
  meta: {
    category_id: 7,
    category_name: "Suite Vista Mar",
    category_code: "SVM",
    total_rooms: 10,
    hotel_currency_code: "ARS",
    date_from: "2026-05-07",
    date_to: "2026-05-09"
  },
  days: [
    {
      date: "2026-05-07",
      is_today: true,
      total_rooms: 10,
      reserved: 8,
      blocked: 0,
      for_sale: 2,
      status: "open",
      occupancy_pct: 80,
      channels: [
        {
          provider_code: "direct",
          provider_label: "Direct",
          currency_code: "ARS",
          missing_mapping: false,
          prices: [
            {
              rate_plan_id: 1,
              rate_plan_code: "BAR",
              rate_plan_name: "BAR",
              base_amount: 42000,
              sales_channel_code: "direct",
              currency_code: "ARS"
            }
          ],
          restrictions: {
            min_stay: 1,
            max_stay: null,
            closed_to_arrival: false,
            closed_to_departure: false,
            allotment: null,
            stop_sell: false
          }
        },
        {
          provider_code: "booking",
          provider_label: "Booking.com",
          currency_code: "ARS",
          missing_mapping: true,
          prices: [],
          restrictions: {
            min_stay: null,
            max_stay: null,
            closed_to_arrival: false,
            closed_to_departure: false,
            allotment: null,
            stop_sell: false
          }
        },
        {
          provider_code: "expedia",
          provider_label: "Expedia",
          currency_code: "USD",
          missing_mapping: false,
          prices: [
            {
              rate_plan_id: 2,
              rate_plan_code: "NRF",
              rate_plan_name: "No reembolsable",
              base_amount: 42,
              sales_channel_code: "expedia",
              currency_code: "USD"
            }
          ],
          restrictions: {
            min_stay: 2,
            max_stay: null,
            closed_to_arrival: false,
            closed_to_departure: true,
            allotment: 3,
            stop_sell: false
          }
        }
      ]
    },
    {
      date: "2026-05-08",
      is_today: false,
      total_rooms: 10,
      reserved: 10,
      blocked: 0,
      for_sale: 0,
      status: "closed",
      occupancy_pct: 100,
      channels: [
        {
          provider_code: "direct",
          provider_label: "Direct",
          currency_code: "ARS",
          missing_mapping: false,
          prices: [
            {
              rate_plan_id: 1,
              rate_plan_code: "BAR",
              rate_plan_name: "BAR",
              base_amount: 43000,
              sales_channel_code: "direct",
              currency_code: "ARS"
            }
          ],
          restrictions: {
            min_stay: 2,
            max_stay: null,
            closed_to_arrival: false,
            closed_to_departure: false,
            allotment: null,
            stop_sell: false
          }
        },
        {
          provider_code: "booking",
          provider_label: "Booking.com",
          currency_code: "ARS",
          missing_mapping: true,
          prices: [],
          restrictions: {
            min_stay: null,
            max_stay: null,
            closed_to_arrival: false,
            closed_to_departure: false,
            allotment: null,
            stop_sell: false
          }
        },
        {
          provider_code: "expedia",
          provider_label: "Expedia",
          currency_code: "USD",
          missing_mapping: false,
          prices: [
            {
              rate_plan_id: 2,
              rate_plan_code: "NRF",
              rate_plan_name: "No reembolsable",
              base_amount: 44,
              sales_channel_code: "expedia",
              currency_code: "USD"
            }
          ],
          restrictions: {
            min_stay: 2,
            max_stay: null,
            closed_to_arrival: true,
            closed_to_departure: false,
            allotment: 2,
            stop_sell: false
          }
        }
      ]
    },
    {
      date: "2026-05-09",
      is_today: false,
      total_rooms: 10,
      reserved: 7,
      blocked: 1,
      for_sale: 2,
      status: "open",
      occupancy_pct: 70,
      channels: [
        {
          provider_code: "direct",
          provider_label: "Direct",
          currency_code: "ARS",
          missing_mapping: false,
          prices: [
            {
              rate_plan_id: 1,
              rate_plan_code: "BAR",
              rate_plan_name: "BAR",
              base_amount: 41000,
              sales_channel_code: "direct",
              currency_code: "ARS"
            }
          ],
          restrictions: {
            min_stay: 1,
            max_stay: null,
            closed_to_arrival: false,
            closed_to_departure: false,
            allotment: null,
            stop_sell: false
          }
        },
        {
          provider_code: "booking",
          provider_label: "Booking.com",
          currency_code: "ARS",
          missing_mapping: true,
          prices: [],
          restrictions: {
            min_stay: null,
            max_stay: null,
            closed_to_arrival: false,
            closed_to_departure: false,
            allotment: null,
            stop_sell: false
          }
        },
        {
          provider_code: "expedia",
          provider_label: "Expedia",
          currency_code: "USD",
          missing_mapping: false,
          prices: [
            {
              rate_plan_id: 2,
              rate_plan_code: "NRF",
              rate_plan_name: "No reembolsable",
              base_amount: 43,
              sales_channel_code: "expedia",
              currency_code: "USD"
            }
          ],
          restrictions: {
            min_stay: 1,
            max_stay: null,
            closed_to_arrival: false,
            closed_to_departure: false,
            allotment: 4,
            stop_sell: false
          }
        }
      ]
    }
  ]
};

const mockDailyRates = [
  {
    date: "2026-05-07",
    price: 42000,
    price_cash: 41000,
    price_transfer: null,
    price_mercadopago: null,
    source: "daily_rate",
    daily_rate_id: 101
  },
  {
    date: "2026-05-08",
    price: 43000,
    price_cash: null,
    price_transfer: null,
    price_mercadopago: null,
    source: "price_period",
    daily_rate_id: null
  },
  {
    date: "2026-05-09",
    price: 41000,
    price_cash: null,
    price_transfer: null,
    price_mercadopago: null,
    source: "category_base",
    daily_rate_id: null
  }
];

test("rate calendar page renders annual editor and integrated channel view", async ({ page }) => {
  const savedCells: unknown[] = [];
  // Model the API's upsert semantics: omitted per-method prices stay as
  // stored when a user updates only the base price.
  const persistedDailyRates = mockDailyRates.map((rate) => ({ ...rate }));
  type MockDraft = {
    id: number;
    hotel_id: number;
    category_id: number;
    draft_type: "daily_rates";
    status: "draft" | "confirmed";
    version: number;
    changes: Array<{
      date: string;
      source_before: string;
      before: Record<string, number | null>;
      after: Record<string, number | null>;
      values: Record<string, number | null>;
    }>;
    impact: { reservations_impacted: number; reservation_nights: number; dates_with_reservations: string[] };
    impact_at_creation: { reservations_impacted: number; reservation_nights: number; dates_with_reservations: string[] };
    created_at: string;
    updated_at: string;
    confirmed_at?: string;
  };
  type DraftCreate = {
    category_id: number;
    draft_type?: "daily_rates";
    changes: Array<{ date: string; values: Record<string, number | null> }>;
  };
  const draftRequests: DraftCreate[] = [];
  let nextDraftId = 500;
  let openDraft: MockDraft | null = null;

  await page.route("https://fonts.googleapis.com/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "text/css", body: "" });
  });
  await page.route("https://fonts.gstatic.com/**", async (route) => {
    await route.abort();
  });

  await page.route("http://127.0.0.1:8040/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    // Authentication, effective permissions, onboarding, and subscription are
    // deliberately exercised against the seeded E2E backend. Only the rate
    // calendar payloads below are synthetic because this test covers their
    // richer OTA/channel rendering.
    if (
      url.pathname.endsWith("/api/auth/login") ||
      url.pathname.endsWith("/api/auth/session/refresh") ||
      url.pathname.endsWith("/api/onboarding/status") ||
      url.pathname.endsWith("/api/permissions/effective") ||
      url.pathname.endsWith("/api/subscription/status")
    ) {
      await route.fallback();
      return;
    }

    if (url.pathname.endsWith("/api/config/")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: 1,
          hotel_name: "Hotel Chipre",
          hotel_timezone: "America/Argentina/Buenos_Aires",
          default_currency: "ARS",
          deposit_percentage: 0,
          free_cancellation_hours: 24,
          cancellation_penalty_percentage: 0,
          enable_full_payment: true,
          enable_deposit_payment: true,
          enable_cash: true,
          enable_mercado_pago: false,
          enable_paypal: false,
          enable_credit_card: false,
          enable_debit_card: false,
          enable_bank_transfer: false,
          enable_booking_sync: true,
          enable_expedia_sync: true,
          allow_cancellation_after_checkin: false,
          require_document_for_checkin: true,
          require_terms_acceptance: true
        })
      });
      return;
    }

    if (url.pathname.endsWith("/api/rooms/categories")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockCategories)
      });
      return;
    }

    if (url.pathname.endsWith("/api/rates/payment-method-options")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          enable_cash: true,
          enable_bank_transfer: true,
          enable_debit_card: false,
          enable_credit_card: false,
          enable_mercado_pago: false,
          enable_paypal: false
        })
      });
      return;
    }

    if (url.pathname.endsWith("/api/rate-change-drafts") && request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(openDraft?.status === "draft" ? [openDraft] : [])
      });
      return;
    }

    if (url.pathname.endsWith("/api/rate-change-drafts") && request.method() === "POST") {
      const payload = request.postDataJSON() as DraftCreate;
      draftRequests.push(payload);
      const now = new Date().toISOString();
      const changes = payload.changes.map((change) => {
        const stored = persistedDailyRates.find((rate) => rate.date === change.date);
        const calendarDay = mockCalendar.days.find((day) => day.date === change.date);
        const calendarBasePrice = calendarDay?.channels.find((channel) => channel.provider_code === "direct")?.prices[0]?.base_amount;
        const before: Record<string, number | null> = {
          price: stored?.price ?? calendarBasePrice ?? 0,
          price_cash: stored?.price_cash ?? null,
          price_transfer: stored?.price_transfer ?? null,
          price_mercadopago: stored?.price_mercadopago ?? null
        };
        return {
          date: change.date,
          source_before: stored?.source ?? "category_base",
          before,
          after: { ...before, ...change.values },
          values: change.values
        };
      });
      const impact = {
        reservations_impacted: changes.some((change) => change.date === "2026-05-07") ? 1 : 0,
        reservation_nights: changes.some((change) => change.date === "2026-05-07") ? 2 : 0,
        dates_with_reservations: changes.some((change) => change.date === "2026-05-07") ? ["2026-05-07"] : []
      };
      openDraft = {
        id: ++nextDraftId,
        hotel_id: 1,
        category_id: payload.category_id,
        draft_type: "daily_rates",
        status: "draft",
        version: 1,
        changes,
        impact,
        impact_at_creation: impact,
        created_at: now,
        updated_at: now
      };
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(openDraft) });
      return;
    }

    const confirmDraftMatch = url.pathname.match(/\/api\/rate-change-drafts\/(\d+)\/confirm$/);
    if (confirmDraftMatch && request.method() === "POST") {
      expect(Number(confirmDraftMatch[1])).toBe(openDraft?.id);
      expect(request.postDataJSON()).toEqual({ expected_version: 1 });
      if (openDraft) {
        for (const change of openDraft.changes) {
          const storedIndex = persistedDailyRates.findIndex((rate) => rate.date === change.date);
          const updatedRate = {
            ...(storedIndex >= 0 ? persistedDailyRates[storedIndex] : {}),
            date: change.date,
            ...change.after,
            source: "daily_rate",
            daily_rate_id: 201
          };
          if (storedIndex >= 0) persistedDailyRates[storedIndex] = updatedRate;
          else persistedDailyRates.push(updatedRate);
        }
        openDraft = { ...openDraft, status: "confirmed", version: 2, confirmed_at: new Date().toISOString() };
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(openDraft) });
      return;
    }

    if (url.pathname.endsWith("/api/rates/category/7/daily") && request.method() === "POST") {
      const payload = request.postDataJSON();
      const storedIndex = persistedDailyRates.findIndex((rate) => rate.date === payload.date);
      const storedRate = storedIndex >= 0
        ? persistedDailyRates[storedIndex]
        : {
            date: payload.date,
            price_cash: null,
            price_transfer: null,
            price_mercadopago: null,
            source: "daily_rate",
            daily_rate_id: 201
          };
      const persistedRate = {
        ...storedRate,
        ...payload,
        source: "daily_rate",
        daily_rate_id: storedRate.daily_rate_id ?? 201
      };
      if (storedIndex >= 0) persistedDailyRates[storedIndex] = persistedRate;
      else persistedDailyRates.push(persistedRate);
      savedCells.push(persistedRate);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: 201,
          hotel_id: 1,
          category_id: 7,
          ...persistedRate
        })
      });
      return;
    }

    if (url.pathname.endsWith("/api/rates/category/7/bulk") && request.method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ created: 1, updated: 0 })
      });
      return;
    }

    if (url.pathname.endsWith("/api/rates/category/7/bulk-field") && request.method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ created: 0, updated: 1 })
      });
      return;
    }

    if (url.pathname.endsWith("/api/rates/category/7") && request.method() === "GET") {
      expect(url.searchParams.get("from_date")).toBeTruthy();
      expect(url.searchParams.get("to_date")).toBeTruthy();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(persistedDailyRates)
      });
      return;
    }

    if (url.pathname.endsWith("/api/rate-calendar/daily")) {
      expect(url.searchParams.get("category_id")).toBe("7");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockCalendar)
      });
      return;
    }

    await route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ detail: `Unhandled mock: ${request.method()} ${url.pathname}` })
    });
  });

  const effectivePermissionsResponsePromise = page.waitForResponse(
    (response) => new URL(response.url()).pathname === "/api/permissions/effective" && response.ok()
  );
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.locator('input[type="email"]').fill(ownerCredentials.email);
  await page.locator('input[type="password"]').fill(ownerCredentials.password);
  await page.getByTestId("login-submit").click();

  await page.waitForURL("**/dashboard");
  const effectivePermissionsResponse = await effectivePermissionsResponsePromise;
  const effectivePermissions = (await effectivePermissionsResponse.json()) as {
    role: string;
    permissions: string[];
  };
  expect(effectivePermissions.role).toBe("owner");
  expect(effectivePermissions.permissions).toEqual(expect.arrayContaining(["rates:read", "rates:update"]));
  // B6.1: Tarifas now lives inside the collapsed "Más operación" sidebar
  // group. A closed <details> removes its content from the accessibility
  // tree, so open it via a plain href locator (which still finds hidden DOM
  // nodes) before using the accessible-role locator to click.
  await revealCollapsedNavLink(page.locator('aside nav a[href="/operacion/tarifas"]'));
  await page.getByRole("link", { name: "Tarifas" }).click();
  await page.waitForURL("**/operacion/tarifas");

  await expect(page.getByTestId("rate-calendar-page")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Calendario de tarifas y disponibilidad" })).toBeVisible();
  const rateEditorGrid = page.getByTestId("rate-editor-grid");
  await expect(rateEditorGrid).toBeVisible();
  // Task 4 added RateEditorMobileCards, a `md:hidden` sibling tree that
  // mounts the same "Precio base <date>" aria-labels for a card-per-day
  // mobile layout (see RateEditorMobileCards.tsx) alongside RateEditorGrid's
  // desktop spreadsheet -- getByLabel finds both regardless of the
  // Tailwind breakpoint that visually hides one, so this desktop-viewport
  // test must scope to the grid to keep resolving a single element.
  await expect(rateEditorGrid.getByLabel("Precio base 2026-05-07")).toBeVisible();
  await expect(page.getByText("Edición masiva")).toBeVisible();
  await expect(page.getByText("Sin cambios pendientes", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toHaveCount(0);
  await expect(page.getByTestId("rate-calendar-grid")).toBeVisible();
  await expect(page.getByText("Direct", { exact: true })).toHaveCount(0);

  const firstBasePrice = rateEditorGrid.getByLabel("Precio base 2026-05-07");
  await expect(firstBasePrice).toHaveValue("42000");
  await firstBasePrice.fill("");
  await firstBasePrice.press("Enter");
  await expect(firstBasePrice).toHaveValue("42000");
  expect(savedCells).toHaveLength(0);

  await firstBasePrice.fill("45000");
  await firstBasePrice.press("Enter");
  await expect(page.getByTestId("rate-change-local-preview")).toBeVisible();
  expect(savedCells).toHaveLength(0);
  await page.getByRole("button", { name: "Guardar borrador", exact: true }).click();
  await expect.poll(() => draftRequests.length).toBe(1);
  expect(draftRequests[0]).toMatchObject({
    category_id: 7,
    changes: [{ date: "2026-05-07", values: { price: 45000 } }]
  });
  await expect(page.getByTestId("rate-change-draft-review")).toContainText("2 noches");
  await page.getByRole("button", { name: "Confirmar tarifas", exact: true }).click();
  await expect.poll(() => openDraft?.status).toBe("confirmed");
  await expect(firstBasePrice).toHaveValue("45000");

  await expect(page.getByText("Booking.com")).toBeVisible();
  await expect(page.getByText("Falta mapeo").first()).toBeVisible();
  await expect(page.getByText("US$ 42")).toBeVisible();

  const rateEditor = page.getByTestId("rate-editor");
  await rateEditor.getByLabel("Desde").fill("2026-05-07");
  await rateEditor.getByLabel("Hasta").fill("2026-05-09");
  await page.getByRole("button", { name: "Días de semana" }).click();
  await page.getByRole("button", { name: "Vie" }).click();
  await page.getByLabel("Precio base *").fill("50000");
  await page.getByTestId("rate-editor-save").click();
  await expect(page.getByTestId("rate-change-local-preview")).toBeVisible();
  await page.getByRole("button", { name: "Guardar borrador", exact: true }).click();
  await expect.poll(() => draftRequests.length).toBe(2);
  expect(draftRequests[1]?.changes).toEqual([{
    date: "2026-05-08",
    values: { price: 50000, price_cash: null, price_transfer: null }
  }]);
  await page.getByRole("button", { name: "Confirmar tarifas", exact: true }).click();
  await expect.poll(() => openDraft?.status).toBe("confirmed");

  await page.getByLabel("Tipo de edición").selectOption("field");
  await page.getByLabel("Campo rápido").selectOption("price_transfer");
  await page.getByLabel("Acción").selectOption("percent_delta");
  await page.getByLabel("Valor").fill("-10");
  await page.getByTestId("rate-editor-save").click();
  await expect(page.getByTestId("rate-change-local-preview")).toBeVisible();
  await page.getByRole("button", { name: "Guardar borrador", exact: true }).click();
  await expect.poll(() => draftRequests.length).toBe(3);
  expect(draftRequests[2]?.changes).toEqual([{ date: "2026-05-08", values: { price_transfer: 45000 } }]);
  await page.getByRole("button", { name: "Confirmar tarifas", exact: true }).click();
  await expect.poll(() => openDraft?.status).toBe("confirmed");
});
