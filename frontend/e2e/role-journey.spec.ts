import { expect, test, type Locator, type Page } from "@playwright/test";

import { revealCollapsedNavLink } from "./support/sidebar";
import {
  completeStepUpPrompt,
  issueStepUpTicket,
  loginAsStepUpOwner,
  stepUpAuthHeaders
} from "./support/step-up-owner";

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
    allowedHeading: /^Lavandería$/,
    forbiddenNavPaths: ["/caja", "/reportes", "/operacion/stock", "/settings/hotel"]
  }
];

async function login(page: Page, persona: Persona) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(persona.email);
  await page.locator('input[type="password"]').fill(persona.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL(`**${persona.landingPath}`, { timeout: 20_000 });
  await expect(page.getByTestId("session-email")).toHaveText(persona.email);
  const roleLabel: Record<string, string> = {
    owner: "Dueño",
    manager: "Gerencia",
    receptionist: "Recepción",
    housekeeping: "Limpieza"
  };
  await expect(page.getByTestId("session-role")).toHaveText(roleLabel[persona.label]);
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

    // Revealing the allowed link waits for the permissions to load, so the
    // forbidden checks below can't pass on a nav that simply isn't built yet.
    const allowedLink = navigation.locator(`a[href="${persona.allowedPath}"]`);
    await revealCollapsedNavLink(allowedLink);

    for (const path of persona.forbiddenNavPaths) {
      await expect(navigation.locator(`a[href="${path}"]`)).toHaveCount(0);
    }

    await expect(allowedLink).toBeVisible();
    await allowedLink.click();
    await expect(page).toHaveURL(new RegExp(`${persona.allowedPath.replaceAll("/", "\\/")}$`));
    await expect(page.getByRole("heading", { name: persona.allowedHeading })).toBeVisible();
  });
}

test("manager sees a permission message on restricted settings routes without denied configuration reads", async ({ page }) => {
  const manager = personas.find((persona) => persona.label === "manager")!;
  await login(page, manager);

  const forbiddenReads: string[] = [];
  page.on("response", (response) => {
    const url = new URL(response.url());
    if (
      response.status() === 403
      && response.request().method() === "GET"
      && ["/api/config/", "/api/subscription/status"].includes(url.pathname)
    ) {
      forbiddenReads.push(`${response.request().method()} ${url.pathname}`);
    }
  });

  for (const path of ["/settings/hotel", "/settings/subscription"]) {
    await page.goto(path);
    await expect(page).toHaveURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
    await expect(page.getByTestId("permission-denied-page")).toBeVisible();
    await expect(page.getByRole("heading", { name: "No tenés permiso para ver esta sección." })).toBeVisible();
  }

  expect(forbiddenReads).toEqual([]);
});

