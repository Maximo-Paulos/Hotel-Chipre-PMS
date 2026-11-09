import { expect, test, type Page, type Route } from "@playwright/test";

const apiBase = "http://127.0.0.1:8040/api";
const apiPath = "/api";
const permissions = [
  "dashboard:view",
  "guest:read",
  "reservation:read",
  "reservation:create",
  "occupancy:view",
  "room:read",
  "reports:operational:view",
  "reports:financial:view",
  "reservation:move",
  "reservation:move_category"
];

const category = {
  id: 11,
  name: "Doble clásica",
  code: "DBL",
  base_price_per_night: 95_000,
  current_rate: 105_000,
  max_occupancy: 2
};

const rooms = Array.from({ length: 16 }, (_, index) => ({
  id: 101 + index,
  room_number: String(101 + index),
  floor: Math.floor(index / 8) + 1,
  category_id: category.id,
  status: index === 0 ? "occupied" : "available",
  housekeeping_status: "clean",
  is_active: true,
  allocation_priority_channel_groups: [],
  allocation_priority_company_ids: [],
  category
}));

const reservation = {
  id: 701,
  version: 1,
  guest_id: 1,
  guest: { id: 1, first_name: "Elena", last_name: "Díaz" },
  room_id: rooms[0].id,
  room_number: rooms[0].room_number,
  category_id: category.id,
  category_name: category.name,
  confirmation_code: "RES-QA101",
  check_in_date: "2026-11-09",
  check_out_date: "2026-11-13",
  total_amount: 420_000,
  amount_paid: 105_000,
  deposit_amount: 105_000,
  balance_due: 315_000,
  status: "deposit_paid",
  source: "direct",
  num_adults: 2,
  num_children: 0,
  currency_code: "ARS"
};

const occupancy = {
  rooms: rooms.map((room) => ({
    id: room.id,
    room_number: room.room_number,
    floor: room.floor,
    category_id: room.category_id,
    category_name: category.name,
    status: room.status
  })),
  reservations: [reservation],
  unassigned: [],
  blocks: []
};

