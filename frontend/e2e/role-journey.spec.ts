import { expect, test, type Locator, type Page } from "@playwright/test";

const backendURL = (process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040").replace(/\/$/, "");

type Persona = {
  label: string;
  email: string;
  password: string;
  landingPath: string;
  allowedPath: string;
  allowedHeading: RegExp;
  forbiddenNavPaths: string[];
};

const personas: Persona[] = [
  {
    label: "manager",
    email: process.env.E2E_MANAGER_EMAIL || "manager@e2e.com",
    password: process.env.E2E_MANAGER_PASSWORD || "E2eManager1234!",
    landingPath: "/dashboard",
    allowedPath: "/reportes",
    allowedHeading: /^Reportes$/,
    forbiddenNavPaths: ["/settings/hotel", "/settings/users"]
  },
  {
    label: "receptionist",
    email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
    password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!",
    landingPath: "/dashboard",
    allowedPath: "/caja",
    allowedHeading: /^Caja$/,
    forbiddenNavPaths: ["/reportes", "/settings/hotel", "/operacion/stock"]
  },
  {
    label: "housekeeping",
    email: process.env.E2E_HOUSEKEEPING_EMAIL || "housekeeping@e2e.com",
    password: process.env.E2E_HOUSEKEEPING_PASSWORD || "E2eHousekeeping1234!",
    landingPath: "/habitaciones",
    allowedPath: "/operacion/lavanderia",
    allowedHeading: /^Lavanderia$/,
    forbiddenNavPaths: ["/caja", "/reportes", "/operacion/stock", "/settings/hotel"]
  }
];

async function login(page: Page, persona: Persona) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(persona.email);
  await page.locator('input[type="password"]').fill(persona.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL(`**${persona.landingPath}`, { timeout: 20_000 });
  await expect(page.getByText(`Usuario ${persona.email}`)).toBeVisible();
  const roleLabel: Record<string, string> = {
    owner: "Dueño",
    manager: "Manager",
    receptionist: "Recepción",
    housekeeping: "Housekeeping"
  };
  await expect(page.getByTestId("session-role")).toHaveText(roleLabel[persona.label]);
}

type ApiSession = {
  hotelId: number;
  userId: string;
  accessToken: string;
  csrfToken?: string;
};

async function readApiSession(page: Page, credentials: { email: string; password: string }): Promise<ApiSession> {
  // Use a fresh API login only for owner-authorized setup/cleanup. The browser
  // session remains the user journey under test, and no secrets are logged.
  const response = await page.request.post(`${backendURL}/api/auth/login`, { data: credentials });
  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as {
    hotel_id: number;
    user: { email: string };
    access_token: string;
    csrf_token?: string;
  };
  return {
    hotelId: payload.hotel_id,
    userId: payload.user.email,
    accessToken: payload.access_token,
    csrfToken: payload.csrf_token
  };
}

async function operationalNavigation(page: Page): Promise<Locator> {
  const asideNav = page.locator("aside nav");
  if (await asideNav.isVisible().catch(() => false)) {
    return asideNav;
  }

  // B7: on mobile the whole nav lives inside a slide-over panel opened via
  // the hamburger button -- open it before returning its nav locator.
  const menuButton = page.getByTestId("mobile-menu-button");
  if (await menuButton.isVisible().catch(() => false)) {
    await menuButton.click();
  }
  return page.locator('nav[aria-label="Navegación móvil"]');
}

for (const persona of personas) {
  test(`${persona.label} sees only its operational surface`, async ({ page }) => {
    await login(page, persona);
    const navigation = await operationalNavigation(page);

    for (const path of persona.forbiddenNavPaths) {
      await expect(navigation.locator(`a[href="${path}"]`)).toHaveCount(0);
    }

    const allowedLink = navigation.locator(`a[href="${persona.allowedPath}"]`);
    // B6.1: routes outside the daily nav row sit inside a collapsed sidebar
    // <details> group -- open its <summary> first.
    const allowedGroup = allowedLink.locator("xpath=ancestor::details[1]");
    if ((await allowedGroup.count()) > 0 && !(await allowedGroup.evaluate((el) => (el as HTMLDetailsElement).open))) {
      await allowedGroup.locator("summary").first().click();
    }
    await expect(allowedLink).toBeVisible();
    await allowedLink.click();
    await expect(page).toHaveURL(new RegExp(`${persona.allowedPath.replaceAll("/", "\\/")}$`));
    await expect(page.getByRole("heading", { name: persona.allowedHeading })).toBeVisible();
  });
}

// State transitions and room blocks are independent capabilities: manager can
// change every state and manage blocks; reception can create blocks but cannot
// change state; housekeeping can only alternate Libre/Limpieza.
for (const persona of personas) {
  test(`${persona.label} room controls on /habitaciones match its permission`, async ({ page }) => {
    await login(page, persona);
    await page.goto("/habitaciones");
    // Scope to <main>: the header's hotel switcher also renders a <select>,
    // which is unrelated to per-room permission controls.
    const main = page.locator("main");
    await expect(main.getByRole("heading", { name: "Habitaciones", exact: true })).toBeVisible();
    await expect(main.locator("p", { hasText: "Hab. 101" })).toBeVisible();

    const roomStatusSelects = main.locator('select[aria-label^="Estado de habitación"]');
    if (persona.label === "manager") {
      await expect(roomStatusSelects.first()).toBeVisible();
      await expect(roomStatusSelects.first().locator("option")).toHaveCount(5);
      await expect(main.getByRole("button", { name: /Crear bloqueo/ })).toBeVisible();
    } else if (persona.label === "receptionist") {
      await expect(roomStatusSelects).toHaveCount(0);
      await expect(main.getByRole("button", { name: /Crear bloqueo/ })).toBeVisible();
    } else {
      await expect(roomStatusSelects.first()).toBeVisible();
      await expect(roomStatusSelects.first().locator("option")).toHaveCount(2);
      await expect(roomStatusSelects.first().locator('option[value="available"]')).toHaveText("Libre");
      await expect(roomStatusSelects.first().locator('option[value="cleaning"]')).toHaveText("Limpieza");
      await expect(main.getByRole("button", { name: /Crear bloqueo/ })).toHaveCount(0);
      await expect(main.getByText("Tarifa hoy:", { exact: false })).toHaveCount(0);
    }
  });
}

test("receptionist can edit guest data and manage tags", async ({ page }) => {
  const receptionist = personas.find((persona) => persona.label === "receptionist")!;
  await login(page, receptionist);
  await page.goto("/huespedes");

  await expect(page.getByRole("heading", { name: "Ficha de huéspedes", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Huesped E2E", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Guardar huésped", exact: true }).click();
  await expect(page.getByText("Huésped guardado.", { exact: true })).toBeVisible();

  const tagSection = page
    .getByRole("heading", { name: "Alertas y segmentación", exact: true })
    .locator("xpath=ancestor::section[1]");
  const tagNote = `QA recepción ${Date.now()}`;
  await tagSection.getByLabel("Etiqueta").selectOption("otro");
  await tagSection.getByLabel("Nota").fill(tagNote);
  await tagSection.getByRole("button", { name: "Agregar", exact: true }).click();
  await expect(page.getByText("Etiqueta agregada.", { exact: true })).toBeVisible();
  const tagPill = tagSection.locator("div").filter({ hasText: tagNote }).last();
  await expect(tagPill).toBeVisible();
  await tagPill.getByRole("button", { name: "Resolver", exact: true }).click();
  await expect(page.getByText("Etiqueta resuelta.", { exact: true })).toBeVisible();
});

test("housekeeping stays inside rooms and laundry without loading restricted data surfaces", async ({ page }) => {
  const housekeeping = personas.find((persona) => persona.label === "housekeeping")!;
  const requestedPaths: string[] = [];
  page.on("request", (request) => requestedPaths.push(new URL(request.url()).pathname));

  await login(page, housekeeping);
  await expect(page.getByRole("heading", { name: "Habitaciones", exact: true })).toBeVisible();

  const navigation = await operationalNavigation(page);
  await expect(navigation.locator('a[href="/operacion/lavanderia"]')).toHaveCount(1);
  const navPaths = await navigation.locator("a[href]").evaluateAll((links) =>
    links.map((link) => link.getAttribute("href")).filter((href): href is string => Boolean(href))
  );
  expect(navPaths.sort()).toEqual(["/habitaciones", "/operacion/lavanderia"].sort());

  for (const forbiddenPath of ["/dashboard", "/huespedes", "/caja", "/reportes", "/operacion/stock", "/settings/security"]) {
    await page.goto(forbiddenPath);
    await expect(page).toHaveURL(/\/habitaciones$/);
  }

  expect(requestedPaths.some((path) => path.startsWith("/api/onboarding"))).toBe(false);
  expect(requestedPaths.some((path) => path.startsWith("/api/subscription"))).toBe(false);
  expect(requestedPaths.some((path) => path === "/api/rooms/categories")).toBe(false);
  expect(requestedPaths.some((path) => path.startsWith("/api/room-blocks"))).toBe(false);
  expect(requestedPaths.some((path) => path.startsWith("/api/guests"))).toBe(false);
  expect(requestedPaths.some((path) => path.startsWith("/api/reports"))).toBe(false);
  expect(requestedPaths.some((path) => path.startsWith("/api/stock"))).toBe(false);
  expect(requestedPaths.some((path) => path.startsWith("/api/cash"))).toBe(false);
  await expect(page.getByText("guest@e2e.com", { exact: false })).toHaveCount(0);
});

test("manager receives operational reports without requesting or rendering financial reports", async ({ page }) => {
  const manager = personas.find((persona) => persona.label === "manager")!;
  const revenueRequests: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/reports/revenue") revenueRequests.push(request.url());
  });

  await login(page, manager);
  await page.goto("/reportes");
  await expect(page.getByText("Llegadas del dia", { exact: true })).toBeVisible();
  await expect(page.getByTestId("financial-report")).toHaveCount(0);
  await expect(page.getByText(/Pagos pendientes/)).toHaveCount(0);
  expect(revenueRequests).toHaveLength(0);
});

