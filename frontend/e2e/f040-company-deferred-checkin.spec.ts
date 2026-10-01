import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const credentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};
const backendURL = (process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040").replace(/\/$/, "");

type TestSession = {
  hotel_id: number;
  access_token: string;
  csrf_token?: string;
  user: { email: string };
};

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

async function readSession(request: APIRequestContext): Promise<TestSession> {
  const response = await request.post(`${backendURL}/api/auth/login`, { data: credentials });
  expect(response.ok()).toBeTruthy();
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

test("company check-in waits for passenger validation and records extension requests without changing the stay", async ({ page, request }) => {
  const session = await readSession(request);
  const headers = authHeaders(session);
  const suffix = Date.now().toString();

  const companyResponse = await request.post(`${backendURL}/api/companies`, {
    headers,
    data: {
      legal_name: `QA Empresa Diferida ${suffix} SRL`,
      display_name: `QA Empresa Diferida ${suffix}`,
      country_code: "AR",
      payment_deferred: true
    }
  });
  expect(companyResponse.status()).toBe(201, await companyResponse.text());
  const company = await companyResponse.json() as { id: number };

  const guestResponse = await request.post(`${backendURL}/api/guests/`, {
    headers,
    data: { first_name: "Huésped QA", last_name: `Empresa ${suffix}` }
  });
  expect(guestResponse.status()).toBe(201, await guestResponse.text());
  const guest = await guestResponse.json() as { id: number };

  const categoriesResponse = await request.get(`${backendURL}/api/rooms/categories`, { headers });
  expect(categoriesResponse.ok()).toBeTruthy();
  const categories = await categoriesResponse.json() as Array<{ id: number; name: string }>;
  const category = categories.find((item) => item.name === "Standard E2E");
  expect(category).toBeTruthy();

  const checkIn = localIsoDate(0);
  const checkOut = localIsoDate(1);
  const reservationResponse = await request.post(`${backendURL}/api/reservations/`, {
    headers,
    data: {
      guest_id: guest.id,
      category_id: category!.id,
      company_id: company.id,
      check_in_date: checkIn,
      check_out_date: checkOut,
      num_adults: 1,
      num_children: 0,
      total_amount: 100,
      manual_rate_reason: "QA: tarifa de empresa",
      reservation_comment: "QA de check-in corporativo"
    }
  });
  expect(reservationResponse.status()).toBe(201, await reservationResponse.text());
  const reservation = await reservationResponse.json() as {
    id: number;
    confirmation_code: string;
    check_in_date: string;
    check_out_date: string;
    total_amount: number;
  };

  let releaseValidation!: () => void;
  let validationReached!: () => void;
  let validationAttempts = 0;
  const validationGate = new Promise<void>((resolve) => { releaseValidation = resolve; });
  const validationStarted = new Promise<void>((resolve) => { validationReached = resolve; });
  await page.route(`**/api/checkin/validate/${guest.id}`, async (route) => {
    validationAttempts += 1;
    validationReached();
    if (validationAttempts === 1) {
      await validationGate;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "temporary QA validation failure" }) });
      return;
    }
    await route.continue();
  });

  await login(page);
  await page.goto(`/dashboard?reserva=${reservation.id}`);
  const drawer = page.getByRole("dialog", { name: reservation.confirmation_code });
  await expect(drawer).toBeVisible();
  await validationStarted;

  const checkInButton = drawer.getByRole("button", { name: "Confirmar check-in" });
  await expect(checkInButton).toBeDisabled();
  releaseValidation();
  await expect(drawer.getByRole("button", { name: "Reintentar" })).toBeVisible();
  await expect(checkInButton).toBeDisabled();
  await drawer.getByRole("button", { name: "Reintentar" }).click();
  await expect(drawer.getByTestId("checkin-capture-form")).toBeVisible();
  await expect(checkInButton).toBeEnabled();

  const capture = drawer.getByTestId("checkin-capture-form");
  await capture.getByLabel("Tipo de documento").selectOption("DNI");
  await capture.getByLabel("Número de documento").fill(`QA-DNI-${suffix}`);
  await capture.getByLabel("Nacionalidad").fill("Argentina");
  await capture.getByLabel("País", { exact: true }).fill("Argentina");
  await capture.getByLabel("Lugar de nacimiento").fill("Rosario");
  await capture.getByLabel("País de nacimiento").fill("Argentina");
  await capture.getByLabel("Estado civil").fill("Soltero");
  await capture.getByLabel("Profesión").fill("QA");
  await capture.getByRole("checkbox").check();
  await checkInButton.click();
  await expect(drawer.getByText("Check-in registrado.", { exact: true })).toBeVisible();

  const extensionPanel = drawer.getByTestId("company-extension-request");
  await expect(extensionPanel).toContainText("No hay una extensión pendiente");
  const extensionNote = "La empresa pidió extender una noche; falta confirmación";
  await extensionPanel.getByLabel("Pedido o detalle pendiente").fill(extensionNote);
  await extensionPanel.getByRole("button", { name: "Registrar solicitud" }).click();
  await expect(extensionPanel).toContainText("Extensión solicitada, pendiente de confirmación");
  await expect(extensionPanel).toContainText(extensionNote);
  await expect(extensionPanel.getByRole("button", { name: "Quitar solicitud" })).toHaveCount(0);

  const afterRequest = await request.get(`${backendURL}/api/reservations/${reservation.id}`, { headers });
  expect(afterRequest.ok()).toBeTruthy();
  const updated = await afterRequest.json() as typeof reservation & {
    company_extension_request_pending: boolean;
    company_extension_request_note: string;
    amount_paid: number;
  };
  expect(updated.company_extension_request_pending).toBe(true);
  expect(updated.company_extension_request_note).toBe(extensionNote);
  expect(updated.check_in_date).toBe(reservation.check_in_date);
  expect(updated.check_out_date).toBe(reservation.check_out_date);
  expect(updated.total_amount).toBe(reservation.total_amount);
  expect(updated.amount_paid).toBe(0);
});
