import { expect, test } from "@playwright/test";

test.describe("sitio público", () => {
  test("expone CTA above the fold, caso ilustrativo, FAQ y metadata social", async ({ page }) => {
    const analyticsRequests: string[] = [];
    page.on("request", (request) => {
      if (/google-analytics|googletagmanager|analytics\.google\.com/i.test(request.url())) {
        analyticsRequests.push(request.url());
      }
    });
    await page.goto("/");

    await expect(page.getByRole("link", { name: "Registrarte" }).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: /PMS hotelero para operar tu hotel/i })).toBeVisible();
    await expect(page.getByText("Caso ilustrativo")).toBeVisible();
    await expect(page.getByRole("link", { name: "Preguntas frecuentes" })).toBeVisible();
    await expect(page.locator('meta[property="og:image"]')).toHaveAttribute("content", /social-share\.svg/);
    await expect(page.locator('meta[property="og:image:width"]')).toHaveAttribute("content", "1200");
    await expect(page.locator('meta[property="og:image:height"]')).toHaveAttribute("content", "630");
    expect(await page.locator("img").count()).toBeGreaterThan(0);
    const hasAltText = await page.locator("img").evaluateAll((images) => images.every((image) => Boolean(image.getAttribute("alt")?.trim())));
    expect(hasAltText).toBe(true);
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

  test("mantiene títulos únicos en las rutas públicas indexables y no publica el placeholder legal", async ({ page }) => {
    const routes = ["/", "/precios", "/funciones", "/pms-hotelero", "/software-para-hoteles", "/faq", "/contacto", "/terms", "/privacy"];
    const titles: string[] = [];

    for (const route of routes) {
      await page.goto(route);
      titles.push(await page.title());
    }

    expect(new Set(titles).size).toBe(routes.length);
    await page.goto("/privacy");
    await expect(page.getByText("Domicilio legal pendiente de completar")).toHaveCount(0);
    await expect(page.locator('meta[name="description"]')).toHaveAttribute("content", /datos personales/i);
  });
});
