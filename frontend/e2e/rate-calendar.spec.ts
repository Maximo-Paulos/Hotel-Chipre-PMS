import { expect, test } from "@playwright/test";

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

test("rate calendar page renders read-only grid", async ({ page }) => {
  await page.route("http://127.0.0.1:8040/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (url.pathname.endsWith("/api/auth/login")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: "test-token",
          token_type: "bearer",
          hotel_id: 1,
          hotel_ids: [1],
          user: {
            id: 1,
            email: "owner@example.com",
            role: "manager",
            is_verified: true,
            is_active: true
          }
        })
      });
      return;
    }

    if (url.pathname.endsWith("/api/onboarding/status")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          hotel_id: 1,
          completed: true,
          steps: {},
          missing_steps: [],
          counts: {}
        })
      });
      return;
    }

    if (url.pathname.endsWith("/api/subscription/status")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          hotel_id: 1,
          status: "active",
          plan: "pro",
          room_limit: 40,
          staff_limit: 8,
          rooms_in_use: 10,
          can_write: true,
          limits: []
        })
      });
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

  await page.goto("http://127.0.0.1:5173/login");
  await page.locator('input[type="email"]').fill("owner@example.com");
  await page.locator('input[type="password"]').fill("demo-password");
  await page.getByTestId("login-submit").click();

  await page.waitForURL("**/dashboard");
  await page.getByRole("link", { name: "Tarifas" }).click();
  await page.waitForURL("**/operacion/tarifas");

  await expect(page.getByTestId("rate-calendar-page")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Calendario de tarifas y disponibilidad" })).toBeVisible();
  await expect(page.getByTestId("rate-calendar-grid")).toBeVisible();
  await expect(page.getByText("Booking.com")).toBeVisible();
  await expect(page.getByText("Falta mapeo").first()).toBeVisible();
  await expect(page.getByText("US$ 42")).toBeVisible();
});
