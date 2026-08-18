import { expect, test } from "@playwright/test";

const mockCategories = [
  { id: 7, name: "Suite Vista Mar", code: "SVM", base_price_per_night: 42000, max_occupancy: 2 }
];

const createdPromotion = {
  id: 1,
  hotel_id: 1,
  code: "VERANO2026",
  name: "Descuento de verano",
  description: null,
  benefit_type: "percentage",
  benefit_value: "15",
  scope: "full_stay",
  from_night_number: null,
  priority: 0,
  stackable: false,
  is_active: true,
  version: 1,
  previous_version_id: null,
  conditions: {
    booking_from: null,
    booking_to: null,
    stay_from: null,
    stay_to: null,
    min_nights: null,
    max_nights: null,
    weekdays: null,
    category_id: null,
    room_id: null,
    sales_channel_code: null,
    guest_id: null,
    company_id: null,
    guest_tag_type: null,
    payment_currency: null,
    payment_method: null
  },
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  deactivated_at: null
};

const simulateResult = {
  pricing_source: "canonical_daily_rate",
  hotel_id: 1,
  category_id: 7,
  check_in: "2026-05-07",
  check_out: "2026-05-09",
  nights: 2,
  base_currency: "ARS",
  output_currency: "ARS",
  per_night: [
    {
      date: "2026-05-07",
      base_amount: "42000.00",
      promotions_applied: [
        { promotion_id: 1, code: "VERANO2026", version: 1, benefit_type: "percentage", benefit_value: "15", amount_deducted: "6300.00" }
      ],
      post_promotion_amount: "35700.00"
    },
    {
      date: "2026-05-08",
      base_amount: "42000.00",
      promotions_applied: [
        { promotion_id: 1, code: "VERANO2026", version: 1, benefit_type: "percentage", benefit_value: "15", amount_deducted: "6300.00" }
      ],
      post_promotion_amount: "35700.00"
    }
  ],
  promotions_applied: [
    { promotion_id: 1, code: "VERANO2026", version: 1, benefit_type: "percentage", benefit_value: "15", amount_deducted: "6300.00" },
    { promotion_id: 1, code: "VERANO2026", version: 1, benefit_type: "percentage", benefit_value: "15", amount_deducted: "6300.00" }
  ],
  subtotal_amount: "71400.00",
  tax_amount: "0.00",
  fee_amount: "0.00",
  fx_rate_snapshot: null,
  booking_total: "71400.00",
  payment_adjustment: null,
  final_total_with_payment_adjustment: "71400.00"
};

test("owner creates a promotion and simulates its price breakdown", async ({ page }) => {
  let promotionsCreated = false;

  await page.route("https://fonts.googleapis.com/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "text/css", body: "" });
  });
  await page.route("https://fonts.gstatic.com/**", async (route) => {
    await route.abort();
  });

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
          user: { id: 1, email: "owner@example.com", role: "owner", is_verified: true, is_active: true }
        })
      });
      return;
    }
    if (url.pathname.endsWith("/api/onboarding/status")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ hotel_id: 1, completed: true, steps: {}, missing_steps: [], counts: {} })
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
    if (url.pathname.endsWith("/api/permissions/effective")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ hotel_id: 1, role: "owner", permissions: ["promotions:read", "promotions:manage"] })
      });
      return;
    }
    if (url.pathname.endsWith("/api/rooms/categories")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(mockCategories) });
      return;
    }
    if (url.pathname.endsWith("/api/rooms/")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
      return;
    }
    if (url.pathname.endsWith("/api/companies")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
      return;
    }
    if (url.pathname.endsWith("/api/promotions") && request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(promotionsCreated ? [createdPromotion] : [])
      });
      return;
    }
    if (url.pathname.endsWith("/api/promotions") && request.method() === "POST") {
      promotionsCreated = true;
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(createdPromotion) });
      return;
    }
    if (url.pathname.endsWith("/api/promotions/simulate") && request.method() === "POST") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(simulateResult) });
      return;
    }

    await route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ detail: `Unhandled mock: ${request.method()} ${url.pathname}` })
    });
  });

  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.locator('input[type="email"]').fill("owner@example.com");
  await page.locator('input[type="password"]').fill("demo-password");
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard");

  await page.goto("/operacion/promociones");
  await expect(page.getByTestId("promotions-page")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Promociones" })).toBeVisible();
  await expect(page.getByText("No hay promociones creadas todavía.")).toBeVisible();

  await page.getByRole("button", { name: "Nueva promoción", exact: true }).click();
  const form = page.getByTestId("promotion-form");
  await expect(form).toBeVisible();

  await form.getByLabel("Código").fill("VERANO2026");
  await form.getByLabel("Nombre").fill("Descuento de verano");
  await form.getByLabel("Valor").fill("15");
  await form.getByRole("button", { name: "Crear promoción" }).click();

  await expect(form).toBeHidden();
  await expect(page.getByText("Descuento de verano")).toBeVisible();
  await expect(page.getByText("VERANO2026", { exact: false })).toBeVisible();

  const simulator = page.getByTestId("promotion-simulator");
  await simulator.getByLabel("Categoría").selectOption("7");
  await simulator.getByLabel("Check-in").fill("2026-05-07");
  await simulator.getByLabel("Check-out").fill("2026-05-09");
  await simulator.getByRole("button", { name: "Simular" }).click();

  const result = page.getByTestId("promotion-simulator-result");
  await expect(result).toBeVisible();
  await expect(result.getByText("VERANO2026", { exact: false }).first()).toBeVisible();
  await expect(result.getByText(/Total reserva/)).toBeVisible();
});
