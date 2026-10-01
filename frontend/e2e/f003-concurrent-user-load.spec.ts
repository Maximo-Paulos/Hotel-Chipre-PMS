import { expect, test, type BrowserContext, type Page, type Request } from "@playwright/test";

import { navigateFromShell } from "./support/sidebar";

test.use({ screenshot: "off", video: "off", trace: "off", locale: "es-AR" });

type RouteScenario = { path: string; heading: RegExp };
type Persona = {
  name: string;
  email: string;
  password: string;
  roleLabel: string;
  landingPath: string;
  routes: RouteScenario[];
};
type ApiRequestMetric = {
  persona: string;
  method: string;
  path: string;
  at: number;
  action?: UiActionMetric;
};
type ApiResponseMetric = ApiRequestMetric & { status: number };
type UiActionMetric = {
  persona: string;
  path: string;
  startedAt: number;
  durationMs: number;
  apiRequests: string[];
};

const personas: Persona[] = [
  {
    name: "owner",
    email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
    password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!",
    roleLabel: "Dueño",
    landingPath: "/dashboard",
    routes: [
      { path: "/dashboard", heading: /^Visión general$/ },
      { path: "/reportes", heading: /^Reportes$/ }
    ]
  },
  {
    name: "manager",
    email: process.env.E2E_MANAGER_EMAIL || "manager@e2e.com",
    password: process.env.E2E_MANAGER_PASSWORD || "E2eManager1234!",
    roleLabel: "Gerencia",
    landingPath: "/dashboard",
    routes: [{ path: "/reservas", heading: /^Reservas$/ }]
  },
  {
    name: "receptionist",
    email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
    password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!",
    roleLabel: "Recepción",
    landingPath: "/dashboard",
    routes: [{ path: "/reservas", heading: /^Reservas$/ }]
  },
  {
    name: "housekeeping",
    email: process.env.E2E_HOUSEKEEPING_EMAIL || "housekeeping@e2e.com",
    password: process.env.E2E_HOUSEKEEPING_PASSWORD || "E2eHousekeeping1234!",
    roleLabel: "Limpieza",
    landingPath: "/habitaciones",
    routes: [
      { path: "/operacion/lavanderia", heading: /^Lavandería$/ },
      { path: "/habitaciones", heading: /^Habitaciones$/ }
    ]
  }
];

const durationSeconds = Number(process.env.E2E_F003_LOAD_DURATION_SECONDS || "1800");
const actionIntervalMs = 20_000;
const normalizePath = (pathname: string) => pathname.replace(/\/+$/, "") || "/";

async function login(page: Page, persona: Persona) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(persona.email);
  await page.locator('input[type="password"]').fill(persona.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL(`**${persona.landingPath}`, { timeout: 20_000 });
  await expect(page.getByTestId("session-email")).toHaveText(persona.email);
  await expect(page.getByTestId("session-role")).toHaveText(persona.roleLabel);
}

async function measureUiAction(
  page: Page,
  persona: Persona,
  path: string,
  actions: UiActionMetric[],
  operation: () => Promise<void>
) {
  const action: UiActionMetric = {
    persona: persona.name,
    path,
    startedAt: Date.now(),
    durationMs: 0,
    apiRequests: []
  };
  (page as Page & { __f003ActiveAction?: UiActionMetric }).__f003ActiveAction = action;
  const started = performance.now();
  try {
    await operation();
  } finally {
    action.durationMs = Math.round(performance.now() - started);
    actions.push(action);
    (page as Page & { __f003ActiveAction?: UiActionMetric }).__f003ActiveAction = undefined;
  }
}

async function navigate(page: Page, persona: Persona, route: RouteScenario, actions: UiActionMetric[]) {
  await measureUiAction(page, persona, route.path, actions, async () => {
    await navigateFromShell(page, route.path);
    await expect(page.locator("main").getByRole("heading", { name: route.heading }).first()).toBeVisible();
    await page.waitForTimeout(250);
  });
  return actions[actions.length - 1];
}

