import { expect, test, type Page } from "@playwright/test";

// C4: "Cambiar vista" (UserBadge's role switcher) only ever changes
// session.role, which drives menu visibility and read-only-vs-editable
// previews -- it never reaches the backend (buildAuthHeaders doesn't send a
// role header; the backend derives the real permission from the JWT/
// HotelMembership via session.baseRole). Two things this spec locks in:
// 1. The switcher is honest about being a preview: a banner says so, and
//    baseRole-gated screens (real mutations, real secrets) keep behaving
//    like the real user, not the previewed one.
// 2. Manipulating localStorage directly to fake a higher role (bypassing
//    the switcher UI entirely) only ever changes what's cosmetically shown
//    -- it never unlocks a baseRole-gated screen, and never produces a
//    broken page.

const owner = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};
const receptionist = {
  email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
  password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!"
};

async function login(page: Page, credentials: { email: string; password: string }) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("owner previewing as Manager sees the honesty banner and keeps owner-only actions", async ({ page }) => {
  await login(page, owner);

  await expect(page.getByTestId("role-switcher")).toBeVisible();
  await page.getByTestId("role-switcher").selectOption("manager");
  await page.waitForURL("**/dashboard");

  await expect(page.getByTestId("viewing-as-banner")).toContainText("Vista previa como Manager");
  await expect(page.getByTestId("viewing-as-banner")).toContainText("no cambia permisos ni identidad");
  await expect(page.getByTestId("session-role")).toHaveText("Manager");

  // StockPage's "Ajuste" option is gated on baseRole (owner), not the
  // previewed role: the real owner keeps it even while previewing as
  // Manager, who wouldn't normally see it (see role-journey.spec.ts).
  await page.goto("/operacion/stock");
  const movementGroup = page.getByRole("group", { name: "Acción de inventario" });
  await expect(movementGroup.getByRole("button", { name: /^Ajuste/ })).toBeVisible();

  await page.getByTestId("reset-role-btn").click();
  await expect(page.getByTestId("viewing-as-banner")).toHaveCount(0);
  await expect(page.getByTestId("session-role")).toHaveText("Dueño");
});

test("a role spoofed directly in localStorage does not unlock baseRole-gated screens for a real receptionist", async ({
  page
}) => {
  await login(page, receptionist);
  await expect(page.getByTestId("session-role")).toHaveText("Recepción");
  // The switcher itself is owner-only and must stay hidden for this persona.
  await expect(page.getByTestId("role-switcher")).toHaveCount(0);

  // Simulate an employee editing localStorage directly (not via the UI) to
  // claim a role they don't have.
  await page.evaluate(() => {
    const raw = localStorage.getItem("hotel-pms-session");
    if (!raw) throw new Error("no session in localStorage");
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    parsed.role = "owner";
    localStorage.setItem("hotel-pms-session", JSON.stringify(parsed));
  });
  await page.reload();

  // The label can remain cosmetically spoofed because preview state is local,
  // but the authenticated base role and effective permission set remain the
  // security boundary.
  await expect(page.getByTestId("session-role")).toBeVisible();

  const sensitiveRequests: string[] = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path === "/api/permissions/matrix" || path.startsWith("/api/stock")) sensitiveRequests.push(path);
  });

  // Deep-link guards use the authenticated baseRole/effective permissions,
  // so neither protected page mounts and no sensitive request is issued.
  await page.goto("/settings/permissions");
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.goto("/operacion/stock");
  await expect(page).toHaveURL(/\/dashboard$/);
  expect(sensitiveRequests).toHaveLength(0);
});
