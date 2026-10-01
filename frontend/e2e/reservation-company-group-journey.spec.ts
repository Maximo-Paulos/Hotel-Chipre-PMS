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

test("owner creates a four-room company group and sees its total balance in the reservations screen", async ({ page, request }) => {
  const session = await readSession(request);
  const headers = authHeaders(session);
  const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`;
  const companyName = `QA Grupo ${suffix}`;
  const guestLastName = `Grupo QA ${suffix}`;

  const categoryResponse = await request.get(`${backendURL}/api/rooms/categories`, { headers });
  expect(categoryResponse.ok()).toBeTruthy();
  const categories = await categoryResponse.json() as Array<{ id: number; name: string }>;
  const category = categories.find((item) => item.name === "Standard E2E");
  expect(category).toBeTruthy();

  const roomsResponse = await request.get(`${backendURL}/api/rooms/`, { headers });
  expect(roomsResponse.ok()).toBeTruthy();
  const rooms = await roomsResponse.json() as Array<{ room_number: string; category_id: number; is_active?: boolean }>;
  const activeCategoryRooms = rooms.filter((room) => room.category_id === category!.id && room.is_active !== false);
  for (let index = activeCategoryRooms.length; index < 4; index += 1) {
    const createRoom = await request.post(`${backendURL}/api/rooms/`, {
      headers,
      data: {
        room_number: `9${suffix.slice(-7)}${index}`,
        floor: 9,
        category_id: category!.id,
        status: "available",
        is_active: true
      }
    });
    expect(createRoom.ok()).toBeTruthy();
  }

  const companyResponse = await request.post(`${backendURL}/api/companies`, {
    headers,
    data: { legal_name: `${companyName} SRL`, display_name: companyName, country_code: "AR" }
  });
  expect(companyResponse.status()).toBe(201);
  const company = await companyResponse.json() as { id: number };

  await login(page);
  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  const form = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(form).toBeVisible();
  await form.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
  await form.getByPlaceholder("Nombre").fill("Huésped");
  await form.getByPlaceholder("Apellido").fill(guestLastName);
  await form.getByPlaceholder("Email").fill(`${suffix}@example.test`);
  await form.getByPlaceholder("Teléfono").fill("1112345678");
  await form.getByLabel("Tipo de documento").selectOption("DNI");
  await form.getByPlaceholder("Documento").fill(`GROUP-${suffix}`);
  await form.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();

  const categorySelect = form.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  const categoryValue = await categoryOption.getAttribute("value");
  expect(categoryValue).toBeTruthy();
  await categorySelect.selectOption(categoryValue!);
  await form.getByTestId("reservation-company-select").selectOption(String(company.id));
  await form.getByTestId("reservation-group-size").selectOption("4");

  const salt = Number(suffix.slice(-3));
  const checkIn = localIsoDate(500 + (salt % 30));
  const checkOut = localIsoDate(502 + (salt % 30));
  await form.getByLabel("Check-in", { exact: true }).fill(checkIn);
  await form.getByLabel("Check-out", { exact: true }).fill(checkOut);
  await expect(form.getByTestId("reservation-group-auto-assignment")).toContainText("4 reservas");
  const groupCreateButton = form.getByRole("button", { name: "Crear grupo de 4 habitaciones", exact: true });
  await expect(groupCreateButton).toBeEnabled({ timeout: 20_000 });

  const [groupResponse] = await Promise.all([
    page.waitForResponse((response) => response.url().includes("/api/reservation-groups") && response.request().method() === "POST"),
    groupCreateButton.click()
  ]);
  expect(groupResponse.status()).toBe(201);
  const group = await groupResponse.json() as {
    id: number;
    company_id: number;
    reservation_count: number;
    room_count: number;
    total_amount: number;
    amount_paid: number;
    balance_due: number;
  };
  expect(group.company_id).toBe(company.id);
  expect(group.reservation_count).toBe(4);
  expect(group.room_count).toBe(4);
  expect(Number(group.total_amount)).toBe(800);
  expect(Number(group.amount_paid)).toBe(0);
  expect(Number(group.balance_due)).toBe(800);
  await expect(page.getByText("Grupo creado con 4 reservas independientes", { exact: true })).toBeVisible();

  const summary = page.getByTestId(`reservation-group-summary-${group.id}`);
  await expect(summary).toBeVisible();
  await expect(summary).toContainText(companyName);
  await expect(summary).toContainText("800");
  await page.getByTestId("reservation-company-filter").selectOption(String(company.id));
  const table = page.locator("table").filter({ hasText: "Código" });
  await expect(table.locator("tbody tr").filter({ hasText: guestLastName })).toHaveCount(4);
});