async function browseUntil(
  page: Page,
  persona: Persona,
  deadline: number,
  requests: ApiRequestMetric[],
  actions: UiActionMetric[]
) {
  let routeIndex = 0;
  while (Date.now() < deadline) {
    const started = Date.now();
    const route = persona.routes[routeIndex % persona.routes.length];
    routeIndex += 1;
    await navigate(page, persona, route, actions);
    const remaining = actionIntervalMs - (Date.now() - started);
    if (remaining > 0 && Date.now() + remaining < deadline) await page.waitForTimeout(remaining);
  }
}

async function reviewReservationQueueUntil(
  page: Page,
  persona: Persona,
  deadline: number,
  actions: UiActionMetric[]
) {
  const statusFilter = page
    .getByRole("heading", { name: "Fecha, estado y empresa" })
    .locator("xpath=../..")
    .locator("label")
    .filter({ hasText: "Estado" })
    .locator("select");
  let showPending = true;
  while (Date.now() < deadline) {
    const started = Date.now();
    const nextStatus = showPending ? "pending" : "";
    showPending = !showPending;
    await measureUiAction(page, persona, "/reservas:status-filter", actions, async () => {
      await statusFilter.selectOption(nextStatus);
      await expect(statusFilter).toHaveValue(nextStatus);
      await page.waitForTimeout(250);
    });
    const remaining = actionIntervalMs - (Date.now() - started);
    if (remaining > 0 && Date.now() + remaining < deadline) await page.waitForTimeout(remaining);
  }
}

function addApiMonitoring(page: Page, persona: Persona, requests: ApiRequestMetric[], responses: ApiResponseMetric[], sessionRedirects: number[]) {
  let authenticated = false;
  const actionByRequest = new WeakMap<Request, UiActionMetric>();
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/")) return;
    const activeAction = (page as Page & { __f003ActiveAction?: UiActionMetric }).__f003ActiveAction;
    const metric: ApiRequestMetric = {
      persona: persona.name,
      method: request.method(),
      path: normalizePath(url.pathname),
      at: Date.now(),
      ...(activeAction ? { action: activeAction } : {})
    };
    requests.push(metric);
    if (activeAction) {
      actionByRequest.set(request, activeAction);
      activeAction.apiRequests.push(`${metric.method} ${metric.path}`);
    }
  });
  page.on("response", (response) => {
    const url = new URL(response.url());
    if (!url.pathname.startsWith("/api/")) return;
    const requestAction = actionByRequest.get(response.request());
    responses.push({
      persona: persona.name,
      method: response.request().method(),
      path: normalizePath(url.pathname),
      status: response.status(),
      at: Date.now(),
      ...(requestAction ? { action: requestAction } : {})
    });
  });
  page.on("framenavigated", (frame) => {
    if (!authenticated || frame !== page.mainFrame()) return;
    if (new URL(frame.url()).pathname === "/login") sessionRedirects.push(Date.now());
  });
  return () => { authenticated = true; };
}

