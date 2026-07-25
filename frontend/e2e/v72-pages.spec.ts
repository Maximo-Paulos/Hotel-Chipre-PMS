import { expect, test, type Locator, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";

const credentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

// Each V72 page: navigate through the visible app shell link, keep the real
// authenticated session, and use a unique on-page text marker proving the page
// rendered wired to its endpoint.
const PAGES: Array<{ path: string; shot: string; marker: RegExp }> = [
  { path: "/caja", shot: "caja", marker: /cierre de arqueo/i },
  { path: "/settings/companies", shot: "empresas", marker: /empresas/i },
  { path: "/settings/hotel", shot: "hotel-settings", marker: /medios de pago/i },
  { path: "/reportes", shot: "reportes", marker: /reporte/i },
  { path: "/operacion/lista-espera", shot: "waitlist", marker: /espera/i },
  { path: "/operacion/lavanderia", shot: "lavanderia", marker: /lavander/i },
  { path: "/operacion/stock", shot: "stock", marker: /stock/i },
  { path: "/settings/api-keys", shot: "api-keys", marker: /API/i },
  { path: "/settings/permissions", shot: "permisos", marker: /permis/i },
  { path: "/settings/whatsapp", shot: "whatsapp", marker: /whatsapp/i },
  { path: "/habitaciones", shot: "rooms-bloqueos", marker: /habitaci/i },
  { path: "/reservas", shot: "reservas-asignacion", marker: /reserva/i },
  { path: "/huespedes", shot: "guests-tags", marker: /huesped/i }
];

async function login(page: Page) {
  await page.goto("/login");
  // Labels lack htmlFor association, so select inputs by type.
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  const onboardingResponse = page
    .waitForResponse((response) => response.url().includes("/api/onboarding/status"), { timeout: 15_000 })
    .catch(() => null);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
  await onboardingResponse;
  await page.waitForTimeout(250);
}

// B6.1: most of these routes now sit inside a collapsed sidebar <details>
// group -- open its <summary> first, closed content isn't clickable.
async function revealCollapsedNavLink(link: Locator) {
  const group = link.locator("xpath=ancestor::details[1]");
  if ((await group.count()) > 0 && !(await group.evaluate((el) => (el as HTMLDetailsElement).open))) {
    await group.locator("summary").first().click();
  }
}

async function clientNavigate(page: Page, path: string) {
  const link = page.locator(`aside nav a[href="${path}"]`);
  await revealCollapsedNavLink(link);
  await expect(link).toHaveCount(1);
  await expect(link).toBeVisible();
  await link.click();
  await expect(page).toHaveURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(600);
}

test.describe("V72 authenticated pages", () => {
  test.beforeAll(() => {
    mkdirSync("e2e/screenshots", { recursive: true });
  });

  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  for (const p of PAGES) {
    test(`renders authenticated page ${p.path}`, async ({ page }) => {
      await clientNavigate(page, p.path);
      await page.screenshot({ path: `e2e/screenshots/${p.shot}.png`, fullPage: true });
      // Authenticated shell present (not bounced to login).
      await expect(page.getByText(credentials.email).first()).toBeVisible();
      // We stayed on the requested route (session preserved).
      expect(page.url()).toContain(p.path);
      // The page content rendered (unique marker text somewhere on the page).
      await expect(page.getByText(p.marker).first()).toBeVisible();
    });
  }
});