test("owner receives the financial report", async ({ page }) => {
  const owner: Persona = {
    label: "owner",
    email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
    password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!",
    landingPath: "/dashboard",
    allowedPath: "/reportes",
    allowedHeading: /^Reportes$/,
    forbiddenNavPaths: []
  };
  await login(page, owner);
  await page.goto("/reportes");
  await expect(page.getByTestId("financial-report")).toBeVisible();
});

test("owner can grant receptionist rates read without granting rate edits", async ({ page }) => {
  const owner: Persona = {
    label: "owner",
    email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
    password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!",
    landingPath: "/dashboard",
    allowedPath: "/reportes",
    allowedHeading: /^Reportes$/,
    forbiddenNavPaths: []
  };
  const receptionist = personas.find((persona) => persona.label === "receptionist")!;

  await login(page, owner);
  const ownerSession = await readApiSession(page, owner);
  const headers = {
    "X-Hotel-Id": String(ownerSession.hotelId),
    "X-User-Id": ownerSession.userId,
    Authorization: `Bearer ${ownerSession.accessToken}`,
    "X-CSRF-Token": String(ownerSession.csrfToken || ""),
    "Content-Type": "application/json"
  };
  const grantResponse = await page.request.put(`${backendURL}/api/permissions/override`, {
    headers,
    data: { role: "receptionist", permission_code: "rates:read", allowed: true }
  });
  expect(grantResponse.ok()).toBeTruthy();
  const grant = (await grantResponse.json()) as { version: number };

  try {
    await login(page, receptionist);
    await page.goto("/operacion/tarifas");
    await expect(page).toHaveURL(/\/operacion\/tarifas$/);
    await expect(page.getByTestId("rate-calendar-page")).toBeVisible();
    await expect(page.getByTestId("rate-calendar-grid")).toBeVisible();
    await expect(page.getByTestId("rate-editor-save")).toBeDisabled();
    await expect(page.getByTestId("rate-editor-grid").locator("input").first()).toBeDisabled();
  } finally {
    const restoreResponse = await page.request.delete(
      `${backendURL}/api/permissions/role-overrides/receptionist/${encodeURIComponent("rates:read")}?expected_version=${grant.version}`,
      { headers }
    );
    expect(restoreResponse.ok()).toBeTruthy();
  }

  await page.goto("/operacion/tarifas");
  await expect(page).toHaveURL(/\/dashboard$/);
});

