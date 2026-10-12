import { expect, test, type Page } from "@playwright/test";

const credentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};
const realtimeE2EEnabled = process.env.REALTIME_E2E === "true";

const localIsoDate = (offsetDays: number) => {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
};

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("reservation create confirms the committed write while list refresh is delayed", async ({ page }) => {
  let delayNextReservationListRead = false;
  let reservationListReadIsHeld = false;
  let writeCommittedAt: number | null = null;
  let mutationOriginKey: string | undefined;
  let releaseReservationListRead = () => undefined;
  const reservationListReadGate = new Promise<void>((resolve) => {
    releaseReservationListRead = resolve;
  });
  const postCommitGetCounts = new Map<string, number>();

  const realtimeReady = realtimeE2EEnabled
    ? page.waitForResponse((response) => {
        const url = new URL(response.url());
        return url.pathname === "/api/events/stream" && response.status() === 200;
      })
    : null;

  page.on("request", (request) => {
    if (writeCommittedAt === null || request.method() !== "GET") return;
    const pathname = new URL(request.url()).pathname;
    // SSE is one long-lived request; count ordinary reads that it can trigger.
    if (pathname === "/api/events/stream") return;
    postCommitGetCounts.set(pathname, (postCommitGetCounts.get(pathname) ?? 0) + 1);
  });

  await page.route("**/api/reservations/**", async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    if (request.method() === "POST" && pathname === "/api/reservations/") {
      mutationOriginKey = request.headers()["x-domain-event-origin"];
      const response = await route.fetch();
      writeCommittedAt = Date.now();
      delayNextReservationListRead = true;
      await route.fulfill({ response });
      return;
    }

    if (request.method() === "GET" && pathname === "/api/reservations/" && delayNextReservationListRead) {
      delayNextReservationListRead = false;
      const response = await route.fetch();
      reservationListReadIsHeld = true;
      await reservationListReadGate;
      await route.fulfill({ response });
      return;
    }

    await route.continue();
  });

  await login(page);
  if (realtimeReady) await realtimeReady;
  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();

  const form = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await expect(form).toBeVisible();
  await form.getByRole("button", { name: "¿No lo encontrás? Crear huésped nuevo", exact: true }).click();
  await form.getByPlaceholder("Nombre").fill("Huésped");
  await form.getByPlaceholder("Apellido").fill(`Save Latency ${Date.now()}`);
  await form.getByPlaceholder("Email").fill(`save-latency-${Date.now()}@example.test`);
  await form.getByPlaceholder("Teléfono").fill(`11${Date.now().toString().slice(-8)}12`);
  await form.getByLabel("Tipo de documento").selectOption("DNI");
  await form.getByPlaceholder("Documento").fill(`SAVE-LATENCY-${Date.now()}`);
  await form.getByRole("button", { name: "Crear Huésped y asignar ID", exact: true }).click();
  await expect(page.getByText("Huésped creado y asignado", { exact: true })).toBeVisible();
  // Let the guest-created event and its refetch settle before measuring the
  // reservation write, so only reads caused by that write are counted.
  if (realtimeE2EEnabled) await page.waitForTimeout(6_500);

  const categorySelect = form.locator("label").filter({ hasText: "Categoría" }).locator("select");
  const categoryOption = categorySelect.locator("option").filter({ hasText: "Standard E2E" });
  await expect(categoryOption).toHaveCount(1);
  await categorySelect.selectOption((await categoryOption.getAttribute("value"))!);
  await form.getByLabel("Check-in", { exact: true }).fill(localIsoDate(60));
  await form.getByLabel("Check-out", { exact: true }).fill(localIsoDate(62));
  await expect(form.getByRole("button", { name: "Crear", exact: true })).toBeEnabled();

  try {
    await form.getByRole("button", { name: "Crear", exact: true }).click();
    await expect.poll(() => reservationListReadIsHeld, { timeout: 15_000 }).toBe(true);

    // The POST reached and committed in the local API. An intentionally held
    // list refetch must not delay the success message or closing the form.
    await expect(page.getByText("Reserva creada", { exact: true })).toBeVisible();
    await expect(form).not.toBeVisible();
  } finally {
    releaseReservationListRead();
  }

  if (realtimeE2EEnabled) {
    // The PostgreSQL fallback polls at most every five seconds, then the client
    // coalesces the event for one second. Wait through that complete window.
    await page.waitForTimeout(6_500);
  }
  console.log(`post-commit GET counts: ${JSON.stringify(Object.fromEntries(postCommitGetCounts))}`);
  expect(mutationOriginKey).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
  expect(postCommitGetCounts.get("/api/reservations/") ?? 0).toBe(1);
  expect(postCommitGetCounts.get("/api/reservations/actions/pending") ?? 0).toBe(1);
  expect(postCommitGetCounts.get("/api/notifications") ?? 0).toBe(0);
});
