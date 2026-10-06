import { expect, test, type Page } from "@playwright/test";

const ownerEmail = process.env.E2E_OWNER_EMAIL || "owner@e2e.com";
const ownerPassword = process.env.E2E_OWNER_PASSWORD || "E2ePass1234!";
const reservationId = 987654321;

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(ownerEmail);
  await page.locator('input[type="password"]').fill(ownerPassword);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("refund_deposit review CTA opens the existing payment form without issuing a refund", async ({ page }) => {
  await login(page);

  let paymentWrites = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && new URL(request.url()).pathname === "/api/payments") {
      paymentWrites += 1;
    }
  });

  await page.route("**/api/reservations/actions/pending**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          action_key: "refund_deposit",
          code: "refund_deposit",
          priority: "high",
          title: "Revisar devolución pendiente de Huésped QA — sale 2026-10-08",
          detail: "Hay ARS 25.00 de pagos netos registrados. La devolución debe revisarse manualmente.",
          reservation_id: reservationId,
          confirmation_code: "QA-REFUND-REVIEW",
          guest_name: "Huésped QA",
          reservation_status: "cancelled",
          source: "direct",
          source_provider_code: null,
          payment_collection_model: "hotel_collect",
          settlement_status: "not_applicable",
          check_in_date: "2026-10-07",
          check_out_date: "2026-10-08",
          reference_type: null,
          reference_id: null
        }
      ])
    })
  );

  await page.route(`**/api/reservations/${reservationId}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: reservationId,
        confirmation_code: "QA-REFUND-REVIEW",
        guest_id: 1,
        guest: { id: 1, first_name: "Huésped", last_name: "QA" },
        room_id: null,
        category_id: 1,
        category_name: "Standard",
        check_in_date: "2026-10-07",
        check_out_date: "2026-10-08",
        total_amount: 100,
        amount_paid: 25,
        deposit_amount: 25,
        status: "cancelled",
        source: "direct",
        num_adults: 1,
        num_children: 0,
        currency_code: "ARS",
        allocation_status: "assigned",
        payment_collection_model: "hotel_collect",
        settlement_status: "not_applicable",
        version: 1
      })
    })
  );

  await page.route(`**/api/payments/summary/${reservationId}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        reservation_id: reservationId,
        confirmation_code: "QA-REFUND-REVIEW",
        status: "cancelled",
        currency_code: "ARS",
        total_amount: 100,
        deposit_required: 25,
        amount_paid: 25,
        balance_due: 75,
        operational_total_amount: 100,
        operational_balance_due: 75,
        company_billing_deferred: false,
        completed_payments: 25,
        transactions: [
          {
            id: 987654322,
            amount: 25,
            currency: "ARS",
            method: "cash",
            type: "deposit",
            status: "completed",
            created_at: "2026-10-05T12:00:00Z"
          }
        ]
      })
    })
  );

  await page.goto("/reservas");
  const reviewButton = page.getByTestId(`pending-action-review-refund-${reservationId}`);
  await expect(reviewButton).toHaveText("Revisar devolución");
  await reviewButton.click();

  const refundButton = page.getByRole("button", { name: "Registrar devolución", exact: true });
  await expect(refundButton).toBeVisible();
  await expect(refundButton).toBeDisabled();
  await expect(page.getByText("Devolución registrada", { exact: true })).toHaveCount(0);
  await expect(reviewButton).toHaveText("Revisar devolución");
  expect(paymentWrites).toBe(0);
});
