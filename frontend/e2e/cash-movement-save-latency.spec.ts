import { expect, test, type Page } from "@playwright/test";

const receptionistCredentials = {
  email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
  password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!"
};

const isMovementListUrl = (url: string) =>
  /^\/api\/cash-register\/sessions\/\d+\/movements$/.test(new URL(url).pathname);

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(receptionistCredentials.email);
  await page.locator('input[type="password"]').fill(receptionistCredentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("cash movement save finishes while its active list refresh is delayed", async ({ page }) => {
  let delayNextMovementListRead = false;
  let movementListReadIsHeld = false;
  let releaseMovementListRead = () => undefined;
  const movementListReadGate = new Promise<void>((resolve) => {
    releaseMovementListRead = resolve;
  });

  await page.route("**/api/cash-register/sessions/*/movements", async (route) => {
    const request = route.request();
    if (request.method() === "POST") {
      // Let the local API commit the movement, then arm the one read that the
      // successful mutation triggers. This keeps the test about UI wait time,
      // not about a slow write or a mocked write response.
      const response = await route.fetch();
      delayNextMovementListRead = true;
      await route.fulfill({ response });
      return;
    }

    if (request.method() === "GET" && delayNextMovementListRead) {
      delayNextMovementListRead = false;
      const response = await route.fetch();
      movementListReadIsHeld = true;
      await movementListReadGate;
      await route.fulfill({ response });
      return;
    }

    await route.continue();
  });

  await login(page);
  const sessionsResponse = page.waitForResponse((response) =>
    response.request().method() === "GET" && new URL(response.url()).pathname === "/api/cash-register/sessions"
  );
  const initialMovementListResponse = page.waitForResponse((response) =>
    response.request().method() === "GET" && isMovementListUrl(response.url())
  );
  await page.goto("/caja");
  await sessionsResponse;

  const openButton = page.getByRole("button", { name: "Abrir caja", exact: true });
  if (await openButton.isVisible().catch(() => false)) {
    const openingForm = page.locator("form").filter({ hasText: "Saldo inicial" }).filter({ hasText: "Abrir caja" });
    await openingForm.getByText("Saldo inicial", { exact: true }).locator("..").locator("input").fill("0");
    await openButton.click();
    await expect(page.getByText("Caja abierta.", { exact: true })).toBeVisible();
  } else {
    await expect(page.getByRole("button", { name: "Ya hay una caja abierta", exact: true })).toBeVisible();
  }
  await initialMovementListResponse;

  const description = `E2E cash save latency ${Date.now()}`;
  const movementForm = page.locator("form").filter({ hasText: "Registrar movimiento" });
  await movementForm.getByLabel("Tipo").selectOption("income");
  await movementForm.getByLabel("Importe").fill("1");
  await movementForm.getByLabel("Descripción").fill(description);

  try {
    await movementForm.getByRole("button", { name: "Registrar movimiento", exact: true }).click();
    await expect.poll(() => movementListReadIsHeld, { timeout: 15_000 }).toBe(true);

    // The write response has completed and the follow-up list response is
    // intentionally still held. The operator should already receive success
    // feedback and a cleared form at this point.
    await expect(page.getByText("Movimiento registrado.", { exact: true })).toBeVisible();
    await expect(movementForm.getByLabel("Importe")).toHaveValue("");
    await expect(movementForm.getByLabel("Descripción")).toHaveValue("");
    await expect(page.getByText(description, { exact: false })).not.toBeVisible();
  } finally {
    releaseMovementListRead();
  }

  await expect(page.getByText(description, { exact: false })).toBeVisible();
});
