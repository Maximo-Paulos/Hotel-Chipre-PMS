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

type NightCharge = {
  id: number;
  stay_date: string;
  amount: string | number;
  paid_amount: string | number;
  remaining_due: string | number;
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

test("authorized staff add and audit company nightly extras; reception collects selected nights", async ({ page, browser, request }) => {
  const ownerSession = await readSession(request, ownerCredentials);
  const ownerHeaders = authHeaders(ownerSession);
  const suffix = Date.now().toString();

  const companyResponse = await request.post(`${backendURL}/api/companies`, {
    headers: ownerHeaders,
    data: {
      legal_name: `QA Empresa Adicional ${suffix} SRL`,
      display_name: `QA Empresa Adicional ${suffix}`,
      country_code: "AR",
      payment_deferred: true,
      base_price: 100
    }
  });
  expect(companyResponse.status(), await companyResponse.text()).toBe(201);
  const company = await companyResponse.json() as { id: number };

  const guestResponse = await request.post(`${backendURL}/api/guests/`, {
    headers: ownerHeaders,
    data: { first_name: "Huésped QA", last_name: `Adicional ${suffix}` }
  });
  expect(guestResponse.status(), await guestResponse.text()).toBe(201);
  const guest = await guestResponse.json() as { id: number };

  const categoriesResponse = await request.get(`${backendURL}/api/rooms/categories`, { headers: ownerHeaders });
  expect(categoriesResponse.ok(), await categoriesResponse.text()).toBeTruthy();
  const categories = await categoriesResponse.json() as Array<{ id: number; name: string }>;
  const category = categories.find((item) => item.name === "Standard E2E");
  expect(category).toBeTruthy();

  const tripleCategoryResponse = await request.post(`${backendURL}/api/rooms/categories`, {
    headers: ownerHeaders,
    data: {
      name: `QA Triple ${suffix}`,
      code: `QT${suffix.slice(-10)}`,
      base_price_per_night: 150,
      max_occupancy: 3
    }
  });
  expect(tripleCategoryResponse.status(), await tripleCategoryResponse.text()).toBe(201);
  const tripleCategory = await tripleCategoryResponse.json() as { id: number };
  const tripleRoomResponse = await request.post(`${backendURL}/api/rooms/`, {
    headers: ownerHeaders,
    data: {
      room_number: `T${suffix.slice(-8)}`,
      floor: 9,
      category_id: tripleCategory.id,
      status: "available",
      is_active: true
    }
  });
  expect(tripleRoomResponse.status(), await tripleRoomResponse.text()).toBe(201);
  const tripleRoom = await tripleRoomResponse.json() as { id: number };

  const checkIn = localIsoDate(10);
  const checkOut = localIsoDate(12);
  const secondStayNight = localIsoDate(11);
  const futureRateResponse = await request.post(`${backendURL}/api/companies/${company.id}/nightly-rates`, {
    headers: ownerHeaders,
    data: { effective_from: checkIn, amount: 25 }
  });
  expect(futureRateResponse.status(), await futureRateResponse.text()).toBe(201);
  const midStayRateResponse = await request.post(`${backendURL}/api/companies/${company.id}/nightly-rates`, {
    headers: ownerHeaders,
    data: { effective_from: secondStayNight, amount: 40 }
  });
  expect(midStayRateResponse.status(), await midStayRateResponse.text()).toBe(201);
  const futureRatesResponse = await request.get(`${backendURL}/api/companies/${company.id}/nightly-rates`, {
    headers: ownerHeaders
  });
  expect(futureRatesResponse.ok(), await futureRatesResponse.text()).toBeTruthy();
  const futureRates = await futureRatesResponse.json() as {
    hotel_today: string;
    rates: Array<{ effective_from: string; amount: string | number }>;
  };
  expect(futureRates.hotel_today < checkIn).toBeTruthy();
  const effectiveFutureRate = futureRates.rates.find((rate) => rate.effective_from === checkIn);
  expect(Number(effectiveFutureRate?.amount)).toBe(25);
  const effectiveMidStayRate = futureRates.rates.find((rate) => rate.effective_from === secondStayNight);
  expect(Number(effectiveMidStayRate?.amount)).toBe(40);
  const quoteResponse = await request.get(`${backendURL}/api/bookings/price-quote`, {
    headers: ownerHeaders,
    params: {
      category_id: category!.id,
      check_in_date: checkIn,
      check_out_date: checkOut,
      guest_id: guest.id,
      company_id: company.id,
      occupancy: 2
    }
  });
  expect(quoteResponse.ok(), await quoteResponse.text()).toBeTruthy();
  const quote = await quoteResponse.json() as { quote_token: string; company_billing_deferred: boolean };
  expect(quote.company_billing_deferred).toBe(true);

  const reservationResponse = await request.post(`${backendURL}/api/reservations/`, {
    headers: ownerHeaders,
    data: {
      guest_id: guest.id,
      category_id: category!.id,
      company_id: company.id,
      check_in_date: checkIn,
      check_out_date: checkOut,
      num_adults: 2,
      num_children: 0,
      quote_token: quote.quote_token,
      reservation_comment: "QA: voucher doble con un huésped extra"
    }
  });
  expect(reservationResponse.status(), await reservationResponse.text()).toBe(201);
  const reservation = await reservationResponse.json() as {
    id: number;
    confirmation_code: string;
    total_amount: number | null;
    company_billing_deferred: boolean;
    category_id: number;
    version: number;
  };
  expect(reservation.company_billing_deferred).toBe(true);
  const contractedTotal = reservation.total_amount;

  const roomMoveResponse = await request.post(`${backendURL}/api/reservations/${reservation.id}/room-move`, {
    headers: ownerHeaders,
    data: {
      client_version: reservation.version,
      to_room_id: tripleRoom.id,
      reason_code: "upgrade",
      price_action: "keep"
    }
  });
  expect(roomMoveResponse.ok(), await roomMoveResponse.text()).toBeTruthy();
  const movedReservation = (await roomMoveResponse.json() as {
    reservation: { category_id: number; room_id: number | null; total_amount: number | null; version: number };
  }).reservation;
  expect(movedReservation).toMatchObject({
    category_id: category!.id,
    room_id: tripleRoom.id,
    total_amount: contractedTotal
  });
  const linkedExtraGuests = await request.post(`${backendURL}/api/reservations/${reservation.id}/guests`, {
    headers: ownerHeaders,
    data: [
      { first_name: "Acompañante QA", last_name: `Extra ${suffix}` },
      { first_name: "Tercer huésped QA", last_name: `Extra ${suffix}` }
    ]
  });
  expect(linkedExtraGuests.ok(), await linkedExtraGuests.text()).toBeTruthy();

  await login(page, ownerCredentials);
  await page.goto(`/reservas?reserva=${reservation.id}`);
  const ownerDrawer = page.getByRole("dialog", { name: reservation.confirmation_code });
  await expect(ownerDrawer).toBeVisible();
  await expect(ownerDrawer).toContainText("el voucher");
  await ownerDrawer.getByLabel("Cantidad de personas extra por noche seleccionada").fill("1");
  for (const stayDate of [checkIn, secondStayNight]) {
    await ownerDrawer.getByLabel(`Agregar adicional por huésped extra para la noche ${stayDate}`).check();
  }
  const [createResponse] = await Promise.all([
    page.waitForResponse((response) =>
      response.url().includes(`/api/reservations/${reservation.id}/company-night-charges`) &&
      response.request().method() === "POST"
    ),
    ownerDrawer.getByRole("button", { name: "Registrar adicionales", exact: true }).click()
  ]);
  expect(createResponse.ok(), await createResponse.text()).toBeTruthy();
  expect(createResponse.request().postDataJSON()).toMatchObject({
    stay_dates: [checkIn, secondStayNight],
    extra_person_count: 1
  });
  const createdSummary = await createResponse.json() as { charges: NightCharge[] };
  expect(createdSummary.charges).toHaveLength(2);
  expect(Number(createdSummary.charges.find((charge) => charge.stay_date === checkIn)?.amount)).toBe(25);
  expect(Number(createdSummary.charges.find((charge) => charge.stay_date === secondStayNight)?.amount)).toBe(40);

  await ownerDrawer.getByLabel(`Seleccionar el cargo de la noche ${checkIn} para corregir`).check();
  await ownerDrawer.getByLabel(`Nuevo total para la noche ${checkIn}`).fill("70");
  await ownerDrawer.getByLabel("Motivo de la corrección (se registra en cada noche)").fill("Se confirmó una persona extra en el check-in");
  const [correctionResponse] = await Promise.all([
    page.waitForResponse((response) =>
      response.url().includes(`/api/reservations/${reservation.id}/company-night-charges/corrections`) &&
      response.request().method() === "POST"
    ),
    ownerDrawer.getByRole("button", { name: "Guardar correcciones", exact: true }).click()
  ]);
  expect(correctionResponse.ok(), await correctionResponse.text()).toBeTruthy();
  const correctionPayload = correctionResponse.request().postDataJSON() as {
    items: Array<{ charge_id: number; new_amount: number; reason: string }>;
  };
  expect(correctionPayload.items).toHaveLength(1);
  expect(correctionPayload.items[0]).toMatchObject({ new_amount: 70, reason: "Se confirmó una persona extra en el check-in" });
  await expect(ownerDrawer.getByText("Se corrigieron las noches seleccionadas y quedó registrado el historial.", { exact: true })).toBeVisible();
  await ownerDrawer.getByText("Historial de ajustes (1)").click();
  await expect(ownerDrawer.getByText("Se confirmó una persona extra en el check-in", { exact: true })).toBeVisible();

  const reservationAfterCorrectionResponse = await request.get(`${backendURL}/api/reservations/${reservation.id}`, {
    headers: ownerHeaders
  });
  expect(reservationAfterCorrectionResponse.ok(), await reservationAfterCorrectionResponse.text()).toBeTruthy();
  const reservationAfterCorrection = await reservationAfterCorrectionResponse.json() as { total_amount: number | null };
  expect(reservationAfterCorrection.total_amount).toBe(contractedTotal);

  const receptionistSession = await readSession(request, receptionistCredentials);
  const receptionistHeaders = authHeaders(receptionistSession);
  const cashSessionsResponse = await request.get(`${backendURL}/api/cash-register/sessions`, { headers: receptionistHeaders });
  expect(cashSessionsResponse.ok(), await cashSessionsResponse.text()).toBeTruthy();
  const cashSessions = await cashSessionsResponse.json() as Array<{ status: string; currency_code: string }>;
  if (!cashSessions.some((session) => session.status === "open" && session.currency_code === "ARS")) {
    const openCashResponse = await request.post(`${backendURL}/api/cash-register/sessions`, {
      headers: receptionistHeaders,
      data: { opening_balance: 0, currency_code: "ARS" }
    });
    expect(openCashResponse.status(), await openCashResponse.text()).toBe(201);
  }

  const receptionistPage = await browser.newPage();
  try {
    await login(receptionistPage, receptionistCredentials);
    await expect(receptionistPage.getByTestId("session-role")).toHaveText("Recepción");
    await receptionistPage.goto(`/reservas?reserva=${reservation.id}`);
    const receptionistDrawer = receptionistPage.getByRole("dialog", { name: reservation.confirmation_code });
    await expect(receptionistDrawer).toBeVisible();
    await expect(receptionistDrawer.getByRole("button", { name: "Registrar adicionales", exact: true })).toHaveCount(0);
    await expect(receptionistDrawer.getByLabel(`Seleccionar el cargo de la noche ${checkIn} para corregir`)).toHaveCount(0);
    await receptionistDrawer.getByLabel(`Seleccionar adicional de la noche ${checkIn} para cobrar`).check();
    await expect(receptionistDrawer.getByLabel("Importe a cobrar")).toHaveValue("70.00");
    const [paymentResponse] = await Promise.all([
      receptionistPage.waitForResponse((response) =>
        response.url().includes("/api/payments") && response.request().method() === "POST"
      ),
      receptionistDrawer.getByRole("button", { name: "Registrar cobro", exact: true }).click()
    ]);
    expect(paymentResponse.ok(), await paymentResponse.text()).toBeTruthy();
    const paymentPayload = paymentResponse.request().postDataJSON() as { company_night_charge_ids?: number[] };
    expect(paymentPayload.company_night_charge_ids).toEqual([correctionPayload.items[0].charge_id]);
    await expect(receptionistDrawer.getByText("Pago registrado.", { exact: true })).toBeVisible();
  } finally {
    await receptionistPage.close();
  }

  await page.goto(`/reservas?reserva=${reservation.id}`);
  const ownerAfterPaymentDrawer = page.getByRole("dialog", { name: reservation.confirmation_code });
  await expect(ownerAfterPaymentDrawer).toBeVisible();
  await ownerAfterPaymentDrawer.getByLabel(`Seleccionar el cargo de la noche ${checkIn} para corregir`).check();
  await ownerAfterPaymentDrawer.getByLabel(`Nuevo total para la noche ${checkIn}`).fill("80");
  await ownerAfterPaymentDrawer.getByLabel("Motivo de la corrección (se registra en cada noche)").fill("Corrección autorizada después del cobro");
  const [paidCorrectionResponse] = await Promise.all([
    page.waitForResponse((response) =>
      response.url().includes(`/api/reservations/${reservation.id}/company-night-charges/corrections`) &&
      response.request().method() === "POST"
    ),
    ownerAfterPaymentDrawer.getByRole("button", { name: "Guardar correcciones", exact: true }).click()
  ]);
  expect(paidCorrectionResponse.ok(), await paidCorrectionResponse.text()).toBeTruthy();

  const finalChargesResponse = await request.get(
    `${backendURL}/api/reservations/${reservation.id}/company-night-charges`,
    { headers: ownerHeaders }
  );
  expect(finalChargesResponse.ok(), await finalChargesResponse.text()).toBeTruthy();
  const finalCharges = await finalChargesResponse.json() as { charges: NightCharge[] };
  const correctedPaidNight = finalCharges.charges.find((charge) => charge.stay_date === checkIn);
  expect(correctedPaidNight).toBeTruthy();
  expect(Number(correctedPaidNight!.amount)).toBe(80);
  expect(Number(correctedPaidNight!.paid_amount)).toBe(70);
  expect(Number(correctedPaidNight!.remaining_due)).toBe(10);
});
