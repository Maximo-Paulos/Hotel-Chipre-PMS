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

async function login(page: Page, credentials: { email: string; password: string }) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("reception can operate company check-in and collect existing extras but cannot change company booking terms", async ({
  page,
  browser,
  request
}) => {
  const ownerSession = await readSession(request, ownerCredentials);
  const ownerHeaders = authHeaders(ownerSession);
  const suffix = Date.now().toString();
  const checkIn = localIsoDate(2);
  const checkOut = localIsoDate(3);

  const companyResponse = await request.post(`${backendURL}/api/companies`, {
    headers: ownerHeaders,
    data: {
      legal_name: `QA Empresa Permisos ${suffix} SRL`,
      display_name: `QA Empresa Permisos ${suffix}`,
      country_code: "AR",
      payment_deferred: true,
      base_price: 100
    }
  });
  expect(companyResponse.status(), await companyResponse.text()).toBe(201);
  const company = await companyResponse.json() as { id: number };

  const guestResponse = await request.post(`${backendURL}/api/guests/`, {
    headers: ownerHeaders,
    data: { first_name: "Huésped QA", last_name: `Permisos ${suffix}` }
  });
  expect(guestResponse.status(), await guestResponse.text()).toBe(201);
  const guest = await guestResponse.json() as { id: number };

  const categoriesResponse = await request.get(`${backendURL}/api/rooms/categories`, { headers: ownerHeaders });
  expect(categoriesResponse.ok(), await categoriesResponse.text()).toBeTruthy();
  const categories = await categoriesResponse.json() as Array<{ id: number; name: string }>;
  const category = categories.find((item) => item.name === "Standard E2E");
  expect(category).toBeTruthy();

  const rateResponse = await request.post(`${backendURL}/api/companies/${company.id}/nightly-rates`, {
    headers: ownerHeaders,
    data: { effective_from: checkIn, amount: 30 }
  });
  expect(rateResponse.status(), await rateResponse.text()).toBe(201);

  const quoteResponse = await request.get(`${backendURL}/api/bookings/price-quote`, {
    headers: ownerHeaders,
    params: {
      category_id: category!.id,
      check_in_date: checkIn,
      check_out_date: checkOut,
      guest_id: guest.id,
      company_id: company.id,
      occupancy: 1
    }
  });
  expect(quoteResponse.ok(), await quoteResponse.text()).toBeTruthy();
  const quote = await quoteResponse.json() as { quote_token: string };

  const reservationResponse = await request.post(`${backendURL}/api/reservations/`, {
    headers: ownerHeaders,
    data: {
      guest_id: guest.id,
      category_id: category!.id,
      company_id: company.id,
      check_in_date: checkIn,
      check_out_date: checkOut,
      num_adults: 1,
      num_children: 0,
      quote_token: quote.quote_token,
      reservation_comment: "QA permiso de reserva de empresa"
    }
  });
  expect(reservationResponse.status(), await reservationResponse.text()).toBe(201);
  const reservation = await reservationResponse.json() as { id: number; confirmation_code: string };

  const additionalGuestResponse = await request.post(`${backendURL}/api/reservations/${reservation.id}/guests`, {
    headers: ownerHeaders,
    data: [{ first_name: "Acompañante QA", last_name: `Adicional ${suffix}` }]
  });
  expect(additionalGuestResponse.ok(), await additionalGuestResponse.text()).toBeTruthy();

  const chargesResponse = await request.post(`${backendURL}/api/reservations/${reservation.id}/company-night-charges`, {
    headers: ownerHeaders,
    data: { stay_dates: [checkIn], extra_person_count: 1 }
  });
  expect(chargesResponse.status(), await chargesResponse.text()).toBe(200);

  await login(page, ownerCredentials);
  await page.goto("/reservas");
  const ownerRow = page.locator("table tbody tr").filter({ hasText: reservation.confirmation_code });
  await expect(ownerRow).toBeVisible();
  await expect(ownerRow.getByRole("button", { name: "Editar", exact: true })).toBeVisible();
  await expect(ownerRow.getByRole("button", { name: "Cancelar", exact: true })).toBeVisible();

  const receptionistPage = await browser.newPage();
  try {
    await login(receptionistPage, receptionistCredentials);
    await expect(receptionistPage.getByTestId("session-role")).toHaveText("Recepción");
    await receptionistPage.goto("/reservas");

    const receptionistRow = receptionistPage.locator("table tbody tr").filter({ hasText: reservation.confirmation_code });
    await expect(receptionistRow).toBeVisible();
    await expect(receptionistRow.getByRole("button", { name: "Editar", exact: true })).toHaveCount(0);
    await expect(receptionistRow.getByRole("button", { name: "Cancelar", exact: true })).toHaveCount(0);
    const mobileCard = receptionistPage.getByText(reservation.confirmation_code, { exact: true }).last().locator("xpath=../../..");
    await expect(mobileCard.getByRole("button", { name: "Editar", exact: true })).toHaveCount(0);
    await expect(mobileCard.getByRole("button", { name: "Cancelar", exact: true })).toHaveCount(0);
    await expect(receptionistRow.getByRole("button", { name: "Check-in", exact: true })).toBeEnabled();

    await receptionistRow.getByRole("button", { name: "Check-in", exact: true }).click();
    const drawer = receptionistPage.getByRole("dialog", { name: reservation.confirmation_code });
    await expect(drawer).toBeVisible();
    await expect(drawer.getByRole("button", { name: "Cancelar", exact: true })).toHaveCount(0);
    await expect(drawer.getByTestId("checkin-capture-form")).toBeVisible();
    await expect(drawer.getByLabel("Nombre del acompañante")).toBeVisible();
    await expect(drawer.getByTestId("company-extension-request")).toBeVisible();
    await expect(drawer.getByLabel(`Seleccionar adicional de la noche ${checkIn} para cobrar`)).toBeVisible();
    await drawer.getByLabel(`Seleccionar adicional de la noche ${checkIn} para cobrar`).check();
    await expect(drawer.getByLabel("Importe a cobrar")).toHaveValue("30.00");
    await expect(drawer.getByRole("button", { name: "Registrar cobro", exact: true })).toBeVisible();

    await drawer.getByRole("button", { name: "Cerrar detalle de reserva" }).click();
    await receptionistRow.getByRole("button", { name: "Ficha", exact: true }).click();
    await expect(receptionistPage.getByRole("button", { name: "Mover habitación", exact: true })).toHaveCount(0);
  } finally {
    await receptionistPage.close();
  }
});