function localIsoDate(offsetDays: number) {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

async function createOneReservation(
  page: Page,
  persona: Persona,
  actions: UiActionMetric[],
  bookingOrdinal: number
): Promise<number> {
  const started = performance.now();
  if (normalizePath(new URL(page.url()).pathname) !== "/reservas") {
    await navigate(page, persona, { path: "/reservas", heading: /^Reservas$/ }, actions);
  } else {
    await expect(page.locator("main").getByRole("heading", { name: /^Reservas$/ }).first()).toBeVisible();
  }
  const form = page.locator("form").filter({ hasText: "Datos de la reserva" });
  const guestName = `Pasajero F003 ${String(bookingOrdinal).padStart(3, "0")}`;
  const checkInOffsetDays = 100 + bookingOrdinal * 3;
  await measureUiAction(page, persona, "/reservas:create-form", actions, async () => {
    await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
    await expect(form).toBeVisible();
  });
  await measureUiAction(page, persona, "/reservas:guest-search", actions, async () => {
    await form.getByTestId("guest-search-input").fill(guestName);
    await expect(
      form.getByTestId("guest-search-results").getByRole("button").filter({ hasText: guestName })
    ).toBeVisible();
  });
  const guest = form.getByTestId("guest-search-results").getByRole("button").filter({ hasText: guestName });
  await measureUiAction(page, persona, "/reservas:guest-select", actions, async () => {
    await guest.click();
  });
  const categorySelect = form.locator("label").filter({ hasText: "Categoría" }).locator("select");
  await measureUiAction(page, persona, "/reservas:category-select", actions, async () => {
    await categorySelect.selectOption({ label: "Doble Estándar" });
  });
  await measureUiAction(page, persona, "/reservas:checkin-date", actions, async () => {
    await form.getByLabel("Check-in", { exact: true }).fill(localIsoDate(checkInOffsetDays));
  });
  await measureUiAction(page, persona, "/reservas:checkout-date", actions, async () => {
    await form.getByLabel("Check-out", { exact: true }).fill(localIsoDate(checkInOffsetDays + 2));
  });
  await measureUiAction(page, persona, "/reservas:notes", actions, async () => {
    await form.getByLabel("Notas").fill("Reserva de prueba F-003; seña acordada de $51.000.");
  });
  await measureUiAction(page, persona, "/reservas:deposit", actions, async () => {
    await form.getByLabel("Seña manual").fill("51000");
  });
  const created = page.waitForResponse((response) =>
    normalizePath(new URL(response.url()).pathname) === "/api/reservations" && response.request().method() === "POST"
  );
  await measureUiAction(page, persona, "/reservas:create-submit", actions, async () => {
    await form.getByRole("button", { name: "Crear", exact: true }).click();
    expect((await created).status()).toBe(201);
    await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();
  });
  return Math.round(performance.now() - started);
}

async function createReservationBatch(
  page: Page,
  persona: Persona,
  actions: UiActionMetric[],
  firstBookingOrdinal: number,
  bookingCount: number
): Promise<number[]> {
  const latencies: number[] = [];
  for (let index = 0; index < bookingCount; index += 1) {
    latencies.push(await createOneReservation(page, persona, actions, firstBookingOrdinal + index));
  }
  return latencies;
}

test("F-003: four hotel roles keep daily UI journeys healthy under 30-minute concurrency", async ({ browser }, testInfo) => {
  test.skip(process.env.E2E_F003_LOAD !== "true", "Run only against a fresh isolated PostgreSQL 16 E2E database with E2E_F003_LOAD=true.");
  test.skip(!Number.isFinite(durationSeconds) || durationSeconds <= 0, "E2E_F003_LOAD_DURATION_SECONDS must be positive.");
  test.setTimeout(durationSeconds * 1000 + 300_000);

  const contexts: BrowserContext[] = [];
  const pages: Page[] = [];
  const requests: ApiRequestMetric[] = [];
  const responses: ApiResponseMetric[] = [];
  const sessionRedirects: number[] = [];
  const actions: UiActionMetric[] = [];

  try {
    const personaPages = await Promise.all(personas.map(async (persona) => {
      const context = await browser.newContext({ locale: "es-AR", viewport: { width: 1365, height: 900 } });
      contexts.push(context);
      const page = await context.newPage();
      pages.push(page);
      const markAuthenticated = addApiMonitoring(page, persona, requests, responses, sessionRedirects);
      const permissionResponsePromise = page.waitForResponse((response) =>
        normalizePath(new URL(response.url()).pathname) === "/api/permissions/effective"
        && response.request().method() === "GET"
      );
      await login(page, persona);
      const permissionResponse = await permissionResponsePromise;
      expect(permissionResponse.status()).toBe(200);
      const permissionPayload = await permissionResponse.json() as { role: string; permissions: string[] };
      const permissionSnapshot = {
        role: permissionPayload.role,
        hotelSettingsRead: permissionPayload.permissions.includes("hotel_settings:read")
      };
      expect(permissionSnapshot.role).toBe(persona.name === "owner" ? "owner" : persona.name);
      expect(permissionSnapshot.hotelSettingsRead).toBe(persona.name === "owner");
      markAuthenticated();
      return { persona, page, permissionSnapshot };
    }));

    const receptionist = personaPages.find(({ persona }) => persona.name === "receptionist")!;
    const manager = personaPages.find(({ persona }) => persona.name === "manager")!;
    const owner = personaPages.find(({ persona }) => persona.name === "owner")!;
    const housekeeping = personaPages.find(({ persona }) => persona.name === "housekeeping")!;
    const deadline = Date.now() + durationSeconds * 1000;
    const reservationLatencies: number[] = [];
    const loadStartedAt = Date.now();
    const bookingAndBrowse = async (
      personaPage: typeof manager,
      firstBookingOrdinal: number,
      bookingCount: number
    ) => {
      const latencies = await createReservationBatch(
        personaPage.page,
        personaPage.persona,
        actions,
        firstBookingOrdinal,
        bookingCount
      );
      reservationLatencies.push(...latencies);
      if (Date.now() < deadline) {
        await reviewReservationQueueUntil(personaPage.page, personaPage.persona, deadline, actions);
      }
    };
    await Promise.all([
      browseUntil(owner.page, owner.persona, deadline, requests, actions),
      browseUntil(housekeeping.page, housekeeping.persona, deadline, requests, actions),
      bookingAndBrowse(receptionist, 1, 13),
      bookingAndBrowse(manager, 14, 18)
    ]);

    const loadRequests = requests.filter((request) => request.at >= loadStartedAt);
    const loadResponses = responses.filter((response) => response.at >= loadStartedAt);
    const loadActions = actions.filter((action) => action.startedAt >= loadStartedAt);
    const fiveXx = loadResponses.filter((response) => response.status >= 500);
    const forbiddenSettingsReads = responses.filter((response) =>
      response.status === 403
      && response.method === "GET"
      && ["/api/config", "/api/subscription/status"].includes(response.path)
    );
    const navigationActions = loadActions.filter((action) => !action.path.includes(":"));
    const categoryReadsPerScreen = navigationActions.map((action) =>
      action.apiRequests.filter((request) => request === "GET /api/rooms/categories").length
    );
    const sortedLatencies = loadActions.map((action) => action.durationMs).sort((left, right) => left - right);
    const p95ActionMs = sortedLatencies.length
      ? sortedLatencies[Math.min(sortedLatencies.length - 1, Math.ceil(sortedLatencies.length * 0.95) - 1)]
      : 0;
    const actionRequestCounts = loadActions.map((action) => action.apiRequests.length);
    const attributedApiRequestCount = actionRequestCounts.reduce((total, count) => total + count, 0);
    const apiRequestsPerAction = loadActions.length
      ? loadRequests.length / loadActions.length
      : 0;
    const attributedApiRequestsPerAction = loadActions.length
      ? attributedApiRequestCount / loadActions.length
      : 0;
    const navigationApiRequestCount = navigationActions.reduce((total, action) => total + action.apiRequests.length, 0);
    const maxRequestAction = loadActions.reduce<UiActionMetric | null>(
      (maximum, action) => !maximum || action.apiRequests.length > maximum.apiRequests.length ? action : maximum,
      null
    );
    const requestBudgetByAction = Object.fromEntries(
      [...new Set(loadActions.map((action) => action.path))].map((path) => {
        const counts = loadActions.filter((action) => action.path === path).map((action) => action.apiRequests.length);
        const pathActions = loadActions.filter((action) => action.path === path);
        const requestCount = pathActions.reduce((total, action) => total + action.apiRequests.length, 0);
        const endpointCounts = Object.fromEntries(
          pathActions.flatMap((action) => action.apiRequests).reduce<Map<string, number>>((totals, endpoint) => {
            totals.set(endpoint, (totals.get(endpoint) ?? 0) + 1);
            return totals;
          }, new Map())
        );
        return [path, {
          max: Math.max(0, ...counts),
          count: counts.length,
          requests: requestCount,
          average_requests: Number((requestCount / Math.max(1, counts.length)).toFixed(2)),
          endpoints: endpointCounts
        }];
      })
    );
    const maxRequestEndpointCounts = Object.fromEntries(
      (maxRequestAction?.apiRequests ?? []).reduce<Map<string, number>>((counts, endpoint) => {
        counts.set(endpoint, (counts.get(endpoint) ?? 0) + 1);
        return counts;
      }, new Map())
    );
    const forbiddenSettingsReadDetails = forbiddenSettingsReads.map((response) => ({
      persona: response.persona,
      method: response.method,
      path: response.path,
      action: response.action?.path ?? null
    }));
    const guestSelectionActions = loadActions.filter((action) =>
      action.path === "/reservas:guest-search" || action.path === "/reservas:guest-select"
    );
    const unassociatedEndpointCounts = Object.fromEntries(
      loadRequests.filter((request) => !request.action).reduce<Map<string, number>>((counts, request) => {
        const endpoint = `${request.method} ${request.path}`;
        counts.set(endpoint, (counts.get(endpoint) ?? 0) + 1);
        return counts;
      }, new Map())
    );
    const individualGuestRestrictionReads = guestSelectionActions.map((action) =>
      action.apiRequests.filter((request) => /^GET \/api\/guests\/\d+\/restrictions$/.test(request)).length
    );
    const guestRestrictionSummaryReads = guestSelectionActions.map((action) =>
      action.apiRequests.filter((request) => request === "GET /api/guests/active-restrictions/summary").length
    );
    const payload = {
      roles: personas.length,
      effective_settings_read_permissions: Object.fromEntries(
        personaPages.map(({ persona, permissionSnapshot }) => [persona.name, permissionSnapshot.hotelSettingsRead])
      ),
      duration_seconds: Math.round((Date.now() - loadStartedAt) / 1000),
      ui_actions: loadActions.length,
      api_requests: loadRequests.length,
      api_requests_per_action: Number(apiRequestsPerAction.toFixed(2)),
      api_requests_per_measured_action: Number(attributedApiRequestsPerAction.toFixed(2)),
      api_requests_per_navigation_action: Number((navigationApiRequestCount / Math.max(1, navigationActions.length)).toFixed(2)),
      api_requests_without_ui_action: loadRequests.length - attributedApiRequestCount,
      api_requests_without_ui_action_by_endpoint: unassociatedEndpointCounts,
      max_api_requests_per_action: Math.max(0, ...actionRequestCounts),
      max_request_action: maxRequestAction ? { persona: maxRequestAction.persona, path: maxRequestAction.path } : null,
      max_request_endpoint_counts: maxRequestEndpointCounts,
      api_requests_by_ui_action: requestBudgetByAction,
      page_action_latency_ms: {
        p95: p95ActionMs,
        max: Math.max(0, ...sortedLatencies)
      },
      reservation_create_latency_ms: Math.max(0, ...reservationLatencies),
      reservation_creates: reservationLatencies.length,
      categories_gets_per_screen_load: {
        max: Math.max(0, ...categoryReadsPerScreen),
        screens_checked: categoryReadsPerScreen.length
      },
      guest_restriction_reads_per_guest_search_or_selection: {
        individual_max: Math.max(0, ...individualGuestRestrictionReads),
        summary_max: Math.max(0, ...guestRestrictionSummaryReads),
        actions_checked: guestSelectionActions.length
      },
      status_counts: loadResponses.reduce<Record<string, number>>((counts, response) => {
        counts[String(response.status)] = (counts[String(response.status)] ?? 0) + 1;
        return counts;
      }, {}),
      five_xx: fiveXx.length,
      forbidden_settings_reads: forbiddenSettingsReads.length,
      forbidden_settings_reads_before_load: forbiddenSettingsReads.filter((response) => response.at < loadStartedAt).length,
      forbidden_settings_read_details: forbiddenSettingsReadDetails,
      session_redirects: sessionRedirects.filter((at) => at >= loadStartedAt).length
    };
    console.log(`F003_LOAD_RESULT ${JSON.stringify(payload)}`);

    expect(payload.duration_seconds).toBeGreaterThanOrEqual(durationSeconds - 5);
    expect(payload.ui_actions).toBeGreaterThan(0);
    expect(payload.five_xx).toBe(0);
    expect(payload.forbidden_settings_reads).toBe(0);
    expect(payload.session_redirects).toBe(0);
    expect(payload.categories_gets_per_screen_load.max).toBeLessThanOrEqual(1);
    expect(payload.api_requests_per_action).toBeLessThanOrEqual(2);
    expect(payload.guest_restriction_reads_per_guest_search_or_selection.individual_max).toBeLessThanOrEqual(1);
    expect(payload.guest_restriction_reads_per_guest_search_or_selection.summary_max).toBeLessThanOrEqual(1);
    expect(payload.reservation_creates).toBe(31);
    expect(payload.reservation_create_latency_ms).toBeLessThanOrEqual(40_000);
  } finally {
    await Promise.all(contexts.map((context) => context.close().catch(() => undefined)));
  }
});
