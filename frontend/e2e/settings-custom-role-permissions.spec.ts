import { expect, test, type Page } from "@playwright/test";

const builtinRoles = ["owner", "co_owner", "manager", "receptionist", "housekeeping"];
const customRoleCode = "night-auditor";
const permissionCode = "guest:read";
const assistantActionsPermissionCode = "settings:assistant:actions:manage";

const roleCatalog = {
  roles: [
    ...builtinRoles.map((code) => ({
      code,
      name: code,
      kind: "builtin" as const,
      base_role: null,
      is_active: true,
      assigned_count: code === "owner" ? 1 : 0,
      pending_invitation_count: 0,
      permission_count: 1,
      version: 1
    })),
    {
      code: customRoleCode,
      name: "Auditoría nocturna",
      kind: "custom" as const,
      base_role: "receptionist",
      is_active: true,
      assigned_count: 0,
      pending_invitation_count: 2,
      permission_count: 1,
      version: 2
    },
    {
      code: "old-auditor",
      name: "Auditoría archivada",
      kind: "custom" as const,
      base_role: "manager",
      is_active: false,
      assigned_count: 0,
      pending_invitation_count: 0,
      permission_count: 1,
      version: 3
    }
  ]
};

const matrixForRoles = Object.fromEntries(
  [...builtinRoles, customRoleCode].map((role) => [
    role,
    {
      [permissionCode]: {
        allowed: true,
        source: "default",
        description: "Consultar huéspedes",
        module: "guests",
        help_es: "Permite consultar huéspedes."
      },
      "permissions:manage": {
        allowed: role === "owner",
        source: "invariant",
        description: "Administrar permisos",
        module: "permissions",
        help_es: "Permiso crítico.",
        locked: true,
        lock_reason: "owner_only"
      },
      [assistantActionsPermissionCode]: {
        allowed: role === "owner" || role === "co_owner",
        source: role === "owner" || role === "co_owner" ? "role_default" : "invariant",
        description: "Revisar acciones del asistente",
        module: "settings",
        help_es: "Revisar y aplicar acciones sugeridas por el asistente.",
        locked: role !== "owner" && role !== "co_owner",
        lock_reason: role === "owner" || role === "co_owner" ? null : "role_scope"
      }
    }
  ])
);

const profilesForRoles = Object.fromEntries(
  [...builtinRoles, customRoleCode].map((role) => [
    role,
    {
      [permissionCode]: {
        allowed: true,
        source: "role_default",
        locked: false,
        lock_reason: null,
        description: "Consultar huéspedes",
        module: "guests",
        help_es: "Permite consultar huéspedes."
      },
      "permissions:manage": {
        allowed: role === "owner",
        source: "invariant",
        locked: true,
        lock_reason: "owner_only",
        description: "Administrar permisos",
        module: "permissions",
        help_es: "Permiso crítico."
      },
      [assistantActionsPermissionCode]: {
        allowed: role === "owner" || role === "co_owner",
        source: role === "owner" || role === "co_owner" ? "role_default" : "invariant",
        locked: role !== "owner" && role !== "co_owner",
        lock_reason: role === "owner" || role === "co_owner" ? null : "role_scope",
        description: "Revisar acciones del asistente",
        module: "settings",
        help_es: "Revisar y aplicar acciones sugeridas por el asistente."
      }
    }
  ])
);

const authResponse = {
  access_token: "test-token",
  token_type: "bearer",
  csrf_token: "test-csrf",
  hotel_id: 1,
  hotel_ids: [1],
  permissions: ["permissions:manage"],
  user: {
    id: 1,
    email: "owner@example.com",
    role: "owner",
    is_verified: true,
    is_active: true,
    permissions: ["permissions:manage"]
  }
};

