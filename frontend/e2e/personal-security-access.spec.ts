import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const backendURL = (process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040").replace(/\/$/, "");
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

async function readSession(request: APIRequestContext): Promise<TestSession> {
  const response = await request.post(`${backendURL}/api/auth/login`, { data: receptionistCredentials });
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

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(receptionistCredentials.email);
  await page.locator('input[type="password"]').fill(receptionistCredentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("reception can reach personal MFA settings without accessing hotel security overview or events", async ({ page, request }) => {
  const session = await readSession(request);
  const headers = authHeaders(session);

  const mfaStatusResponse = await request.get(`${backendURL}/api/auth/mfa/status`, { headers });
  expect(mfaStatusResponse.status(), await mfaStatusResponse.text()).toBe(200);
  expect(await mfaStatusResponse.json()).toEqual({ enabled: expect.any(Boolean) });

  const securityOverviewResponse = await request.get(`${backendURL}/api/settings/security/overview`, { headers });
  expect(securityOverviewResponse.status()).toBe(403);
  const securityEventsResponse = await request.get(`${backendURL}/api/settings/security/events?limit=20`, { headers });
  expect(securityEventsResponse.status()).toBe(403);

  await login(page);
  await expect(page.getByTestId("session-role")).toHaveText("Recepción");
  const securityRequests: string[] = [];
  let browserMfaStatus = 0;
  page.on("request", (browserRequest) => {
    const pathname = new URL(browserRequest.url()).pathname;
    if (pathname.startsWith("/api/settings/security/")) securityRequests.push(pathname);
  });
  page.on("response", (response) => {
    if (new URL(response.url()).pathname === "/api/auth/mfa/status") browserMfaStatus = response.status();
  });

  await page.getByText("Configuración", { exact: true }).click();
  await page.getByRole("link", { name: "Mi seguridad", exact: true }).click();
  await expect(page).toHaveURL(/\/settings\/my-security$/);
  await expect(page.getByTestId("personal-security-page")).toBeVisible();
  await expect(page.getByTestId("mfa-settings-card")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Mi seguridad", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Eventos recientes", exact: true })).toHaveCount(0);
  await expect(page.getByTestId("security-events")).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Resumen de seguridad" })).toHaveCount(0);
  await expect.poll(() => browserMfaStatus).toBe(200);

  await page.goto("/settings/security");
  await expect(page.getByTestId("permission-denied-page")).toBeVisible();
  expect(securityRequests).toEqual([]);
});