test("permissions screen shows the catalog help text in an InfoTip", async ({ page }) => {
  const owner: Persona = {
    label: "owner",
    email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
    password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!",
    landingPath: "/dashboard",
    allowedPath: "/reportes",
    allowedHeading: /^Reportes$/,
    forbiddenNavPaths: []
  };

  await login(page, owner);
  const catalogResponsePromise = page.waitForResponse(
    (response) => new URL(response.url()).pathname === "/api/permissions/catalog" && response.ok()
  );
  await page.goto("/settings/permissions");
  const catalogResponse = await catalogResponsePromise;
  const catalog = (await catalogResponse.json()) as {
    permissions: Array<{ description: string; help_es: string }>;
  };
  const permission = catalog.permissions.find((item) => item.help_es.trim());
  expect(permission).toBeDefined();

  const infoButton = page.getByRole("button", { name: `Más información sobre ${permission!.description}` }).first();
  await expect(infoButton).toBeVisible();
  await infoButton.click();
  await expect(page.getByRole("tooltip")).toContainText(permission!.help_es);
});

// D2 (Via D lavanderia): laundry:vendor_manage is owner/co_owner/manager
// only (vendor setup + pricing); housekeeping only holds
// laundry:remito_manage (create/list remitos, see balance). The "Nuevo
// lavadero" panel was shown to everyone regardless and its POST always
// 403'd for housekeeping.
test("housekeeping can create remitos but not manage laundry vendors", async ({ page }) => {
  const housekeeping = personas.find((persona) => persona.label === "housekeeping")!;
  await login(page, housekeeping);
  await page.goto("/operacion/lavanderia");

  const main = page.locator("main");
  await expect(main.getByRole("heading", { name: "Lavanderia", exact: true })).toBeVisible();
  await expect(main.getByRole("button", { name: "Crear lavadero" })).toHaveCount(0);
  await expect(main.getByRole("button", { name: "Guardar remito" })).toBeVisible();
});

