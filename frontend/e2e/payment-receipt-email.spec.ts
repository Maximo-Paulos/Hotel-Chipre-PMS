import { expect, test } from "@playwright/test";

const backendOrigin = process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040";
const reservationId = 731;
const transactionId = 9021;
const guestId = 551;
const registeredEmail = "registered-guest@example.test";
const permissions = [
  "reservation:read",
  "reservation:update",
  "cash:operate",
  "payment:receipt_email",
  "hotel_settings:read",
  "settings:subscription:view",
  "operations:audit:view"
];

const reservation = {
  id: reservationId,
  confirmation_code: "R11-EMAIL-E2E",
  guest_id: guestId,
  guest: { id: guestId, first_name: "Ana", last_name: "Prueba" },
  room_id: 101,
  room_number: "101",
  category_id: 11,
  category_name: "Habitación de prueba",
  check_in_date: "2026-10-01",
  check_out_date: "2026-10-03",
  total_amount: 120,
  amount_paid: 120,
  deposit_amount: 36,
  balance_due: 0,
  status: "fully_paid",
  source: "direct",
  num_adults: 1,
  num_children: 0,
  currency_code: "USD",
  version: 1,
  allocation_status: "allocated",
  payment_collection_model: "hotel_collect",
  settlement_status: "not_applicable"
};

const transaction = {
  id: transactionId,
  amount: 120,
  applied_amount: 120,
  applied_currency: "USD",
  gross_amount: 120,
  fee_amount: 0,
  currency: "USD",
  method: "cash",
  type: "full_payment",
  status: "completed",
  created_at: "2026-10-01T12:00:00Z"
};

const financialSummary = {
  reservation_id: reservationId,
  confirmation_code: reservation.confirmation_code,
  status: reservation.status,
  currency_code: "USD",
  total_amount: 120,
  deposit_required: 36,
  amount_paid: 120,
  hotel_received_amount: 120,
  ota_prepaid_amount: 0,
  balance_due: 0,
  operational_total_amount: 120,
  operational_balance_due: 0,
  billing_adjustment_total: 0,
  payment_collection_model: "hotel_collect",
  settlement_status: "not_applicable",
  has_financial_reconciliation_gap: false,
  financial_reconciliation_gap: 0,
  recommended_next_action: null,
  transactions: [transaction],
  billing_adjustments: [],
  completed_payments: 1
};

type ReceiptEmailResult = "sent" | "captured" | "failed" | "unknown";
type InterceptedApiRequest = {
  method: string;
  path: string;
  body: unknown;
  idempotencyKey?: string;
};

