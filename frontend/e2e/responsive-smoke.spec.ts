import { expect, test, type Page } from "@playwright/test";

const ownerEmail = process.env.E2E_OWNER_EMAIL || "owner@e2e.com";
const ownerPassword = process.env.E2E_OWNER_PASSWORD || "E2ePass1234!";

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(ownerEmail);
  await page.locator('input[type="password"]').fill(ownerPassword);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

test.describe("Responsive mobile smoke", () => {
  test("dashboard fits an iPhone viewport and exposes operational navigation", async ({ page }) => {
    await login(page);

    await expect(page.getByTestId("dashboard-mobile-reservations")).toBeVisible();
    await expect(page.locator('nav[aria-label="Navegación móvil"] a[href="/reservas"]')).toBeVisible();
    await expect(
      page.getByRole("option", {
        name: "Hotel Chipre E2E con un nombre operacionalmente largo (ID 1)",
        exact: true
      })
    ).toBeAttached();

    for (const [width, height] of [[375, 812], [390, 844], [430, 932]]) {
      await test.step(`viewport ${width}x${height}`, async () => {
        await page.setViewportSize({ width, height });
        const layout = await page.evaluate(() => ({
          viewportWidth: window.innerWidth,
          documentScrollWidth: document.documentElement.scrollWidth,
          bodyScrollWidth: document.body.scrollWidth
        }));

        expect(layout.viewportWidth).toBe(width);
        expect(layout.documentScrollWidth).toBeLessThanOrEqual(layout.viewportWidth);
        expect(layout.bodyScrollWidth).toBeLessThanOrEqual(layout.viewportWidth);
      });
    }
  });

  test("mobile navigation reaches reservations", async ({ page }) => {
    await login(page);

    const reservationsLink = page.locator('nav[aria-label="Navegación móvil"] a[href="/reservas"]');
    await reservationsLink.click();
    await expect(page).toHaveURL(/\/reservas$/);
    await expect(page.locator("main").getByRole("heading", { name: "Reservas", exact: true })).toBeVisible();
  });

  test("critical mobile controls provide 44px touch targets", async ({ page }) => {
    await login(page);
    await page.setViewportSize({ width: 375, height: 812 });

    const mobileNavigationTargets = await page.locator('nav[aria-label="Navegación móvil"] a').evaluateAll((nodes) =>
      nodes
        .map((node) => {
          const element = node as HTMLElement;
          const rect = element.getBoundingClientRect();
          const style = window.getComputedStyle(element);
          return {
            label: node.textContent?.trim() || "",
            height: Math.round(rect.height),
            width: Math.round(rect.width),
            // A nav item can legitimately unmount between query and
            // measurement (e.g. the Onboarding link disappears once
            // onboarding completes), leaving a detached node whose rect is
            // always 0x0. That is not a real undersized touch target.
            connected: element.isConnected && style.display !== "none" && style.visibility !== "hidden"
          };
        })
        .filter((target) => target.connected)
    );
    expect(
      mobileNavigationTargets.filter((target) => target.height < 44 || target.width < 44),
      "mobile navigation has undersized touch targets"
    ).toEqual([]);

    for (const path of ["/reservas", "/caja", "/operacion/stock", "/reportes", "/operacion/lavanderia", "/habitaciones"]) {
      await page.goto(path);
      const targets = await page.evaluate(() => {
        const nodes = Array.from(
          document.querySelectorAll(
            "main button, main input:not([type='checkbox']):not([type='radio']), main select, main textarea, header button, header select, [role='banner'] button, [role='banner'] select"
          )
        );
        return nodes
          .map((node) => {
            const element = node as HTMLElement;
            const rect = element.getBoundingClientRect();
            const style = window.getComputedStyle(element);
            return {
              tag: element.tagName,
              label: element.getAttribute("aria-label") || element.textContent?.trim().slice(0, 50) || "",
              height: Math.round(rect.height),
              visible: rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none"
            };
          })
          .filter((target) => target.visible);
      });

      expect(targets.filter((target) => target.height < 44), `${path} has undersized touch targets`).toEqual([]);
    }
  });

  test("cash close approval checkbox has a 44px touch target", async ({ page }) => {
    await login(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/caja");

    const openCashButton = page.getByRole("button", { name: "Abrir caja", exact: true });
    const existingOpenCashButton = page.getByRole("button", { name: "Ya hay una caja abierta", exact: true });
    if (await openCashButton.isVisible()) {
      await openCashButton.click();
      await expect(page.getByText("Caja abierta.", { exact: true })).toBeVisible();
    } else {
      await expect(existingOpenCashButton).toBeVisible();
    }

    const approvalCheckbox = page.locator("form").filter({ hasText: "Cerrar caja" }).locator('input[type="checkbox"]');
    await expect(approvalCheckbox).toBeVisible();
    const box = await approvalCheckbox.boundingBox();

    expect(box?.width).toBeGreaterThanOrEqual(44);
    expect(box?.height).toBeGreaterThanOrEqual(44);
  });

  test("critical operational pages have no horizontal overflow", async ({ page }) => {
    await login(page);
    await page.setViewportSize({ width: 390, height: 844 });

    for (const path of ["/reservas", "/caja", "/operacion/stock", "/reportes", "/operacion/lavanderia", "/habitaciones"]) {
      await page.goto(path);
      const layout = await page.evaluate(() => ({
        viewportWidth: window.innerWidth,
        documentScrollWidth: document.documentElement.scrollWidth,
        bodyScrollWidth: document.body.scrollWidth
      }));

      expect(layout.documentScrollWidth, `${path} has document horizontal overflow`).toBeLessThanOrEqual(layout.viewportWidth);
      expect(layout.bodyScrollWidth, `${path} has body horizontal overflow`).toBeLessThanOrEqual(layout.viewportWidth);
    }
  });
});