test("manager keeps laundry vendor management", async ({ page }) => {
  const manager = personas.find((persona) => persona.label === "manager")!;
  await login(page, manager);
  await page.goto("/operacion/lavanderia");

  const main = page.locator("main");
  await expect(main.getByRole("heading", { name: "Lavanderia", exact: true })).toBeVisible();
  await expect(main.getByRole("button", { name: "Crear lavadero" })).toBeVisible();
});

// PERMISSION_STOCK_ADJUST is owner/co_owner only; manager has PERMISSION_STOCK_MOVE
// (in/out movements) but not adjustments (see _ensure_adjustment_permission in
// app/api/stock.py). StockPage offered the "Ajuste" movement-type option to
// manager regardless, which always 403s on submit.
test("manager does not see the stock adjustment option, only in/out movements", async ({ page }) => {
  const manager = personas.find((persona) => persona.label === "manager")!;
  await login(page, manager);
  await page.goto("/operacion/stock");

  const movementGroup = page.getByRole("group", { name: "Acción de inventario" });
  await expect(movementGroup.getByRole("button", { name: /^Ingreso/ })).toBeVisible();
  await expect(movementGroup.getByRole("button", { name: /^Egreso/ })).toBeVisible();
  await expect(movementGroup.getByRole("button", { name: /^Ajuste/ })).toHaveCount(0);
});
