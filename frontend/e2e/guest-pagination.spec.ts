import { expect, test, type Page } from "@playwright/test";

// A5: the backend has always paginated GET /api/guests/ (app/api/guests.py)
// but the frontend never sent skip/limit, so a hotel with >50 guests only
// ever saw the first page with no signal that more existed. This seeds
// enough synthetic guests to cross that 50-guest page boundary and checks
// the UI actually pages through the rest instead of silently truncating.

const credentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

const backendURL = (process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040").replace(/\/$/, "");

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

type StoredSession = { hotelId?: number; userId?: string; accessToken?: string };

async function readSession(page: Page): Promise<StoredSession> {
  const raw = await page.evaluate(() => localStorage.getItem("hotel-pms-session"));
  if (!raw) throw new Error("No session persisted in localStorage after login");
  return JSON.parse(raw) as StoredSession;
}

test("owner pages through >50 synthetic guests instead of only seeing the first 50", async ({ page }) => {
  const suffix = Date.now().toString();
  const prefix = "A5Page" + suffix;
  const TOTAL_SYNTHETIC_GUESTS = 55;

  await login(page);
  const session = await readSession(page);
  const headers = {
    "X-Hotel-Id": String(session.hotelId),
    "X-User-Id": String(session.userId),
    Authorization: `Bearer ${session.accessToken}`,
    "Content-Type": "application/json"
  };

  // Seed synthetic guests directly against the real backend -- creating 55
  // via the UI form would make this spec unreasonably slow for no extra
  // coverage; the pagination contract only cares that the rows exist.
  for (let i = 0; i < TOTAL_SYNTHETIC_GUESTS; i += 1) {
    const response = await page.request.post(`${backendURL}/api/guests/`, {
      headers,
      data: {
        first_name: prefix,
        last_name: `Sintetico${String(i).padStart(3, "0")}`,
        document_type: "DNI",
        document_number: `${prefix}-${i}`
      }
    });
    expect(response.ok()).toBeTruthy();
  }

  await page.goto("/huespedes");
  await page.getByPlaceholder("Buscar por nombre, documento o email").fill(prefix);

  const page1Rows = page.locator("section", { hasText: "Huéspedes del hotel" }).getByRole("button", {
    name: new RegExp(prefix)
  });
  await expect(page1Rows).toHaveCount(50, { timeout: 15_000 });
  const page1Names = await page1Rows.allTextContents();

  await expect(page.getByTestId("guests-page-indicator")).toContainText("Página 1");
  await expect(page.getByTestId("guests-prev-page")).toBeDisabled();
  const nextButton = page.getByTestId("guests-next-page");
  await expect(nextButton).toBeEnabled();

  await nextButton.click();
  await expect(page.getByTestId("guests-page-indicator")).toContainText("Página 2");

  const page2Rows = page.locator("section", { hasText: "Huéspedes del hotel" }).getByRole("button", {
    name: new RegExp(prefix)
  });
  await expect(page2Rows).toHaveCount(5, { timeout: 15_000 });
  const page2Names = await page2Rows.allTextContents();

  // The two pages must not overlap -- this is the actual bug the plan
  // flagged: without skip/limit, "page 2" would just re-show the same 50.
  for (const name of page2Names) {
    expect(page1Names).not.toContain(name);
  }

  await expect(page.getByTestId("guests-next-page")).toBeDisabled();
  await page.getByTestId("guests-prev-page").click();
  await expect(page.getByTestId("guests-page-indicator")).toContainText("Página 1");
  await expect(page1Rows).toHaveCount(50, { timeout: 15_000 });
});