async function installMocks(
  page: import("@playwright/test").Page,
  results: ReceiptEmailResult | ReceiptEmailResult[]
) {
  const appOrigin = new URL(process.env.E2E_BASE_URL || "http://127.0.0.1:5173").origin;
  const apiRequests: InterceptedApiRequest[] = [];
  const receiptRequests: InterceptedApiRequest[] = [];
  const receiptPdfRequests: InterceptedApiRequest[] = [];
  const receiptEmailResults = typeof results === "string" ? [results] : results;
  const unexpectedApiRequests: string[] = [];
  const blockedExternalRequests: string[] = [];
  const allowedApiPaths = new Set([
    "/api/auth/session/refresh",
    "/api/permissions/effective",
    "/api/reservations/",
    `/api/reservations/${reservationId}`,
    `/api/reservations/${reservationId}/operations-summary`,
    `/api/reservations/${reservationId}/communications`,
    "/api/reservations/actions/pending",
    `/api/payments/summary/${reservationId}`,
    `/api/guests/${guestId}`,
    "/api/room-movement-groups/",
    "/api/rooms/",
    "/api/rooms/categories",
    "/api/config/",
    "/api/config/interface-language",
    "/api/subscription/status",
    "/api/companies/options",
    "/api/reservation-groups",
    "/api/cash/sessions",
    "/api/cash-register/sessions",
    "/api/notifications",
    "/api/events/recovery",
    "/api/events/stream",
    "/api/payment-surcharges",
    "/api/operations/audit"
  ]);

  await page.addInitScript(() => {
    localStorage.setItem("hotel-pms-csrf-token", "local-e2e-csrf");
  });

  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin === backendOrigin) {
      if (request.method() === "OPTIONS") {
        await route.fulfill({
          status: 204,
          headers: {
            "access-control-allow-origin": appOrigin,
            "access-control-allow-credentials": "true",
            "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
            "access-control-allow-headers": "authorization,content-type,x-hotel-id,x-user-id,x-csrf-token,idempotency-key"
          }
        });
        return;
      }

      const path = url.pathname;
      const method = request.method();
      const pathForAllowlist = path.endsWith("/") ? path : path;
      const requestBody = request.postData() ? JSON.parse(request.postData() || "null") as unknown : null;
      let status = 200;
      let body: unknown = [];
      const entry: InterceptedApiRequest = {
        method,
        path,
        body: requestBody,
        idempotencyKey: request.headers()["idempotency-key"]
      };
      apiRequests.push(entry);

      const isReceiptSend = method === "POST" && path === `/api/payments/transactions/${transactionId}/receipt/email`;
      const isReceiptPdfDownload = method === "GET" && path === `/api/payments/transactions/${transactionId}/receipt.pdf`;
      if (isReceiptSend) receiptRequests.push(entry);
      if (isReceiptPdfDownload) receiptPdfRequests.push(entry);
      if (!allowedApiPaths.has(pathForAllowlist) && !isReceiptSend && !isReceiptPdfDownload) {
        unexpectedApiRequests.push(`${method} ${path}`);
      }

      // Receipt email behavior does not depend on realtime. A 403 makes the
      // stream bootstrap exit instead of opening a live connection in this
      // request-contract test.
      if (path === "/api/events/stream") {
        status = 403;
        body = { detail: "Realtime is not part of this request-contract test." };
        await route.fulfill({
          status,
          contentType: "application/json",
          headers: {
            "access-control-allow-origin": appOrigin,
            "access-control-allow-credentials": "true",
            "access-control-allow-headers": "authorization,content-type,x-hotel-id,x-user-id,x-csrf-token,idempotency-key",
            "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS"
          },
          body: JSON.stringify(body)
        });
        return;
      }

      if (isReceiptPdfDownload) {
        await route.fulfill({
          status: 200,
          contentType: "application/pdf",
          headers: {
            "access-control-allow-origin": appOrigin,
            "access-control-allow-credentials": "true",
            "access-control-allow-headers": "authorization,content-type,x-hotel-id,x-user-id,x-csrf-token,idempotency-key",
            "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
            "access-control-expose-headers": "Content-Disposition",
            "content-disposition": `attachment; filename="payment-receipt-${transactionId}.pdf"`
          },
          body: "%PDF-1.4\n% Local E2E PDF fixture\n%%EOF"
        });
        return;
      }

      if (path === "/api/auth/session/refresh") {
        body = {
          access_token: "local-e2e-access-token",
          token_type: "bearer",
          hotel_id: 1,
          hotel_ids: [1],
          user: {
            id: 88,
            email: "owner@local.test",
            role: "owner",
            is_verified: true,
            is_active: true,
            permissions
          },
          permissions,
          csrf_token: "local-e2e-csrf"
        };
      } else if (path === "/api/permissions/effective") {
        body = { hotel_id: 1, role: "owner", permissions };
      } else if (path === "/api/reservations/" && method === "GET") {
        body = [reservation];
      } else if (path === `/api/reservations/${reservationId}` && method === "GET") {
        body = reservation;
      } else if (path === `/api/payments/summary/${reservationId}`) {
        body = {
          reservation_id: reservationId,
          confirmation_code: reservation.confirmation_code,
          status: reservation.status,
          currency_code: "USD",
          total_amount: 120,
          deposit_required: 36,
          amount_paid: 120,
          hotel_received_amount: 120,
          ota_prepaid_amount: 0,
          balance_due: 0,
          operational_total_amount: 120,
          operational_balance_due: 0,
          billing_adjustment_total: 0,
          completed_payments: 1,
          transactions: [transaction]
        };
      } else if (path === `/api/reservations/${reservationId}/operations-summary`) {
        body = {
          reservation_id: reservationId,
          confirmation_code: reservation.confirmation_code,
          status: reservation.status,
          source: "direct",
          allocation_status: "allocated",
          requires_manual_review: false,
          payment_collection_model: "hotel_collect",
          settlement_status: "not_applicable",
          pending_action_count: 0,
          pending_actions: [],
          financial_summary: financialSummary,
          open_adjustments: []
        };
      } else if (path === `/api/guests/${guestId}`) {
        body = {
          id: guestId,
          first_name: "Ana",
          last_name: "Prueba",
          email: registeredEmail,
          phone: "+54 11 5555 0101",
          document_type: "DNI",
          document_number: "TEST-551",
          terms_accepted: true
        };
      } else if (path === `/api/reservations/${reservationId}/communications`) {
        body = [];
      } else if (path === "/api/config/") {
        body = {
          id: 1,
          hotel_name: "Hotel de prueba",
          hotel_timezone: "America/Argentina/Buenos_Aires",
          default_currency: "USD",
          fx_conversion_rate_type: "oficial",
          fx_display_rate_types: ["oficial"],
          deposit_percentage: 30,
          checkin_payment_policy: "deposit",
          free_cancellation_hours: 24,
          cancellation_penalty_percentage: 0,
          enable_full_payment: true,
          enable_deposit_payment: true,
          enable_cash: true,
          enable_mercado_pago: false,
          enable_paypal: false,
          enable_credit_card: true,
          enable_debit_card: true,
          enable_bank_transfer: true,
          enable_booking_sync: false,
          enable_expedia_sync: false,
          enable_despegar_sync: false,
          allow_cancellation_after_checkin: false,
          languages: ["es"],
          jurisdiction_code: "AR",
          interface_language: "es",
          require_document_for_checkin: false,
          require_terms_acceptance: false
        };
      } else if (path === "/api/config/interface-language") {
        body = { interface_language: "es" };
      } else if (path === "/api/subscription/status") {
        body = {
          hotel_id: 1,
          status: "active",
          plan: "pro",
          room_limit: 40,
          staff_limit: 8,
          rooms_in_use: 1,
          can_write: true,
          source: "local-e2e"
        };
      } else if (path === "/api/operations/audit") {
        body = { hotel_id: 1, items: [], total: 0, limit: 50, offset: 0, has_more: false };
      } else if (isReceiptSend) {
        const resultIndex = receiptRequests.length - 1;
        const result = receiptEmailResults[Math.min(resultIndex, receiptEmailResults.length - 1)] ?? "unknown";
        if (result === "sent") {
          body = { transaction_id: transactionId, status: "sent", delivery_mode: "provider", replayed: false };
        } else if (result === "captured") {
          body = { transaction_id: transactionId, status: "captured", delivery_mode: "local_simulation", replayed: false };
        } else if (result === "failed") {
          status = 400;
          body = { detail: "No se pudo enviar el correo indicado." };
        } else {
          status = 503;
          body = {
            detail: "No se pudo confirmar el resultado del envío. Revisá el correo enviado antes de volver a intentar."
          };
        }
      } else if (!allowedApiPaths.has(pathForAllowlist)) {
        status = 501;
        body = { detail: "Unmocked local E2E endpoint" };
      }

      await route.fulfill({
        status,
        contentType: "application/json",
        headers: {
          "access-control-allow-origin": appOrigin,
          "access-control-allow-credentials": "true",
          "access-control-allow-headers": "authorization,content-type,x-hotel-id,x-user-id,x-csrf-token,idempotency-key",
          "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        },
        body: JSON.stringify(body)
      });
      return;
    }

    if (url.origin === appOrigin) {
      await route.continue();
      return;
    }
    blockedExternalRequests.push(url.origin);
    await route.abort();
  });

  return { apiRequests, receiptRequests, receiptPdfRequests, unexpectedApiRequests, blockedExternalRequests };
}

