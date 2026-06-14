import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";

const credentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

// Each V72 page: client-side route (the app clears session on full reload, so we
// must NOT page.goto), a screenshot, and a unique on-page text marker proving the
// authenticated page rendered wired to its endpoint.
const PAGES: Array<{ path: string; shot: string; marker: RegExp }> = [
  { path: "/caja", shot: "caja", marker: /cierre de arqueo/i },
  { path: "/settings/companies", shot: "empresas", marker: /empresas/i },
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
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

async function clientNavigate(page: Page, path: string) {
  await page.evaluate((p) => {
    window.history.pushState({}, "", p);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, path);
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
