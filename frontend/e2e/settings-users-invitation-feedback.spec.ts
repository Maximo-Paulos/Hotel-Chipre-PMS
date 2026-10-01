import { expect, test, type Page } from "@playwright/test";

const backendURL = process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040";
const ownerPermissions = ["dashboard:view", "settings:users:view", "settings:users:manage"];
const authResponse = {
  access_token: "synthetic-owner-token",
  token_type: "bearer",
  csrf_token: "synthetic-csrf-token",
  hotel_id: 42,
  hotel_ids: [42],
  permissions: ownerPermissions,
  user: {
    id: 1,
    email: "owner@example.test",
    role: "owner",
    is_verified: true,
    is_active: true,
    permissions: ownerPermissions
  }
};

test("F-050 requires an invitation role and confirms role changes visibly", async ({ page }) => {
  let loggedIn = false;
  let memberRole = "manager";
  const roleWrites: string[] = [];
  const invitePayloads: Array<Record<string, unknown>> = [];

  await page.route(`${backendURL}/api/**`, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

    if (pathname === "/api/auth/session/refresh") {
      if (!loggedIn) return json({ detail: "No session" }, 401);
      return json(authResponse);
    }
    if (pathname === "/api/auth/login" && method === "POST") {
      loggedIn = true;
      return json(authResponse);
    }
    if (pathname === "/api/onboarding/status") {
      return json({ hotel_id: 42, completed: true, steps: {}, missing_steps: [], counts: {} });
    }
    if (pathname === "/api/subscription/status") {
      return json({ hotel_id: 42, status: "active", plan: "pro", can_write: true, limits: [] });
    }
    if (pathname === "/api/permissions/effective") {
      return json({ hotel_id: 42, role: "owner", permissions: ownerPermissions });
    }
    if (pathname === "/api/auth/mfa/status") return json({ enabled: true });
    if (pathname === "/api/notifications") return json({ items: [], unread_count: 0 });
    if (pathname === "/api/roles" && method === "GET") {
      return json({
        roles: ["owner", "co_owner", "manager", "receptionist", "housekeeping"].map((code) => ({
          code,
          name: code,
          kind: "builtin",
          base_role: null,
          is_active: true,
          assigned_count: code === "owner" ? 1 : 0,
          pending_invitation_count: 0,
          permission_count: 1,
          version: 1
        }))
      });
    }
    if (pathname === "/api/users/" && method === "GET") {
      return json([
        { id: 1, email: "owner@example.test", role: "owner", is_verified: true, is_active: true },
        { id: 2, email: "staff@example.test", role: memberRole, is_verified: true, is_active: true }
      ]);
    }
    if (pathname === "/api/users/aliases" && method === "GET") {
      return json({ items: [
        { user_id: 1, email: "owner@example.test", role: "owner", status: "active", alias: null },
        { user_id: 2, email: "staff@example.test", role: memberRole, status: "active", alias: null }
      ] });
    }
    if (pathname === "/api/users/invitations" && method === "GET") return json([]);
    if (pathname === "/api/users/invite" && method === "POST") {
      const payload = request.postDataJSON() as Record<string, unknown>;
      invitePayloads.push(payload);
      return json({
        user: { id: 3, email: payload.email, role: payload.role, is_verified: false, is_active: true },
        invitation_id: 9,
        invite_token: "synthetic-invitation-token",
        accept_url: "https://example.test/invitations/accept#token=synthetic-invitation-token",
        email_delivery: "not_configured"
      }, 201);
    }
    if (pathname === "/api/users/2/role" && method === "PATCH") {
      const payload = request.postDataJSON() as { role: string };
      memberRole = payload.role;
      roleWrites.push(payload.role);
      return json({ id: 2, email: "staff@example.test", role: memberRole, is_verified: true, is_active: true });
    }

    return json({});
  });

  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.locator('input[type="email"]').fill("owner@example.test");
  await page.locator('input[type="password"]').fill("synthetic-password");
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard");
  await page.goto("/settings/users");

  const inviteRole = page.getByLabel("Rol para invitar");
  await expect(inviteRole).toHaveValue("");
  await expect(page.getByRole("button", { name: "Invitar", exact: true })).toBeDisabled();
  await page.getByLabel("Email de invitación").fill("new-staff@example.test");
  await inviteRole.selectOption("receptionist");
  await page.getByRole("button", { name: "Invitar", exact: true }).click();
  await expect.poll(() => invitePayloads.length).toBe(1);
  expect(invitePayloads[0]).toMatchObject({ email: "new-staff@example.test", role: "receptionist" });
  await expect(inviteRole).toHaveValue("");

  const memberRoleSelect = page.getByLabel("Rol de staff@example.test");
  page.once("dialog", (dialog) => void dialog.dismiss());
  await memberRoleSelect.selectOption("co_owner");
  await expect(memberRoleSelect).toHaveValue("manager");
  expect(roleWrites).toEqual([]);

  page.once("dialog", (dialog) => void dialog.accept());
  await memberRoleSelect.selectOption("receptionist");
  await expect.poll(() => roleWrites).toEqual(["receptionist"]);
  await expect(memberRoleSelect).toHaveValue("receptionist");
  await expect(page.getByRole("status")).toContainText("Rol de staff@example.test actualizado a Recepción");
});