async function openReservationPaymentDetails(page: import("@playwright/test").Page) {
  await page.goto("/reservas");
  await page.getByRole("button", { name: "Ficha", exact: true }).first().click();
  await expect(page.getByTestId(`payment-receipt-email-${transactionId}`)).toBeVisible();
}

test("allows a recipient edit, creates a new idempotency key, and sends only after confirmation", async ({ page }) => {
  const tracker = await installMocks(page, ["failed", "sent"]);
  await openReservationPaymentDetails(page);

  await page.getByTestId(`payment-receipt-email-${transactionId}`).click();
  const dialog = page.getByTestId("payment-receipt-email-dialog");
  await expect(dialog).toBeVisible();
  const recipientInput = dialog.getByLabel("Email de destino");
  await expect(recipientInput).toHaveValue(registeredEmail);
  expect(tracker.receiptRequests).toHaveLength(0);

  const firstRecipient = "facturacion-uno@example.test";
  await recipientInput.fill(firstRecipient);
  await dialog.getByTestId("payment-receipt-email-confirm").click();
  await expect(dialog.getByRole("alert")).toHaveText("El servidor rechazó el envío. Revisá el destinatario y los permisos antes de volver a intentar manualmente.");
  expect(tracker.receiptRequests).toHaveLength(1);
  const firstIdempotencyKey = tracker.receiptRequests[0].idempotencyKey;
  expect(tracker.receiptRequests[0].body).toEqual({ recipient_email: firstRecipient });

  const secondRecipient = "facturacion-dos@example.test";
  await recipientInput.fill(secondRecipient);
  await dialog.getByTestId("payment-receipt-email-confirm").click();
  await expect(dialog.getByRole("status")).toHaveText("El comprobante se envió al correo indicado.");
  expect(tracker.receiptRequests).toHaveLength(2);
  expect(tracker.receiptRequests[1].body).toEqual({ recipient_email: secondRecipient });
  expect(tracker.receiptRequests[1].idempotencyKey).not.toBe(firstIdempotencyKey);
  expect(tracker.receiptRequests[1].idempotencyKey).toMatch(/^ui-payment-receipt-email-9021-/);

  await dialog.getByRole("button", { name: "Cerrar" }).click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByTestId(`payment-receipt-download-${transactionId}`).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(`payment-receipt-${transactionId}.pdf`);
  expect(tracker.receiptPdfRequests).toHaveLength(1);

  await expect(dialog.getByTestId("payment-receipt-email-confirm")).toHaveCount(0);
  expect(
    tracker.apiRequests.filter((request) => request.method === "POST" && request.path.startsWith("/api/payments/") && !request.path.endsWith("/receipt/email"))
  ).toHaveLength(0);

  await page.getByTestId(`payment-receipt-email-${transactionId}`).click();
  await expect(page.getByTestId("payment-receipt-email-confirm")).toHaveCount(0);
  await expect(page.getByTestId("payment-receipt-email-dialog").getByRole("status")).toHaveText(
    "El comprobante se envió al correo indicado."
  );
  expect(tracker.receiptRequests).toHaveLength(2);
  expect(tracker.unexpectedApiRequests).toEqual([]);
  expect(tracker.blockedExternalRequests.every((origin) => origin !== backendOrigin)).toBe(true);
});

