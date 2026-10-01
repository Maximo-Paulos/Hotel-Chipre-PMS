import { expect, test } from "@playwright/test";

const authenticatedManager = {
  access_token: "synthetic-access-token",
  token_type: "bearer",
  hotel_id: 42,
  hotel_ids: [42],
  user: {
    id: 7,
    email: "manager@example.test",
    role: "manager",
    is_verified: true,
    is_active: true,
    permissions: ["dashboard:view"]
  },
  permissions: ["dashboard:view"],
  csrf_token: "synthetic-csrf-token"
};

test("a reused invitation link exits to login without carrying the token", async ({ page }) => {
  const backendURL = process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040";
  await page.route(`${backendURL}/api/**`, async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/invitations/preview") {
      return route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({
          detail: {
            code: "INVITATION_ALREADY_ACCEPTED",
            msg: "Esta invitación ya fue aceptada."
          }
        })
      });
    }
    if (path === "/api/auth/session/refresh") {
      return route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "No active session" }) });
    }
    if (path === "/api/auth/providers") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ google: { enabled: false, client_id: null, self_signup_enabled: false, allowed_domains: [] } })
      });
    }
    return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not found" }) });
  });

  await page.goto("/invitations/accept#token=reused-invitation-token");
  await expect(page.getByRole("alert")).toContainText("Puede que ya la hayas usado o haya vencido");
  await page.getByRole("link", { name: "Volver al ingreso" }).click();

  await expect(page).toHaveURL(/\/login$/);
  expect(new URL(page.url()).hash).toBe("");
  await expect(page.getByRole("status")).toContainText("Ingresá con tu cuenta");
});

test("a signed-in user can leave a reused invitation for their account", async ({ page }) => {
  const backendURL = process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040";
  await page.route(`${backendURL}/api/**`, async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/invitations/preview") {
      return route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ detail: { code: "INVITATION_ALREADY_ACCEPTED", msg: "Esta invitación ya fue aceptada." } })
      });
    }
    if (path === "/api/auth/session/refresh") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(authenticatedManager) });
    }
    if (path === "/api/auth/providers") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ google: { enabled: false, client_id: null, self_signup_enabled: false, allowed_domains: [] } })
      });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
  });

  await page.goto("/invitations/accept#token=reused-invitation-token");
  await expect(page.getByRole("alert")).toContainText("Puede que ya la hayas usado o haya vencido");
  await page.getByRole("link", { name: "Ir a mi cuenta" }).click();
  await expect(page).not.toHaveURL(/invitations\/accept/);
});
