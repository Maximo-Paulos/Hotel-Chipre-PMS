import { expect, test, type BrowserContext, type Page, type Request } from "@playwright/test";

import { navigateFromShell } from "./support/sidebar";

test.use({ screenshot: "off", video: "off", trace: "off", locale: "es-AR" });

type Persona = {
  name: "owner" | "manager" | "receptionist" | "housekeeping";
  email: string;
  password: string;
  landingPath: string;
  roomInventory: boolean;
};

const personas: Persona[] = [
  {
    name: "owner",
    email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
    password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!",
    landingPath: "/dashboard",
    roomInventory: true
  },
  {
    name: "manager",
    email: process.env.E2E_MANAGER_EMAIL || "manager@e2e.com",
    password: process.env.E2E_MANAGER_PASSWORD || "E2eManager1234!",
    landingPath: "/dashboard",
    roomInventory: false
  },
  {
    name: "receptionist",
    email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
    password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!",
    landingPath: "/dashboard",
    roomInventory: false
  },
  {
    name: "housekeeping",
    email: process.env.E2E_HOUSEKEEPING_EMAIL || "housekeeping@e2e.com",
    password: process.env.E2E_HOUSEKEEPING_PASSWORD || "E2eHousekeeping1234!",
    landingPath: "/habitaciones",
    roomInventory: true
  }
];

async function login(page: Page, persona: Persona) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(persona.email);
  await page.locator('input[type="password"]').fill(persona.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL(`**${persona.landingPath}`, { timeout: 20_000 });
}

async function logout(page: Page) {
  await page.getByTestId("logout-btn").click();
  await page.waitForURL("**/login");
}

test("H31: four cold user sessions load all 30 room cards and expose page/API timings", async ({ browser }) => {
  test.skip(process.env.E2E_F003_LOAD !== "true", "Requires the isolated PostgreSQL 16 30-room/45-reservation fixture.");
  test.setTimeout(240_000);

  const contexts: BrowserContext[] = [];
  const pageLoadsMs: number[] = [];
  const apiDurationsMs = new Map<string, number[]>();
  const serverErrors: Array<{ persona: string; path: string; status: number }> = [];

  try {
    for (let iteration = 0; iteration < 3; iteration += 1) {
      const sessions = await Promise.all(personas.map(async (persona) => {
        const context = await browser.newContext({ locale: "es-AR", viewport: { width: 1365, height: 900 } });
        contexts.push(context);
        const page = await context.newPage();
        const requestStartedAt = new WeakMap<Request, number>();
        page.on("request", (request) => {
          if (new URL(request.url()).pathname.startsWith("/api/")) {
            requestStartedAt.set(request, performance.now());
          }
        });
        page.on("response", (response) => {
          const path = new URL(response.url()).pathname;
          const startedAt = requestStartedAt.get(response.request());
          if (!path.startsWith("/api/") || startedAt === undefined) return;
          const durationMs = Math.round(performance.now() - startedAt);
          const samples = apiDurationsMs.get(path) ?? [];
          samples.push(durationMs);
          apiDurationsMs.set(path, samples);
          if (response.status() >= 500) {
            serverErrors.push({ persona: persona.name, path, status: response.status() });
          }
        });
        await login(page, persona);
        return { persona, page };
      }));

      await Promise.all(sessions.map(async ({ persona, page }) => {
        const path = persona.roomInventory ? "/habitaciones" : "/reservas";
        await navigateFromShell(page, path);
        if (!persona.roomInventory) {
          await expect(page.locator("main").getByRole("heading", { name: "Reservas" }).first()).toBeVisible();
          return;
        }
        const startedAt = performance.now();
        await page.reload();
        const cards = page.getByTestId("room-card");
        await expect(cards).toHaveCount(30, { timeout: 60_000 });
        await expect(cards.first()).toContainText("Doble Estándar", { timeout: 60_000 });
        expect(await cards.count()).toBe(30);
        pageLoadsMs.push(Math.round(performance.now() - startedAt));
      }));
    }
  } finally {
    await Promise.all(contexts.map((context) => context.close()));
  }

  const sortedPageLoads = [...pageLoadsMs].sort((left, right) => left - right);
  const percentile = (samples: number[], value: number) =>
    samples[Math.min(samples.length - 1, Math.ceil(samples.length * value) - 1)] ?? 0;
  const apiSummary = Object.fromEntries(
    [...apiDurationsMs.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([path, samples]) => [path, {
      count: samples.length,
      p95_ms: percentile([...samples].sort((left, right) => left - right), 0.95),
      max_ms: Math.max(...samples)
    }])
  );

  console.info("[H31 room inventory baseline]", JSON.stringify({
    workload: "3 cold rounds × owner, manager, receptionist, housekeeping",
    visible_room_cards_per_room_role: 30,
    room_page_load_measurement: "cold full-page reload with fresh React Query state",
    room_page_loads_ms: { samples: pageLoadsMs, p50: percentile(sortedPageLoads, 0.5), max: Math.max(...pageLoadsMs) },
    api: apiSummary,
    server_errors: serverErrors.length
  }));
  expect(pageLoadsMs).toHaveLength(6);
  expect(serverErrors).toEqual([]);
});