test("reports local simulation capture without claiming that an email was sent", async ({ page }) => {
  const tracker = await installMocks(page, "captured");
  await openReservationPaymentDetails(page);
  await page.getByTestId(`payment-receipt-email-${transactionId}`).click();
  const dialog = page.getByTestId("payment-receipt-email-dialog");
  await expect(dialog.getByLabel("Email de destino")).toHaveValue(registeredEmail);
  await dialog.getByTestId("payment-receipt-email-confirm").click();
  const capturedMessage = dialog.getByTestId("payment-receipt-email-captured");
  await expect(capturedMessage).toContainText("No se envió ningún correo fuera de esta máquina.");
  await expect(dialog.getByText("El comprobante se envió al correo indicado.", { exact: true })).toHaveCount(0);
  expect(tracker.receiptRequests[0].body).toEqual({ recipient_email: registeredEmail });
  expect(tracker.unexpectedApiRequests).toEqual([]);
});

test("shows an ambiguous result and never retries automatically", async ({ page }) => {
  const tracker = await installMocks(page, "unknown");
  await openReservationPaymentDetails(page);

  await page.getByTestId(`payment-receipt-email-${transactionId}`).click();
  const dialog = page.getByTestId("payment-receipt-email-dialog");
  await expect(dialog.getByLabel("Email de destino")).toHaveValue(registeredEmail);
  expect(tracker.receiptRequests).toHaveLength(0);

  await dialog.getByTestId("payment-receipt-email-confirm").click();
  await expect(dialog.getByRole("alert")).toHaveText(
    "No se pudo confirmar el resultado del envío. Consultá la actividad registrada antes de intentar de nuevo. No vuelvas a enviarlo desde esta pantalla."
  );
  await expect(page.getByTestId("payment-receipt-email-confirm")).toHaveCount(0);
  await expect(dialog.getByLabel("Email de destino")).toHaveAttribute("readonly", "");
  await expect(page.getByTestId("payment-receipt-email-dialog").getByRole("button", { name: "Cerrar" })).toBeVisible();
  await dialog.getByRole("button", { name: "Cerrar" }).click();
  await page.getByTestId(`payment-receipt-email-${transactionId}`).click();
  await expect(page.getByTestId("payment-receipt-email-dialog").getByRole("alert")).toContainText(
    "No se pudo confirmar el resultado del envío"
  );
  await expect(page.getByTestId("payment-receipt-email-confirm")).toHaveCount(0);
  expect(tracker.receiptRequests).toHaveLength(1);
  expect(
    tracker.apiRequests.filter((request) => request.method === "POST" && request.path.startsWith("/api/payments/") && !request.path.endsWith("/receipt/email"))
  ).toHaveLength(0);
  expect(tracker.unexpectedApiRequests).toEqual([]);
  expect(tracker.blockedExternalRequests.every((origin) => origin !== backendOrigin)).toBe(true);
});