async function installMocks(page: Page, options: { rolesFailure?: boolean; overrideStatus?: number; legacyUserDeny?: boolean } = {}) {
  let loggedIn = false;
  const writes: Array<{ path: string; method: string; payload: unknown }> = [];

  await page.route("https://fonts.googleapis.com/**", (route) => route.fulfill({ status: 200, body: "" }));
  await page.route("https://fonts.gstatic.com/**", (route) => route.abort());
  await page.route("http://127.0.0.1:8040/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;
    const method = request.method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

    if (pathname.endsWith("/api/auth/session/refresh") && !loggedIn) {
      await json({ detail: "No session" }, 401);
      return;
    }
    if (pathname.endsWith("/api/auth/login") || pathname.endsWith("/api/auth/session/refresh")) {
      loggedIn = true;
      await json(authResponse);
      return;
    }
    if (pathname.endsWith("/api/onboarding/status")) {
      await json({ hotel_id: 1, completed: true, steps: {}, missing_steps: [], counts: {} });
      return;
    }
    if (pathname.endsWith("/api/subscription/status")) {
      await json({ hotel_id: 1, status: "active", plan: "pro", room_limit: 40, staff_limit: 8, rooms_in_use: 10, can_write: true, limits: [] });
      return;
    }
    if (pathname.endsWith("/api/permissions/effective")) {
      await json({ hotel_id: 1, role: "owner", permissions: ["permissions:manage"] });
      return;
    }
    if (pathname.endsWith("/api/notifications")) {
      await json({ items: [], unread_count: 0 });
      return;
    }
    if (pathname === "/api/roles" && method === "GET") {
      if (options.rolesFailure) {
        await json({ detail: "Role catalog unavailable" }, 503);
        return;
      }
      await json(roleCatalog);
      return;
    }
    if (pathname.endsWith("/api/permissions/catalog")) {
      await json({
        hotel_id: 1,
        permissions: [
          { code: permissionCode, module: "guests", description: "Consultar huéspedes", help_es: "Permite consultar huéspedes.", legacy_aliases: [], locked: false, lock_reason: null, critical: false, step_up_required: false, delegable: true },
          { code: assistantActionsPermissionCode, module: "settings", description: "Revisar acciones del asistente", help_es: "Revisar y aplicar acciones sugeridas por el asistente.", legacy_aliases: [], locked: false, lock_reason: null, critical: false, step_up_required: false, delegable: true },
          { code: "permissions:manage", module: "permissions", description: "Administrar permisos", help_es: "Permiso crítico.", legacy_aliases: [], locked: true, lock_reason: "owner_only", critical: true, step_up_required: true, delegable: false }
        ]
      });
      return;
    }
    if (pathname.endsWith("/api/permissions/matrix")) {
      await json({ hotel_id: 1, matrix: matrixForRoles });
      return;
    }
    if (pathname.endsWith("/api/permissions/role-overrides") && method === "GET") {
      await json({ hotel_id: 1, matrix: profilesForRoles });
      return;
    }
    const userOverridesMatch = pathname.match(/\/api\/permissions\/user-overrides\/(\d+)$/);
    if (userOverridesMatch && method === "GET") {
      const userId = Number(userOverridesMatch[1]);
      const role = userId === 2 ? "co_owner" : "old-auditor";
      const details = { ...(profilesForRoles[role] ?? {}) };
      if (options.legacyUserDeny && userId === 2) {
        details[assistantActionsPermissionCode] = {
          ...details[assistantActionsPermissionCode],
          allowed: false,
          source: "legacy_user_deny",
          legacy_permission_code: "settings:assistant:view"
        };
      }
      await json({ hotel_id: 1, user_id: userId, role, details });
      return;
    }
    if (pathname.endsWith("/api/permissions/visibility-windows") && method === "GET") {
      await json({
        hotel_id: 1,
        windows: [...builtinRoles, customRoleCode].map((role) => ({ role, past_hours: 24, future_hours: 24, updated_by_user_id: null, updated_at: null }))
      });
      return;
    }
    if (pathname.endsWith("/api/permissions/visibility-windows") && method === "PUT") {
      const payload = request.postDataJSON();
      writes.push({ path: pathname, method, payload });
      await json({ role: payload.role, past_hours: payload.past_hours, future_hours: payload.future_hours, updated_by_user_id: 1, updated_at: new Date().toISOString() });
      return;
    }
    if (pathname.endsWith("/api/permissions/override") && method === "PUT") {
      const payload = request.postDataJSON();
      writes.push({ path: pathname, method, payload });
      const responseBody = options.overrideStatus === 403
        ? { detail: "Not authorized" }
        : options.overrideStatus === 409
          ? { detail: "El permiso fue modificado por otra solicitud" }
          : { hotel_id: 1, role: payload.role, permission_code: payload.permission_code, allowed: payload.allowed, version: 2, source: "role_override", locked: false };
      await json(responseBody, options.overrideStatus ?? 200);
      return;
    }
    if (pathname.endsWith("/api/users/")) {
      await json([
        { id: 2, email: "co-owner@example.com", role: "co_owner", is_verified: true, is_active: true, password_login_enabled: true },
        { id: 3, email: "archived-user@example.com", role: "old-auditor", is_verified: true, is_active: true, password_login_enabled: true }
      ]);
      return;
    }

    await json({ detail: `Unhandled mock: ${method} ${pathname}` }, 404);
  });

  return writes;
}

async function openPermissions(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.locator('input[type="email"]').fill("owner@example.com");
  await page.locator('input[type="password"]').fill("test-password");
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard");
  await page.goto("/settings/permissions");
  await expect(page.getByTestId("permissions-matrix")).toBeVisible();
}

