import { expect, test, type Page, type Route } from "@playwright/test";

const apiBase = "http://127.0.0.1:8040/api";
const apiPath = "/api";
const allowedPermissions = [
  "dashboard:view",
  "reservation:create",
  "reservation:read",
  "occupancy:view",
  "room:read",
  "reservation:move",
  "guest:read",
  "cash:view",
  "settings:notifications:view",
  "reports:operational:view"
];

function apiMock(permissions: string[], blockedWrites: string[]) {
  return async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const cors = {
      "access-control-allow-origin": "http://127.0.0.1:5181",
      "access-control-allow-credentials": "true",
      "access-control-allow-methods": "GET,POST,PATCH,PUT,DELETE,OPTIONS",
      "access-control-allow-headers": request.headers()["access-control-request-headers"]
        || "authorization,content-type,x-hotel-id,x-user-id,x-csrf-token"
    };

    if (request.method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: cors });
      return;
    }

    if (path === `${apiPath}/auth/login` && request.method() === "POST") {
      await route.fulfill({
        status: 200,
        headers: cors,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: "synthetic-actions-only-token",
          token_type: "bearer",
          hotel_id: 1,
          hotel_ids: [1],
          user: {
            id: 8,
            email: "qa.manager@example.test",
            role: "manager",
            is_verified: true,
            is_active: true,
            permissions
          },
          permissions
        })
      });
      return;
    }

    if (request.method() !== "GET") {
      blockedWrites.push(`${request.method()} ${path}`);
      await route.fulfill({
        status: 403,
        headers: cors,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Synthetic visual QA blocks writes" })
      });
      return;
    }

    let payload: unknown = [];
    if (path === `${apiPath}/auth/providers`) {
      payload = { google: { enabled: false, client_id: null, self_signup_enabled: false, allowed_domains: [] } };
    } else if (path === `${apiPath}/permissions/effective`) {
      payload = { hotel_id: 1, role: "manager", permissions };
    } else if (path === `${apiPath}/config/`) {
      payload = {
        id: 1,
        hotel_name: "Hotel Chipre QA",
        hotel_timezone: "America/Argentina/Buenos_Aires",
        check_in_time: "14:00",
        check_out_time: "10:00",
        default_currency: "ARS",
        languages: ["es"],
        interface_language: "es",
        jurisdiction_code: "AR",
        require_terms_acceptance: true,
        require_document_for_checkin: true,
        allow_cancellation_after_checkin: false,
        updated_at: "2026-11-09T12:00:00Z"
      };
    } else if (path === `${apiPath}/config/interface-language`) {
      payload = { interface_language: "es" };
    } else if (path === `${apiPath}/config/business-clock`) {
      payload = {
        hotel_id: 1,
        business_date: "2026-11-09",
        hotel_timezone: "America/Argentina/Buenos_Aires",
        simulation_enabled: false
      };
    } else if (path === `${apiPath}/subscription/status` || path === `${apiPath}/subscription`) {
      payload = { status: "active", can_write: true, plan: "ultra", plan_code: "ultra" };
    } else if (path === `${apiPath}/reports/operational/arrivals/count`) {
      payload = { count: 0, report_date: "2026-11-09" };
    } else if (path === `${apiPath}/reports/occupancy`) {
      payload = { total_rooms: 16, daily: [{ date: "2026-11-09", rate: 50 }] };
    } else if (path === `${apiPath}/reservations/` || path === `${apiPath}/reservations`) {
      payload = [];
    } else if (path === `${apiPath}/reservations/actions/pending` || path === `${apiPath}/reservations/cancellation-reviews/pending`) {
      payload = [];
    } else if (path.startsWith(`${apiPath}/events/`)) {
      payload = [];
    }

    await route.fulfill({
      status: 200,
      headers: cors,
      contentType: "application/json",
      body: JSON.stringify(payload)
    });
  };
}

async function login(page: Page, permissions: string[], blockedWrites: string[]) {
  await page.route("https://**/*", (route) => route.abort());
  await page.route(`${apiBase}/**`, apiMock(permissions, blockedWrites));
  await page.goto("/login");
  await page.locator('input[type="email"]').fill("qa.manager@example.test");
  await page.locator('input[type="password"]').fill("synthetic-visual-only-password");
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
  await page.addStyleTag({ content: '[data-testid="realtime-status"], .tsqd-parent-container { display: none !important; }' });
  await expect(page.getByTestId("dashboard-primary-actions")).toBeAttached();
}

const actionDialog = (page: Page) => page.getByRole("dialog", { name: "Acciones y más" });