// State transitions and room blocks are independent capabilities: manager can
// change every state and manage blocks; reception can create blocks but cannot
// change operational state; housekeeping changes only the separate cleaning state.
for (const persona of personas) {
  test(`${persona.label} room controls on /habitaciones match its permission`, async ({ page }) => {
    await login(page, persona);
    await page.goto("/habitaciones");
    // Scope to <main>: the header's hotel switcher also renders a <select>,
    // which is unrelated to per-room permission controls.
    const main = page.locator("main");
    await expect(main.getByRole("heading", { name: "Habitaciones", exact: true })).toBeVisible();
    await expect(
      main.getByTestId("room-card").filter({ hasText: "Hab. 101" }).first()
    ).toBeVisible();

    const roomStatusSelects = main.locator('select[aria-label^="Estado de habitación"]');
    const housekeepingStatusSelects = main.locator('select[aria-label^="Estado de limpieza"]');
    if (persona.label === "manager") {
      await expect(roomStatusSelects.first()).toBeVisible();
      await expect(roomStatusSelects.first().locator("option")).toHaveCount(5);
      await expect(housekeepingStatusSelects).toHaveCount(0);
      await expect(main.getByRole("button", { name: /Crear bloqueo/ })).toBeVisible();
    } else if (persona.label === "receptionist") {
      await expect(roomStatusSelects).toHaveCount(0);
      await expect(housekeepingStatusSelects).toHaveCount(0);
      await expect(main.getByRole("button", { name: /Crear bloqueo/ })).toBeVisible();
    } else {
      const roomListResponse = page.waitForResponse((response) =>
        response.request().method() === "GET" && new URL(response.url()).pathname === "/api/rooms/"
      );
      await page.goto("/habitaciones");
      await expect(main.getByRole("heading", { name: "Habitaciones", exact: true })).toBeVisible();
      await expect(roomStatusSelects).toHaveCount(0);
      await expect(housekeepingStatusSelects.first()).toBeVisible();
      await expect(housekeepingStatusSelects.first().locator("option")).toHaveCount(4);
      await expect(housekeepingStatusSelects.first().locator('option[value="dirty"]')).toHaveText("Sucia");
      await expect(housekeepingStatusSelects.first().locator('option[value="clean"]')).toHaveText("Limpia");
      const rooms = await (await roomListResponse).json() as Array<{
        id: number;
        room_number: string;
        status: string;
        housekeeping_status: string;
      }>;
      const room = rooms.find((candidate) => candidate.room_number === "101");
      expect(room).toBeTruthy();
      const housekeepingSelect = main.getByLabel(`Estado de limpieza · ${room!.room_number}`, { exact: true });
      const updateResponse = page.waitForResponse((response) =>
        response.request().method() === "PATCH" && new URL(response.url()).pathname.endsWith("/cleaning-status")
      );
      await housekeepingSelect.selectOption("clean");
      const updated = await (await updateResponse).json();
      expect(updated.room.status).toBe(room!.status);
      expect(updated.room.housekeeping_status).toBe("clean");
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
  expect(navPaths.sort()).toEqual(["/habitaciones", "/operacion/lavanderia", "/operacion/limpieza-hoy", "/operacion/tareas"].sort());

  for (const forbiddenPath of ["/dashboard", "/huespedes", "/caja", "/reportes", "/operacion/stock", "/settings/security"]) {
    await page.goto(forbiddenPath);
    await expect(page.getByTestId("permission-denied-page")).toBeVisible();
    expect(new URL(page.url()).pathname).toBe(forbiddenPath);
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

test("housekeeping has a privacy-safe daily board that works on a phone", async ({ page }) => {
  const housekeeping = personas.find((persona) => persona.label === "housekeeping")!;
  await login(page, housekeeping);
  await page.setViewportSize({ width: 390, height: 844 });

  let boardPayload: unknown;
  await page.route("**/api/rooms/housekeeping-board", async (route) => {
    const upstreamResponse = await route.fetch();
    expect(upstreamResponse.ok()).toBeTruthy();
    boardPayload = await upstreamResponse.json();
    await route.fulfill({ response: upstreamResponse });
  });

  const boardResponsePromise = page.waitForResponse((response) =>
    response.url().includes("/api/rooms/housekeeping-board") && response.request().method() === "GET"
  );
  await page.goto("/operacion/limpieza-hoy");
  await expect(page.getByRole("heading", { level: 1, name: "Limpieza de hoy" })).toBeVisible();
  const boardResponse = await boardResponsePromise;
  expect(boardResponse.ok()).toBeTruthy();
  const board = boardPayload as {
    rooms: Array<{ room_id: number; room_number: string; housekeeping_status: string }>;
  };
  expect(JSON.stringify(board)).not.toMatch(/guest_name|confirmation_code|guest_id|reservation_id|reason_note/i);
  expect(board.rooms.length).toBeGreaterThan(0);

  const firstRoom = board.rooms[0]!;
  const statusControl = page.getByLabel(`Estado de limpieza · ${firstRoom.room_number}`, { exact: true });
  await expect(statusControl).toBeVisible();
  const nextStatus = firstRoom.housekeeping_status === "clean" ? "dirty" : "clean";
  const statusResponsePromise = page.waitForResponse((response) =>
    response.url().includes(`/api/rooms/${firstRoom.room_id}/cleaning-status`) && response.request().method() === "PATCH"
  );
  await statusControl.selectOption(nextStatus);
  const statusResponse = await statusResponsePromise;
  expect(statusResponse.ok()).toBeTruthy();
  await expect(statusControl).toHaveValue(nextStatus);
});

test("housekeeping can comment on existing tasks and send work for review", async ({ page }) => {
  const housekeeping = personas.find((persona) => persona.label === "housekeeping")!;
  const manager = personas.find((persona) => persona.label === "manager")!;
  await login(page, housekeeping);
  await page.goto("/operacion/tareas");

  const title = `Seguimiento de limpieza ${Date.now()}`;
  await page.getByLabel("Título").fill(title);
  await page.getByLabel("Área").selectOption("housekeeping");
  await page.getByRole("button", { name: "Agregar", exact: true }).click();
  const card = page.locator("article").filter({ hasText: title });
  await expect(card).toBeVisible();
  await card.getByLabel(`Comentario para ${title}`).fill("Repuesto completado; revisar disponibilidad.");
  await card.getByRole("button", { name: "Agregar comentario" }).click();
  await card.getByRole("button", { name: "Ver historial" }).click();
  await expect(card).toContainText("Repuesto completado; revisar disponibilidad.");
  await expect(card.getByRole("button", { name: "Resolver" })).toHaveCount(0);
  await card.getByRole("button", { name: "Tomar" }).click();
  await card.getByRole("button", { name: "Enviar a revisión" }).click();
  await expect(card).toContainText("Pendiente de revisión");
  await expect(card).toContainText("La gerencia revisa y cierra este pendiente.");

  await page.getByTestId("logout-btn").click();
  await page.waitForURL("**/login");
  await login(page, manager);
  await page.goto("/operacion/tareas");

  const managerCard = page.locator("article").filter({ hasText: title });
  await expect(managerCard).toContainText("Pendiente de revisión");
  await managerCard.getByRole("button", { name: "Resolver", exact: true }).click();
  await expect(page.getByText("Tarea resuelta.", { exact: true })).toBeVisible();
  await expect(managerCard).toContainText("Resuelta");
  await managerCard.getByRole("button", { name: "Ver historial" }).click();
  await expect(managerCard).toContainText("Repuesto completado; revisar disponibilidad.");
  await expect(managerCard).toContainText("Resuelta");
});

test("manager receives operational reports without requesting or rendering financial reports", async ({ page }) => {
  const manager = personas.find((persona) => persona.label === "manager")!;
  const revenueRequests: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/reports/revenue") revenueRequests.push(request.url());
  });

  await login(page, manager);
  await page.goto("/reportes");
  await expect(page.getByText("Llegadas del día", { exact: true })).toBeVisible();
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

test("owner can grant receptionist rates read without granting rate edits", async ({ page, request }, testInfo) => {
  // Login, grant, and cleanup each consume a distinct TOTP counter. Cleanup
  // can wait for the next valid 30-second counter after the action ticket.
  test.setTimeout(90_000);
  const receptionist = personas.find((persona) => persona.label === "receptionist")!;

  const ownerSession = await loginAsStepUpOwner(page, "rbac", testInfo.project.name);
  let lastTotpStep = ownerSession.lastTotpStep;
  const headers = stepUpAuthHeaders(ownerSession.auth);
  const grantTicket = await issueStepUpTicket(request, ownerSession.auth, {
    permissionCode: "permissions:manage",
    method: "PUT",
    path: "/api/permissions/override"
  }, lastTotpStep);
  lastTotpStep = grantTicket.lastTotpStep;
  const grantResponse = await request.put(`${backendURL}/api/permissions/override`, {
    headers: { ...headers, "X-Action-Step-Up-Ticket": grantTicket.ticket },
    data: { role: "receptionist", permission_code: "rates:read", allowed: true }
  });
  expect(grantResponse.ok()).toBeTruthy();
  const grant = (await grantResponse.json()) as { version: number };

  try {
    // Hand the browser over the way a shared front-desk computer does: the
    // owner's session ends first, otherwise /login just returns to the owner's
    // dashboard.
    await page.context().clearCookies();
    await login(page, receptionist);
    await page.goto("/operacion/tarifas");
    await expect(page).toHaveURL(/\/operacion\/tarifas$/);
    await expect(page.getByTestId("rate-calendar-page")).toBeVisible();
    await expect(page.getByTestId("rate-calendar-grid")).toBeVisible();
    await expect(page.getByTestId("rate-editor-save")).toBeDisabled();
    await expect(page.getByTestId("rate-editor-grid").locator("input").first()).toBeDisabled();
  } finally {
    const restoreTicket = await issueStepUpTicket(request, ownerSession.auth, {
      permissionCode: "permissions:manage",
      method: "DELETE",
      path: "/api/permissions/role-overrides/receptionist/rates:read"
    }, lastTotpStep);
    const restoreResponse = await request.delete(
      `${backendURL}/api/permissions/role-overrides/receptionist/rates:read?expected_version=${grant.version}`,
      { headers: { ...headers, "X-Action-Step-Up-Ticket": restoreTicket.ticket } }
    );
    expect(restoreResponse.ok()).toBeTruthy();
  }

  await page.goto("/operacion/tarifas");
  await expect(page.getByTestId("permission-denied-page")).toBeVisible();
  expect(new URL(page.url()).pathname).toBe("/operacion/tarifas");
});

test("permissions screen shows the catalog help text in an InfoTip", async ({ page }, testInfo) => {
  const ownerSession = await loginAsStepUpOwner(page, "rbac-info", testInfo.project.name);
  const catalogResponsePromise = page.waitForResponse(
    (response) => new URL(response.url()).pathname === "/api/permissions/catalog" && response.ok()
  );
  await page.goto("/settings/permissions");
  await completeStepUpPrompt(page, ownerSession.lastTotpStep, ownerSession.auth.user.email);
  const catalogResponse = await catalogResponsePromise;
  const catalog = (await catalogResponse.json()) as {
    permissions: Array<{ code: string; description: string; help_es: string }>;
  };
  const permission = catalog.permissions.find((item) => item.help_es.trim());
  expect(permission).toBeDefined();

  // The page also renders an effective-permissions table for the signed-in
  // user, which can contain the same permission code. Scope this lookup to
  // the role matrix under test.
  const permissionRow = page.getByTestId("permissions-matrix").getByRole("row").filter({
    has: page.getByText(permission!.code, { exact: true })
  });
  await expect(permissionRow).toHaveCount(1);
  const infoButton = permissionRow.getByRole("button", {
    name: `Más información sobre ${permission!.description}`,
    exact: true
  });
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
  await expect(main.getByRole("heading", { name: "Lavandería", exact: true })).toBeVisible();
  await expect(main.getByRole("button", { name: "Crear lavadero" })).toHaveCount(0);
  await expect(main.getByRole("button", { name: "Guardar remito" })).toBeVisible();
});

test("manager keeps laundry vendor management", async ({ page }) => {
  const manager = personas.find((persona) => persona.label === "manager")!;
  await login(page, manager);
  await page.goto("/operacion/lavanderia");

  const main = page.locator("main");
  await expect(main.getByRole("heading", { name: "Lavandería", exact: true })).toBeVisible();
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