test("shows an active custom role by name and uses its code for permission and visibility writes", async ({ page }, testInfo) => {
  const writes = await installMocks(page);
  await openPermissions(page);

  await expect(page.getByRole("checkbox", { name: "Consultar huéspedes para Auditoría nocturna" })).toBeVisible();
  await expect(page.getByTestId(`permission-toggle-${customRoleCode}-${permissionCode}`)).toBeEnabled();
  await expect(page.getByTestId("permission-toggle-old-auditor-guest:read")).toHaveCount(0);
  await expect(page.getByTestId(`permission-toggle-owner-${permissionCode}`)).toBeDisabled();
  await expect(page.getByTestId(`permission-toggle-co_owner-${permissionCode}`)).toBeDisabled();
  await expect(page.getByTestId(`permission-toggle-${customRoleCode}-permissions:manage`)).toBeDisabled();
  const customRoleEntry = page.getByRole("listitem").filter({ hasText: "Auditoría nocturna" });
  await expect(customRoleEntry.getByRole("button", { name: "Archivar" })).toBeDisabled();
  await expect(customRoleEntry).toContainText("2 invitaciones pendientes");
  await expect(customRoleEntry).toContainText("no se eliminan automáticamente");
  await expect(customRoleEntry).not.toContainText(/borrar.*asignaciones automáticamente/i);

  await page.screenshot({ path: testInfo.outputPath("custom-roles-desktop.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: testInfo.outputPath("custom-roles-mobile.png") });
  await page.setViewportSize({ width: 1280, height: 900 });

  await page.getByTestId(`permission-toggle-${customRoleCode}-${permissionCode}`).click();
  await expect.poll(() => writes.some((write) => (write.payload as { role?: string }).role === customRoleCode)).toBe(true);
  expect(writes.find((write) => write.path.endsWith("/permissions/override"))?.payload).toMatchObject({
    role: customRoleCode,
    permission_code: permissionCode,
    allowed: false,
    expected_version: 0
  });

  const visibilityWindow = page.getByLabel("Ventana de visibilidad para Auditoría nocturna").first();
  await expect(visibilityWindow).toBeEnabled();
  await visibilityWindow.selectOption("48");
  await expect.poll(() => writes.some((write) => write.path.endsWith("/visibility-windows"))).toBe(true);
  expect(writes.find((write) => write.path.endsWith("/visibility-windows"))?.payload).toMatchObject({
    role: customRoleCode,
    past_hours: 48,
    future_hours: 48
  });
});

test("surfaces a 409 custom override conflict and leaves the permission unchanged", async ({ page }) => {
  const writes = await installMocks(page, { overrideStatus: 409 });
  await openPermissions(page);
  const toggle = page.getByTestId(`permission-toggle-${customRoleCode}-${permissionCode}`);
  await toggle.click();
  await expect(page.getByRole("alert").filter({ hasText: "cambió mientras editabas" })).toBeVisible();
  await expect(toggle).toBeChecked();
  expect(writes).toHaveLength(1);
  expect(writes[0].payload).toMatchObject({ role: customRoleCode, permission_code: permissionCode, expected_version: 0 });
});

test("surfaces a 403 custom override rejection without applying it", async ({ page }) => {
  const writes = await installMocks(page, { overrideStatus: 403 });
  await openPermissions(page);
  const toggle = page.getByTestId(`permission-toggle-${customRoleCode}-${permissionCode}`);
  await toggle.click();
  await expect(page.getByRole("alert").filter({ hasText: "rechazó el cambio" })).toBeVisible();
  await expect(toggle).toBeChecked();
  expect(writes).toHaveLength(1);
  expect(writes[0].payload).toMatchObject({ role: customRoleCode, permission_code: permissionCode });
});

test("blocks user overrides for protected built-ins and archived custom roles", async ({ page }) => {
  await installMocks(page);
  await openPermissions(page);
  const userPicker = page.getByLabel("Usuario para configurar overrides");
  const userToggle = page.getByTestId(`user-permission-toggle-${permissionCode}`);

  await expect(userPicker).toHaveValue("2");
  await expect(userToggle).toBeDisabled();
  await expect(page.getByRole("status").filter({ hasText: "rol protegido" })).toBeVisible();

  await userPicker.selectOption("3");
  await expect(page.getByRole("status").filter({ hasText: "archivado" })).toBeVisible();
  await expect(userToggle).toBeDisabled();
});

test("explains when a new capability remains denied by an older user override", async ({ page }) => {
  await installMocks(page, { legacyUserDeny: true });
  await openPermissions(page);

  const permissionRow = page
    .getByTestId(`user-permission-toggle-${assistantActionsPermissionCode}`)
    .locator("xpath=ancestor::tr");
  await expect(permissionRow).toContainText("Denegación heredada del usuario");
  await expect(permissionRow).toContainText("settings:assistant:view");
});

test("denies matrix editing when the hotel role catalog fails to load", async ({ page }) => {
  await installMocks(page, { rolesFailure: true });
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.locator('input[type="email"]').fill("owner@example.com");
  await page.locator('input[type="password"]').fill("test-password");
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard");
  await page.goto("/settings/permissions");

  await expect(page.getByTestId("hotel-role-management").getByRole("alert")).toBeVisible();
  await expect(page.getByTestId("permissions-matrix")).toHaveCount(0);
  await expect(page.getByLabel("Nombre del rol")).toBeDisabled();
  await expect(page.getByRole("button", { name: "Crear rol" })).toBeDisabled();
});