test("H31: housekeeping sees a room blocked for maintenance", async ({ page }) => {
  test.skip(process.env.E2E_F003_LOAD !== "true", "Requires the isolated PostgreSQL 16 30-room/45-reservation fixture.");
  test.setTimeout(90_000);

  await login(page, personas[0], "/dashboard");
  await page.goto("/habitaciones");
  const blockForm = page.locator("form").filter({ hasText: "Crear bloqueo" });
  await blockForm.getByLabel("Habitación").selectOption({ label: "Hab. 305" });
  const startsOn = await blockForm.getByLabel("Desde").inputValue();
  const [year, month, day] = startsOn.split("-").map(Number);
  const endsOn = new Date(Date.UTC(year, month - 1, day + 1)).toISOString().slice(0, 10);
  await blockForm.getByLabel("Hasta").fill(endsOn);
  await blockForm.getByLabel("Motivo").selectOption("maintenance");
  await blockForm.getByLabel("Detalle").fill("Validación H31 de mantenimiento activo");
  await blockForm.getByRole("button", { name: "Crear bloqueo", exact: true }).click();
  await expect(page.getByText("Bloqueo creado.", { exact: true })).toBeVisible();

  await logout(page);
  await login(page, personas[3], "/habitaciones");
  const roomCard = page.getByTestId("room-card").filter({ hasText: "Hab. 305" });
  await expect(roomCard).toContainText("Libre");
  await expect(roomCard).toContainText("Bloqueada por mantenimiento");
});

test("H31: housekeeping gets a zero-stock linen alert in each office", async ({ page }) => {
  test.skip(process.env.E2E_F003_LOAD !== "true", "Requires the isolated PostgreSQL 16 30-room/45-reservation fixture.");
  test.setTimeout(90_000);

  const suffix = Date.now().toString();
  const itemName = `QA H31 Toallon pileta ${suffix}`;
  const locationNames = [`QA H31 Office 2 ${suffix}`, `QA H31 Office 3 ${suffix}`];

  await login(page, personas[0], "/dashboard");
  await page.goto("/operacion/lavanderia");
  const itemForm = page.locator("form").filter({ hasText: "Nuevo tipo de ropa blanca" });
  await itemForm.getByLabel("Nombre").fill(itemName);
  await itemForm.getByRole("button", { name: "Crear tipo de ropa blanca", exact: true }).click();
  await expect(page.getByText("Tipo de ropa blanca creado.", { exact: true })).toBeVisible();

  const locationForm = page.locator("form").filter({ hasText: "Nueva ubicación" });
  for (const locationName of locationNames) {
    await locationForm.getByLabel("Nombre").fill(locationName);
    await locationForm.getByRole("button", { name: "Crear ubicación", exact: true }).click();
    await expect(page.getByText("Ubicación de lavandería creada.", { exact: true })).toBeVisible();
  }
  await logout(page);

  await login(page, personas[3], "/habitaciones");
  await page.goto("/operacion/lavanderia");
  const houseStock = page.locator('section[aria-labelledby="house-stock-title"]');
  for (const locationName of locationNames) {
    await houseStock.getByLabel("Ubicación").selectOption({ label: locationName });
    await expect(houseStock.getByRole("alert")).toContainText(
      `No hay unidades disponibles de ${itemName} en esta ubicación.`
    );
  }
});