async function mockApi(route: Route) {
  const request = route.request();
  const url = new URL(request.url());
  const path = url.pathname;
  const cors = {
    "access-control-allow-origin": "http://127.0.0.1:5177",
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
        access_token: "synthetic-visual-only-token",
        token_type: "bearer",
        hotel_id: 1,
        hotel_ids: [1],
        user: {
          id: 7,
          email: "qa.owner@example.test",
          role: "owner",
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
  } else if (path === `${apiPath}/onboarding/status`) {
    payload = { hotel_id: 1, completed: true, steps: {}, missing_steps: [], counts: {} };
  } else if (path === `${apiPath}/permissions/effective`) {
    payload = { hotel_id: 1, role: "owner", permissions };
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
  } else if (path === `${apiPath}/rooms/`) {
    payload = rooms;
  } else if (path === `${apiPath}/rooms/categories` || path === `${apiPath}/categories/`) {
    payload = [category];
  } else if (path === `${apiPath}/reservations/occupancy-grid`) {
    payload = occupancy;
  } else if (path === `${apiPath}/reservations/` || path === `${apiPath}/reservations`) {
    payload = [reservation];
  } else if (path === `${apiPath}/reservations/actions/pending` || path === `${apiPath}/reservations/cancellation-reviews/pending`) {
    payload = [];
  } else if (path === `${apiPath}/reports/occupancy`) {
    payload = { total_rooms: rooms.length, daily: [] };
  } else if (path === `${apiPath}/reports/operational/arrivals/count`) {
    payload = { count: 1, report_date: "2026-11-09" };
  } else if (path === `${apiPath}/subscription/status` || path === `${apiPath}/subscription`) {
    payload = { status: "active", can_write: true, plan_code: "qa" };
  } else if (path.startsWith(`${apiPath}/events/`)) {
    payload = [];
  }

  await route.fulfill({
    status: 200,
    headers: cors,
    contentType: "application/json",
    body: JSON.stringify(payload)
  });
}

async function loginAndOpenPlanilla(page: Page) {
  await page.route("https://**/*", (route) => route.abort());
  await page.route(`${apiBase}/**`, mockApi);
  await page.goto("/login");
  await page.locator('input[type="email"]').fill("qa.owner@example.test");
  await page.locator('input[type="password"]').fill("synthetic-visual-only-password");
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
  await page.addStyleTag({ content: '[data-testid="realtime-status"]{display:none!important}' });
  await page.evaluate(() => {
    window.history.pushState({}, "", "/operacion/planilla");
    window.dispatchEvent(new PopStateEvent("popstate", { state: {} }));
  });
  await expect(page.getByTestId("occupancy-grid")).toBeVisible();
}

test("occupancy grid stays below the mobile app header while the page scrolls", async ({ page }, testInfo) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await loginAndOpenPlanilla(page);

  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await page.evaluate(() => window.scrollTo(0, 0));
    await expect(page.getByTestId("mobile-screen-title")).toHaveText("Planilla");
    await page.screenshot({ path: testInfo.outputPath(`planilla-${width}-top.png`) });

    await page.evaluate(() => window.scrollTo(0, 520));
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(520);
    await page.screenshot({ path: testInfo.outputPath(`planilla-${width}-scroll.png`) });

    const overlapProbe = await page.evaluate(() => {
      const title = document.querySelector<HTMLElement>('[data-testid="mobile-screen-title"]');
      const appHeader = title?.closest("header");
      const grid = document.querySelector<HTMLElement>('[data-testid="occupancy-grid"]');
      if (!title || !appHeader || !grid) return null;
      const rect = title.getBoundingClientRect();
      const target = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
      const firstRoomHeader = grid.querySelector<HTMLElement>("thead th");
      return {
        titleText: title.textContent?.trim(),
        titleTop: rect.top,
        targetTestId: target?.getAttribute("data-testid"),
        targetText: target?.textContent?.trim(),
        targetIsTitle: target === title || Boolean(target?.closest('[data-testid="mobile-screen-title"]')),
        targetIsInAppHeader: Boolean(target && appHeader.contains(target)),
        headerTop: appHeader.getBoundingClientRect().top,
        headerZIndex: getComputedStyle(appHeader).zIndex,
        firstRoomHeaderZIndex: firstRoomHeader ? getComputedStyle(firstRoomHeader).zIndex : null,
        windowScrollY: window.scrollY,
        gridScrollTop: grid.scrollTop,
        gridClientWidth: grid.clientWidth,
        gridScrollWidth: grid.scrollWidth
      };
    });

    expect(overlapProbe).not.toBeNull();
    expect(overlapProbe?.windowScrollY).toBe(520);
    expect(overlapProbe?.gridScrollTop).toBe(0);
    expect(overlapProbe?.headerTop).toBe(0);
    expect(overlapProbe?.targetIsInAppHeader).toBe(true);
    expect(overlapProbe?.targetIsTitle).toBe(true);
    expect(overlapProbe?.gridScrollWidth).toBeGreaterThan(overlapProbe?.gridClientWidth ?? 0);

    const horizontalScroll = await page.getByTestId("occupancy-grid").evaluate((element) => {
      const grid = element as HTMLElement;
      grid.scrollLeft = 120;
      const firstHeader = grid.querySelector<HTMLElement>("thead th");
      return {
        scrollLeft: grid.scrollLeft,
        gridLeft: grid.getBoundingClientRect().left,
        firstHeaderLeft: firstHeader?.getBoundingClientRect().left ?? Number.NaN
      };
    });
    expect(horizontalScroll.scrollLeft).toBeGreaterThan(0);
    expect(Math.abs(horizontalScroll.firstHeaderLeft - horizontalScroll.gridLeft)).toBeLessThanOrEqual(1);
    await page.getByTestId("occupancy-grid").evaluate((element) => { (element as HTMLElement).scrollLeft = 0; });
  }

  expect(pageErrors).toEqual([]);
});
