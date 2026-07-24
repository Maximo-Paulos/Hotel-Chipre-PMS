import { expect, test, type Page } from "@playwright/test";

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

for (const persona of personas) {
  test(`${persona.label} sees only its operational surface`, async ({ page }) => {
    await login(page, persona);

    for (const path of persona.forbiddenNavPaths) {
      await expect(page.locator(`aside nav a[href="${path}"]`)).toHaveCount(0);
    }

    await page.locator(`aside nav a[href="${persona.allowedPath}"]`).click();
    await expect(page).toHaveURL(new RegExp(`${persona.allowedPath.replaceAll("/", "\\/")}$`));
    await expect(page.getByRole("heading", { name: persona.allowedHeading })).toBeVisible();
  });
}
