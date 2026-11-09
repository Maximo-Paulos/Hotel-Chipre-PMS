import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const backendURL = (process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040").replace(/\/$/, "");
const ownerCredentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};
const receptionistCredentials = {
  email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
  password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!"
};

type TestSession = {
  hotel_id: number;
  access_token: string;
  csrf_token?: string;
  user: { email: string };
};

async function readSession(request: APIRequestContext, credentials: { email: string; password: string }) {
  const response = await request.post(`${backendURL}/api/auth/login`, { data: credentials });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json() as Promise<TestSession>;
}

function authHeaders(session: TestSession) {
  return {
    "X-Hotel-Id": String(session.hotel_id),
    "X-User-Id": session.user.email,
    Authorization: `Bearer ${session.access_token}`,
    "X-CSRF-Token": String(session.csrf_token || ""),
    "Content-Type": "application/json"
  };
}

function localIsoDate(offsetDays: number) {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(receptionistCredentials.email);
  await page.locator('input[type="password"]').fill(receptionistCredentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("cash-restricted reception sees no payment blocker for a paid reservation", async ({ browser, request }) => {
  const ownerSession = await readSession(request, ownerCredentials);
  const ownerHeaders = authHeaders(ownerSession);
  const suffix = Date.now().toString();
  const checkIn = localIsoDate(0);
  const checkOut = localIsoDate(1);

  const guestResponse = await request.post(`${backendURL}/api/guests/`, {
    headers: ownerHeaders,
    data: { first_name: "QA Llegada", last_name: `Sin caja ${suffix}` }
  });
  expect(guestResponse.status(), await guestResponse.text()).toBe(201);
  const guest = await guestResponse.json() as { id: number };

  const categoriesResponse = await request.get(`${backendURL}/api/rooms/categories`, { headers: ownerHeaders });
  expect(categoriesResponse.ok(), await categoriesResponse.text()).toBeTruthy();
  const categories = await categoriesResponse.json() as Array<{ id: number; name: string }>;
  const category = categories.find((item) => item.name === "Standard E2E");
  expect(category).toBeTruthy();

  const roomResponse = await request.post(`${backendURL}/api/rooms/`, {
    headers: ownerHeaders,
    data: {
      room_number: `QC${suffix.slice(-7)}`,
      floor: 1,
      category_id: category!.id,
      status: "available"
    }
  });
  expect(roomResponse.status(), await roomResponse.text()).toBe(201);
  const room = await roomResponse.json() as { id: number };

  const priceQuoteResponse = await request.get(`${backendURL}/api/bookings/price-quote`, {
    headers: ownerHeaders,
    params: {
      category_id: category!.id,
      check_in_date: checkIn,
      check_out_date: checkOut,
      guest_id: guest.id,
      occupancy: 1
    }
  });
  expect(priceQuoteResponse.ok(), await priceQuoteResponse.text()).toBeTruthy();
  const priceQuote = await priceQuoteResponse.json() as { quote_token: string };

  const reservationResponse = await request.post(`${backendURL}/api/reservations/`, {
    headers: ownerHeaders,
    data: {
      guest_id: guest.id,
      category_id: category!.id,
      room_id: room.id,
      check_in_date: checkIn,
      check_out_date: checkOut,
      num_adults: 1,
      num_children: 0,
      quote_token: priceQuote.quote_token,
      reservation_comment: "QA: saldo cancelado, términos sin aceptar"
    }
  });
  expect(reservationResponse.status(), await reservationResponse.text()).toBe(201);
  const reservation = await reservationResponse.json() as { id: number; confirmation_code: string };

  const initialSummaryResponse = await request.get(`${backendURL}/api/payments/summary/${reservation.id}`, {
    headers: ownerHeaders
  });
  expect(initialSummaryResponse.ok(), await initialSummaryResponse.text()).toBeTruthy();
  const initialSummary = await initialSummaryResponse.json() as { operational_balance_due?: number; balance_due: number };
  const amountDue = Number(initialSummary.operational_balance_due ?? initialSummary.balance_due);
  expect(amountDue).toBeGreaterThan(0);

  const paymentQuoteResponse = await request.post(`${backendURL}/api/payment-surcharges/quote`, {
    headers: ownerHeaders,
    data: {
      reservation_id: reservation.id,
      payment_method: "bank_transfer",
      currency_code: "ARS",
      base_amount: amountDue
    }
  });
  expect(paymentQuoteResponse.ok(), await paymentQuoteResponse.text()).toBeTruthy();
  const paymentQuote = await paymentQuoteResponse.json() as { base_amount: number; payment_quote_token: string };

  const paymentResponse = await request.post(`${backendURL}/api/payments`, {
    headers: { ...ownerHeaders, "Idempotency-Key": `qa-cashless-${suffix}` },
    data: {
      reservation_id: reservation.id,
      amount: paymentQuote.base_amount,
      payment_method: "bank_transfer",
      transaction_type: "full_payment",
      currency: "ARS",
      manual_reference: `QA-CASHLESS-${suffix}`,
      payment_quote_token: paymentQuote.payment_quote_token
    }
  });
  expect(paymentResponse.status(), await paymentResponse.text()).toBe(201);

  const receptionistPage = await browser.newPage();
  try {
    await receptionistPage.route("**/api/permissions/effective", async (route) => {
      const response = await route.fetch();
      const permissions = await response.json() as { permissions: string[] };
      await route.fulfill({
        response,
        json: { ...permissions, permissions: permissions.permissions.filter((permission) => permission !== "cash:operate") }
      });
    });
    await login(receptionistPage);
    await receptionistPage.goto(`/reservas?reserva=${reservation.id}`);

    const drawer = receptionistPage.getByRole("dialog", { name: reservation.confirmation_code });
    await expect(drawer).toBeVisible();
    await expect(drawer.getByText("Pago completo", { exact: true })).toBeVisible();
    await expect(drawer.getByTestId("drawer-balance-due")).toHaveText(/0/);
    await expect(drawer.getByTestId("reservation-drawer-payment-permission-required")).toHaveCount(0);
    await expect(drawer.getByTestId("reservation-drawer-payment-no-collection-required")).toContainText(
      "No hay cobros pendientes"
    );
    await expect(drawer.getByLabel("Método de pago")).toHaveCount(0);
    await expect(drawer.getByTestId("checkin-capture-form").getByLabel("Acepta términos y condiciones", { exact: true }))
      .not.toBeChecked();
    await expect(drawer.getByRole("button", { name: "Confirmar check-in", exact: true })).toBeDisabled();
    await expect(drawer.getByTestId("checkin-capture-form").getByRole("list")).toContainText(
      "Confirmá la aceptación de términos y condiciones."
    );
  } finally {
    await receptionistPage.close();
  }
});