test("mobile quick actions fit and only navigate to existing flows", async ({ page }, testInfo) => {
  const blockedWrites: string[] = [];
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await login(page, allowedPermissions, blockedWrites);

  for (const viewport of [{ width: 320, height: 568 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await expect(page.getByTestId("dashboard-primary-actions")).toBeHidden();
    const actionButton = page.getByTestId("bottom-nav-actions-button");
    await expect(actionButton).toBeVisible();
    const nav = page.getByRole("navigation", { name: "Navegación principal móvil" });
    await expect(nav.locator("a,button")).toHaveCount(5);
    await expect(nav.getByText("Habitación", { exact: true })).toBeVisible();
    await expect(nav.locator('a[href="/caja"]')).toBeVisible();
    const [navBox, actionBox] = await Promise.all([nav.boundingBox(), actionButton.boundingBox()]);
    expect(navBox && actionBox).toBeTruthy();
    expect(actionBox!.height).toBeGreaterThanOrEqual(64);
    expect(actionBox!.width).toBeGreaterThanOrEqual(48);
    expect(Math.abs((actionBox!.x + actionBox!.width / 2) - (navBox!.x + navBox!.width / 2))).toBeLessThanOrEqual(8);
    const navSafeArea = await nav.evaluate((element) => ({
      bottom: getComputedStyle(element).bottom,
      paddingBottom: Number.parseFloat(getComputedStyle(element).paddingBottom)
    }));
    expect(navSafeArea.bottom).toBe("0px");
    expect(navSafeArea.paddingBottom).toBeGreaterThanOrEqual(8);

    const suffix = `${viewport.width}x${viewport.height}`;
    await page.screenshot({ path: testInfo.outputPath(`dashboard-${suffix}.png`) });
    await actionButton.click();
    await expect(actionDialog(page)).toBeVisible();
    await expect(page.getByTestId("quick-action-new-reservation")).toBeVisible();
    await expect(page.getByTestId("quick-action-assign-room")).toBeVisible();
    for (const locator of [page.getByTestId("quick-action-new-reservation"), page.getByTestId("quick-action-assign-room")]) {
      const box = await locator.boundingBox();
      expect(box?.height).toBeGreaterThanOrEqual(52);
    }
    await expect(page.getByRole("navigation", { name: "Navegación móvil" }).locator('a[href="/reservas"]')).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Navegación móvil" }).locator('a[href="/operacion/asignacion"]')).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Navegación móvil" }).locator('a[href="/caja"]')).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`actions-${suffix}.png`) });
    if (viewport.width === 390) {
      const scrollRegion = page.getByTestId("mobile-menu-scroll-region");
      await scrollRegion.evaluate((element) => element.scrollTo({ top: element.scrollHeight, behavior: "instant" }));
      await expect.poll(() => scrollRegion.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
      await expect(page.getByRole("navigation", { name: "Configuración" }).locator('a[href="/settings/notifications"]'))
        .toBeInViewport({ ratio: 1 });
      await expect(page.getByRole("navigation", { name: "Navegación móvil" }).locator('a[href="/caja"]'))
        .toBeAttached();
    }
    await page.keyboard.press("Escape");
    await expect(actionDialog(page)).toBeHidden();
    await expect(actionButton).toBeFocused();
    if (viewport.width === 320) {
      await actionButton.click();
      await expect(actionDialog(page)).toBeVisible();
      await page.getByTestId("mobile-menu-backdrop").click({ position: { x: 10, y: 10 } });
      await expect(actionDialog(page)).toBeHidden();
      await expect(actionButton).toBeFocused();
    }
  }

  await page.getByTestId("bottom-nav-actions-button").click();
  await expect(actionDialog(page)).toBeVisible();
  await page.getByTestId("quick-action-new-reservation").click();
  await expect(page).toHaveURL(/\/reservas\?crear=1$/);
  await expect(actionDialog(page)).toBeHidden();

  await page.evaluate(() => {
    window.history.pushState({}, "", "/dashboard");
    window.dispatchEvent(new PopStateEvent("popstate", { state: {} }));
  });
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.getByTestId("bottom-nav-actions-button").click();
  await page.getByTestId("quick-action-assign-room").click();
  await expect(page).toHaveURL(/\/operacion\/planilla$/);
  expect(blockedWrites).toEqual([]);
  expect(pageErrors).toEqual([]);

  await page.evaluate(() => {
    window.history.pushState({}, "", "/dashboard");
    window.dispatchEvent(new PopStateEvent("popstate", { state: {} }));
  });
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.setViewportSize({ width: 1280, height: 800 });
  await expect(page.getByTestId("bottom-nav-actions-button")).toBeHidden();
  await expect(page.getByTestId("dashboard-primary-actions")).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("dashboard-1280x800.png") });
});

test("quick actions stay hidden until their permissions are effective", async ({ page }) => {
  const blockedWrites: string[] = [];
  await login(page, ["dashboard:view", "reservation:read"], blockedWrites);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByTestId("bottom-nav-actions-button").click();
  await expect(actionDialog(page)).toBeVisible();
  await expect(page.getByTestId("mobile-quick-actions")).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "Navegación móvil" }).locator('a[href="/reservas"]')).toBeVisible();
  await page.keyboard.press("Escape");
  expect(blockedWrites).toEqual([]);
});
