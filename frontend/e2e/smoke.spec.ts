import { test, expect, APIRequestContext } from "@playwright/test";

const apiBase = process.env.E2E_API_URL || "http://localhost:8000";
const baseUser = "owner@example.com";
const receptionistUser = "reception@example.com";
const hotelId = Number(process.env.E2E_HOTEL_ID || 1);

const authHeaders = (userId: string) => ({
  "X-User-Id": userId,
  "X-Hotel-Id": String(hotelId)
});

async function resetBackend(request: APIRequestContext) {
  await request.post(`${apiBase}/api/reset`);
}

async function ensureOnboarding(request: APIRequestContext, userId: string) {
  const statusResp = await request.get(`${apiBase}/api/onboarding/status`, { headers: authHeaders(userId) });
  const status = await statusResp.json();
  if (status.completed) return;

  await request.post(`${apiBase}/api/onboarding/owner`, {
    headers: authHeaders(userId),
    data: { name: "Owner Demo", email: userId, phone: "123456", role: "Owner" }
  });
  await request.post(`${apiBase}/api/onboarding/categories`, {
    headers: authHeaders(userId),
    data: {
      categories: [
        { name: "Standard Doble", code: "STD", base_price_per_night: 100, max_occupancy: 2 },
        { name: "Suite", code: "STE", base_price_per_night: 180, max_occupancy: 4 }
      ]
    }
  });
  await request.post(`${apiBase}/api/onboarding/rooms`, {
    headers: authHeaders(userId),
    data: {
      rooms: [
        { room_number: "101", floor: 1, category_code: "STD" },
        { room_number: "102", floor: 1, category_code: "STD" },
        { room_number: "201", floor: 2, category_code: "STE" }
      ]
    }
  });
  await request.post(`${apiBase}/api/onboarding/staff`, {
    headers: authHeaders(userId),
    data: {
      staff: [
        { name: "Lucia", role: "Front desk", email: "lucia@example.com" },
        { name: "Javier", role: "Housekeeping", email: "hk@example.com" }
      ]
    }
  });
  await request.post(`${apiBase}/api/onboarding/finish`, { headers: authHeaders(userId) });
}

async function login(page, { email, role = "owner" as const, hotel = hotelId }) {
  await page.goto("/login");
  await page.getByLabel(/Email/i).fill(email);
  await page.getByLabel(/Contrase/i).fill("demo-password");
  await page.getByLabel(/Hotel ID/i).fill(String(hotel));
  await page.getByLabel(/Rol/i).selectOption(role);
  await page.getByTestId("login-submit").click();
}

test.describe.serial("E2E smoke", () => {
  test.beforeAll(async ({ request }) => {
    await resetBackend(request);
  });

  test("1) Login \u2192 onboarding completo \u2192 dashboard", async ({ page, request }) => {
    await login(page, { email: baseUser, role: "owner" });

    await page.waitForURL("**/onboarding**", { timeout: 15000 });

    await page.getByLabel("Nombre completo").fill("Owner Demo");
    await page.getByRole("button", { name: "Guardar y seguir" }).click();

    await page.waitForURL("**/onboarding/categories**");
    await page.getByRole("button", { name: "Guardar y seguir" }).click();

    await page.waitForURL("**/onboarding/rooms**");
    await page.getByRole("button", { name: "Guardar y seguir" }).click();

    await page.waitForURL("**/onboarding/staff**");
    await page.getByRole("button", { name: "Guardar y seguir" }).click();

    await page.waitForURL("**/onboarding/finish**");
    await page.getByRole("button", { name: "Marcar onboarding como completo" }).click();

    await page.waitForURL("**/dashboard", { timeout: 15000 });
    await expect(page.getByText(/Visi/i)).toBeVisible();

    const statusResp = await request.get(`${apiBase}/api/onboarding/status`, { headers: authHeaders(baseUser) });
    const status = await statusResp.json();
    expect(status.completed).toBeTruthy();
  });

  test("2) Cambio de rol owner vs receptionist", async ({ page, request }) => {
    await ensureOnboarding(request, baseUser);
    await login(page, { email: baseUser, role: "owner" });
    await page.waitForURL("**/dashboard", { timeout: 15000 });

    await expect(page.getByRole("link", { name: "Seguridad" })).toBeVisible();
    await page.getByTestId("role-receptionist").click();

    await expect(page.getByTestId("session-role")).toHaveText(/Recepcionista/i);
    await expect(page.getByRole("link", { name: "Seguridad" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Dashboard" })).toBeVisible();
  });

  test("3) Logout visible y funcional", async ({ page, request }) => {
    await ensureOnboarding(request, baseUser);
    await login(page, { email: receptionistUser, role: "receptionist" });
    await page.waitForURL("**/dashboard", { timeout: 15000 });

    await expect(page.getByTestId("logout-btn")).toBeVisible();
    await page.getByTestId("logout-btn").click();
    await page.waitForURL("**/login");
    await expect(page.getByTestId("login-submit")).toBeVisible();
  });
});
