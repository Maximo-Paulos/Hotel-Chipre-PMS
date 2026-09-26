import { expect, test } from "@playwright/test";
import { hero } from "../src/content/marketing";

test.describe("sitio público", () => {
  test("expone el posicionamiento actual, FAQ y metadata social sin analytics", async ({ page }) => {
    const analyticsRequests: string[] = [];
    page.on("request", (request) => {
      if (/google-analytics|googletagmanager|analytics\.google\.com/i.test(request.url())) {
        analyticsRequests.push(request.url());
      }
    });
    await page.goto("/");

    await expect(page.getByRole("heading", { name: hero.title })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Lo que todo el mundo pregunta antes de decidir." })).toBeVisible();
    await expect(page.getByRole("link", { name: "Contacto", exact: true }).first()).toBeVisible();
    await expect(page.locator('meta[property="og:image"]')).toHaveAttribute("content", /og-default\.png/);
    await expect(page.locator('meta[property="og:image:width"]')).toHaveAttribute("content", "1200");
    await expect(page.locator('meta[property="og:image:height"]')).toHaveAttribute("content", "630");
    expect(analyticsRequests).toEqual([]);
  });

  test("muestra 404 visual y noindex sin redirigir al inicio", async ({ page }) => {
    await page.goto("/ruta-que-no-existe");

    await expect(page.getByRole("heading", { name: "Esta página no está disponible" })).toBeVisible();
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", "noindex, nofollow");
    await expect(page).toHaveURL(/\/ruta-que-no-existe$/);
  });

  test("muestra breadcrumbs y CTA móvil, y lleva una consulta aceptada a gracias", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/api/public/inquiries", async (route) => {
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ status: "accepted" }) });
    });
    await page.goto("/contacto");

    await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Hablar con el equipo" })).toBeVisible();
    await page.getByLabel("Nombre *").fill("Ana Pérez");
    await page.getByLabel("Email *").fill("ana@example.com");
    await page.getByLabel("Mensaje *").fill("Quiero conocer el sistema para mi hotel.");
    await page.getByLabel(/Acepto la Política de Privacidad/).check();
    await page.getByRole("button", { name: "Enviar consulta" }).click();

    await expect(page).toHaveURL(/\/gracias$/);
    await expect(page.getByRole("heading", { name: "Gracias por escribirnos" })).toBeVisible();
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", "noindex, nofollow");
  });

  test("acepta una invitación con contraseña existente y MFA ligado al enlace", async ({ page }) => {
    const requests: Array<{ path: string; body: Record<string, unknown> }> = [];
    const token = "synthetic-invitation-capability";
    await page.route("**/api/auth/providers", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ google: { enabled: false, client_id: null, self_signup_enabled: false, allowed_domains: [] } })
      });
    });
    await page.route("**/api/invitations/preview", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ email: "mfa-invitee@example.test", hotel_name: "Hotel de prueba" })
      });
    });
    await page.route("**/api/invitations/accept", async (route) => {
      requests.push({ path: "/api/invitations/accept", body: route.request().postDataJSON() });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ requires_mfa: true, mfa_token: "synthetic-invitation-mfa", expires_in: 300 })
      });
    });
    await page.route("**/api/invitations/accept/mfa", async (route) => {
      requests.push({ path: "/api/invitations/accept/mfa", body: route.request().postDataJSON() });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: "synthetic-access-token",
          token_type: "bearer",
          hotel_id: 12,
          hotel_ids: [12],
          permissions: [],
          user: {
            id: 50,
            email: "mfa-invitee@example.test",
            role: "manager",
            is_verified: true,
            is_active: true,
            password_login_enabled: true,
            permissions: []
          }
        })
      });
    });

    await page.goto(`/invitations/accept#token=${encodeURIComponent(token)}`);
    await page.getByPlaceholder("Tu contraseña actual").fill("legacy-password");
    await page.getByRole("button", { name: "Verificar y aceptar" }).click();
    await expect(page.getByLabel("Código de la app autenticadora o de recuperación")).toBeVisible();
    await page.getByLabel("Código de la app autenticadora o de recuperación").fill("123456");
    await page.getByRole("button", { name: "Verificar y aceptar invitación" }).click();

    await expect(page).toHaveURL(/\/dashboard$/);
    expect(requests).toEqual([
      {
        path: "/api/invitations/accept",
        body: { token, email: "mfa-invitee@example.test", current_password: "legacy-password" }
      },
      {
        path: "/api/invitations/accept/mfa",
        body: { token, mfa_token: "synthetic-invitation-mfa", code: "123456" }
      }
    ]);
  });

  test("mantiene títulos únicos en las rutas públicas indexables y no publica el placeholder legal", async ({ page }) => {
    const routes = [
      ["/", "Hotels-PMS | El sistema de gestión que unifica todo el hotel"],
      ["/precios", "Precios | Hotels-PMS"],
      ["/funciones", "El sistema | Hotels-PMS"],
      ["/pms-hotelero", "PMS hotelero | Hotels-PMS"],
      ["/software-para-hoteles", "Software para hoteles | Hotels-PMS"],
      ["/faq", "FAQ | Hotels-PMS"],
      ["/contacto", "Contacto | Consultas sobre Hotels-PMS"],
      ["/terms", "Términos y Condiciones | Hotels-PMS"],
      ["/privacy", "Política de Privacidad | Hotels-PMS"]
    ];
    const titles: string[] = [];

    for (const [route, expectedTitle] of routes) {
      await page.goto(route);
      await expect(page).toHaveTitle(expectedTitle);
      titles.push(expectedTitle);
    }

    expect(new Set(titles).size).toBe(routes.length);
    await page.goto("/privacy");
    await expect(page.getByText("Domicilio legal pendiente de completar")).toHaveCount(0);
    await expect(page.locator('meta[name="description"]')).toHaveAttribute("content", /datos personales/i);
  });
});
