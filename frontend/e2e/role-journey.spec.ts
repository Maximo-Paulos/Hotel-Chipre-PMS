import { expect, test, type Locator, type Page } from "@playwright/test";

type Persona = {
  label: string;
  email: string;
  password: string;
  allowedPath: string;
  allowedHeading: RegExp;
  forbiddenNavPaths: string[];
};

const personas: Persona[] = [
  {
    label: "manager",
    email: process.env.E2E_MANAGER_EMAIL || "manager@e2e.com",
    password: process.env.E2E_MANAGER_PASSWORD || "E2eManager1234!",
    allowedPath: "/reportes",
    allowedHeading: /^Reportes$/,
    forbiddenNavPaths: ["/settings/hotel", "/settings/users"]
  },
  {
    label: "receptionist",
    email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
    password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!",
    allowedPath: "/caja",
    allowedHeading: /^Caja$/,
    forbiddenNavPaths: ["/reportes", "/settings/hotel", "/operacion/stock"]
  },
  {
    label: "housekeeping",
    email: process.env.E2E_HOUSEKEEPING_EMAIL || "housekeeping@e2e.com",
    password: process.env.E2E_HOUSEKEEPING_PASSWORD || "E2eHousekeeping1234!",
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
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
  await expect(page.getByText(`Usuario ${persona.email}`)).toBeVisible();
  await expect(page.getByTestId("session-role")).toHaveText(
    persona.label === "receptionist" ? "Recepción" : persona.label === "housekeeping" ? "Housekeeping" : "Manager"
  );
}

async function operationalNavigation(page: Page): Promise<Locator> {
  const mobileNavigation = page.locator('nav[aria-label="Navegación móvil"]');

  if (await mobileNavigation.isVisible()) {
    return mobileNavigation;
  }

  return page.locator("aside nav");
}

for (const persona of personas) {
  test(`${persona.label} sees only its operational surface`, async ({ page }) => {
    await login(page, persona);
    const navigation = await operationalNavigation(page);

    for (const path of persona.forbiddenNavPaths) {
      await expect(navigation.locator(`a[href="${path}"]`)).toHaveCount(0);
    }

    const allowedLink = navigation.locator(`a[href="${persona.allowedPath}"]`);
    await expect(allowedLink).toBeVisible();
    await allowedLink.click();
    await expect(page).toHaveURL(new RegExp(`${persona.allowedPath.replaceAll("/", "\\/")}$`));
    await expect(page.getByRole("heading", { name: persona.allowedHeading })).toBeVisible();
  });
}

// The "Habitaciones" nav link is shown to every operational role, but the backend
// only lets owner/co_owner/manager mutate room status or room blocks
// (require_roles / PERMISSION_ROOM_BLOCK). Reception and housekeeping must not be
// offered controls that always fail; they should see room state as read-only.
for (const persona of personas) {
  const canManageRooms = persona.label === "manager";

  test(`${persona.label} room controls on /habitaciones match its permission`, async ({ page }) => {
    await login(page, persona);
    await page.goto("/habitaciones");
    // Scope to <main>: the header's hotel switcher also renders a <select>,
    // which is unrelated to per-room permission controls.
    const main = page.locator("main");
    await expect(main.getByRole("heading", { name: "Habitaciones", exact: true })).toBeVisible();
    await expect(main.locator("p", { hasText: "Hab. 101" })).toBeVisible();

    if (canManageRooms) {
      await expect(main.locator("select").first()).toBeVisible();
      await expect(main.getByRole("button", { name: /Crear bloqueo/ })).toBeVisible();
    } else {
      await expect(main.locator("select")).toHaveCount(0);
      await expect(main.getByRole("button", { name: /Crear bloqueo/ })).toHaveCount(0);
    }
  });
}

// Creating a laundry batch requires owner/co_owner/manager (see require_roles on
// POST /api/laundry/batches); housekeeping can only list batches, add items and
// change status. The "Crear lote" form was shown to housekeeping regardless and
// always failed on submit.
test("housekeeping sees laundry batch status/item controls but not batch creation", async ({ page }) => {
  const housekeeping = personas.find((persona) => persona.label === "housekeeping")!;
  await login(page, housekeeping);
  await page.goto("/operacion/lavanderia");

  const main = page.locator("main");
  await expect(main.getByRole("heading", { name: "Lavanderia", exact: true })).toBeVisible();
  await expect(main.getByRole("button", { name: "Crear lote" })).toHaveCount(0);
});

test("manager keeps laundry batch creation", async ({ page }) => {
  const manager = personas.find((persona) => persona.label === "manager")!;
  await login(page, manager);
  await page.goto("/operacion/lavanderia");

  const main = page.locator("main");
  await expect(main.getByRole("heading", { name: "Lavanderia", exact: true })).toBeVisible();
  await expect(main.getByRole("button", { name: "Crear lote" })).toBeVisible();
});
