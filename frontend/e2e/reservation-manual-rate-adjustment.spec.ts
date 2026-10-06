import { expect, test, type Page } from "@playwright/test";

const manager = {
  email: process.env.E2E_MANAGER_EMAIL || "manager@e2e.com",
  password: process.env.E2E_MANAGER_PASSWORD || "E2eManager1234!"
};
const owner = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

const ids = {
  directUnpaid: 870001,
  directPaid: 870002,
  ota: 870003,
  group: 870004
} as const;

const futureDate = (daysAhead: number) => {
  const date = new Date();
  date.setDate(date.getDate() + daysAhead);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
};

const fixtures = [
  {
    id: ids.directUnpaid,
    confirmation_code: "QA-RATE-DIRECT",
    guest_id: 870001,
    guest: { id: 870001, first_name: "Huésped", last_name: "Directo QA" },
    room_id: null,
    category_id: 1,
    category_name: "Standard QA",
    company_id: null,
    group_id: null,
    check_in_date: futureDate(30),
    check_out_date: futureDate(32),
    total_amount: 100,
    amount_paid: 0,
    deposit_amount: 0,
    status: "pending",
    source: "direct",
    external_id: null,
    source_provider_code: null,
    num_adults: 1,
    num_children: 0,
    currency_code: "ARS",
    allocation_status: "assigned",
    version: 1
  },
  {
    id: ids.directPaid,
    confirmation_code: "QA-RATE-PAID",
    guest_id: 870002,
    guest: { id: 870002, first_name: "Huésped", last_name: "Pagado QA" },
    room_id: null,
    category_id: 1,
    category_name: "Standard QA",
    company_id: null,
    group_id: null,
    check_in_date: futureDate(33),
    check_out_date: futureDate(35),
    total_amount: 100,
    amount_paid: 20,
    deposit_amount: 20,
    status: "deposit_paid",
    source: "direct",
    external_id: null,
    source_provider_code: null,
    num_adults: 1,
    num_children: 0,
    currency_code: "ARS",
    allocation_status: "assigned",
    version: 1
  },
  {
    id: ids.ota,
    confirmation_code: "QA-RATE-OTA",
    guest_id: 870003,
    guest: { id: 870003, first_name: "Huésped", last_name: "OTA QA" },
    room_id: null,
    category_id: 1,
    category_name: "Standard QA",
    company_id: null,
    group_id: null,
    check_in_date: futureDate(36),
    check_out_date: futureDate(38),
    total_amount: 100,
    amount_paid: 0,
    deposit_amount: 0,
    status: "pending",
    source: "booking",
    external_id: "QA-OTA-EXTERNAL-ID",
    source_provider_code: "booking_com",
    num_adults: 1,
    num_children: 0,
    currency_code: "ARS",
    allocation_status: "assigned",
    version: 1
  },
  {
    id: ids.group,
    confirmation_code: "QA-RATE-GROUP",
    guest_id: 870004,
    guest: { id: 870004, first_name: "Huésped", last_name: "Grupo QA" },
    room_id: null,
    category_id: 1,
    category_name: "Standard QA",
    company_id: null,
    group_id: 870099,
    check_in_date: futureDate(39),
    check_out_date: futureDate(41),
    total_amount: 100,
    amount_paid: 0,
    deposit_amount: 0,
    status: "pending",
    source: "direct",
    external_id: null,
    source_provider_code: null,
    num_adults: 1,
    num_children: 0,
    currency_code: "ARS",
    allocation_status: "assigned",
    version: 1
  }
] as const;

const transactionsByReservation: Record<number, Array<Record<string, unknown>>> = {
  [ids.directUnpaid]: [],
  [ids.directPaid]: [
    {
      id: 870201,
      amount: 20,
      currency: "ARS",
      method: "cash",
      type: "deposit",
      status: "completed",
      created_at: "2026-10-05T12:00:00Z"
    }
  ],
  [ids.ota]: [],
  [ids.group]: []
};

async function login(page: Page, credentials: { email: string; password: string }) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

async function installReservationMocks(page: Page) {
  const patchRequests: Array<{ id: number; payload: Record<string, unknown> }> = [];
  const paymentWrites: string[] = [];
  const paymentSummaryReads: Array<{ id: number; transactionIds: number[] }> = [];

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();

    if (pathname === "/api/reservations/" && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(fixtures)
      });
    }

    const reservationMatch = pathname.match(/^\/api\/reservations\/(\d+)$/);
    if (reservationMatch && method === "PATCH") {
      const id = Number(reservationMatch[1]);
      const payload = JSON.parse(request.postData() || "{}") as Record<string, unknown>;
      patchRequests.push({ id, payload });

      if (typeof payload.paid_total_change_reason !== "string" || !payload.paid_total_change_reason.trim()) {
        return route.fulfill({
          status: 422,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Escribí el motivo para corregir el total de la reserva." })
        });
      }

      const total = Number(payload.total_amount);
      if (id === ids.directUnpaid && (total < 90 || total > 120)) {
        return route.fulfill({
          status: 422,
          contentType: "application/json",
          body: JSON.stringify({ detail: "El total debe estar entre ARS 90 y ARS 120 según los límites configurados." })
        });
      }

      const reservation = fixtures.find((item) => item.id === id);
      if (!reservation) {
        return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Reserva inexistente" }) });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...reservation, total_amount: total, version: reservation.version + 1 })
      });
    }

    const paymentSummaryMatch = pathname.match(/^\/api\/payments\/summary\/(\d+)$/);
    if (paymentSummaryMatch && method === "GET") {
      const id = Number(paymentSummaryMatch[1]);
      const reservation = fixtures.find((item) => item.id === id);
      const transactions = transactionsByReservation[id] ?? [];
      paymentSummaryReads.push({
        id,
        transactionIds: transactions.map((transaction) => Number(transaction.id))
      });
      const amountPaid = Number(reservation?.amount_paid ?? 0);
      const totalAmount = Number(reservation?.total_amount ?? 0);
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          reservation_id: id,
          confirmation_code: reservation?.confirmation_code,
          status: reservation?.status,
          currency_code: "ARS",
          total_amount: totalAmount,
          deposit_required: Number(reservation?.deposit_amount ?? 0),
          amount_paid: amountPaid,
          balance_due: totalAmount - amountPaid,
          operational_total_amount: totalAmount,
          operational_balance_due: totalAmount - amountPaid,
          company_billing_deferred: false,
          completed_payments: amountPaid,
          transactions,
          billing_adjustments: []
        })
      });
    }

    if ((pathname === "/api/payments" || pathname.startsWith("/api/payments/")) && method !== "GET" && method !== "HEAD") {
      paymentWrites.push(`${method} ${pathname}`);
      return route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "E2E bloqueó una mutación de pagos no esperada." })
      });
    }

    return route.continue();
  });

  return { patchRequests, paymentWrites, paymentSummaryReads };
}

const rowFor = (page: Page, confirmationCode: string) =>
  page.locator("table tbody tr").filter({ hasText: confirmationCode });

const editForm = (page: Page) =>
  page.locator("form").filter({ hasText: "Datos de la reserva" }).last();

test("bounded manager adjusts only a direct unpaid reservation within the configured range and with a reason", async ({ page }) => {
  await login(page, manager);
  const { patchRequests, paymentWrites } = await installReservationMocks(page);
  await page.goto("/reservas");

  const directRow = rowFor(page, "QA-RATE-DIRECT");
  await expect(directRow).toHaveCount(1);
  await directRow.getByRole("button", { name: "Editar", exact: true }).click();

  let form = editForm(page);
  const adjustment = form.getByTestId("reservation-total-adjustment");
  await expect(adjustment).toBeVisible();
  await expect(adjustment).toContainText("rango de tarifa manual configurado por el owner");

  const amount = adjustment.getByTestId("reservation-total-adjustment-amount");
  const reason = adjustment.getByTestId("reservation-total-adjustment-reason");
  await amount.fill("110");
  await form.getByRole("button", { name: "Guardar cambios", exact: true }).click();
  await expect(form.getByTestId("reservation-submit-error")).toContainText("Escribí el motivo");
  expect(patchRequests).toHaveLength(0);

  await reason.fill("Corrección de tarifa acordada con el huésped");
  const allowedUpdate = page.waitForResponse((response) =>
    new URL(response.url()).pathname === `/api/reservations/${ids.directUnpaid}` &&
      response.request().method() === "PATCH"
  );
  await form.getByRole("button", { name: "Guardar cambios", exact: true }).click();
  expect((await allowedUpdate).status()).toBe(200);
  await expect(page.getByText("Reserva actualizada", { exact: true })).toBeVisible();
  expect(patchRequests[0]).toEqual({
    id: ids.directUnpaid,
    payload: expect.objectContaining({
      total_amount: 110,
      paid_total_change_reason: "Corrección de tarifa acordada con el huésped"
    })
  });
  expect(paymentWrites).toHaveLength(0);

  await rowFor(page, "QA-RATE-DIRECT").getByRole("button", { name: "Editar", exact: true }).click();
  form = editForm(page);
  await form.getByTestId("reservation-total-adjustment-amount").fill("140");
  await form.getByTestId("reservation-total-adjustment-reason").fill("Importe fuera de los límites del hotel");
  const rejectedUpdate = page.waitForResponse((response) =>
    new URL(response.url()).pathname === `/api/reservations/${ids.directUnpaid}` &&
      response.request().method() === "PATCH"
  );
  await form.getByRole("button", { name: "Guardar cambios", exact: true }).click();
  expect((await rejectedUpdate).status()).toBe(422);
  await expect(form.getByTestId("reservation-submit-error")).toContainText("debe estar entre ARS 90 y ARS 120");

  await form.getByRole("button", { name: "Cancelar", exact: true }).click();
  const paidRow = rowFor(page, "QA-RATE-PAID");
  await paidRow.getByRole("button", { name: "Editar", exact: true }).click();
  form = editForm(page);
  await expect(form.getByTestId("reservation-total-adjustment")).toHaveCount(0);
  await form.getByRole("button", { name: "Cancelar", exact: true }).click();

  for (const code of ["QA-RATE-OTA", "QA-RATE-GROUP"]) {
    const row = rowFor(page, code);
    await expect(row).toHaveCount(1);
    await row.getByRole("button", { name: "Editar", exact: true }).click();
    form = editForm(page);
    await expect(form.getByTestId("reservation-total-adjustment")).toHaveCount(0);
    await form.getByRole("button", { name: "Cancelar", exact: true }).click();
  }
  expect(patchRequests.map((request) => request.payload.total_amount)).toEqual([110, 140]);
  expect(paymentWrites).toHaveLength(0);
});

test("paid total correction requires the paid adjustment permission and reason without mutating transactions", async ({ page }) => {
  await login(page, owner);
  const { patchRequests, paymentWrites, paymentSummaryReads } = await installReservationMocks(page);
  await page.goto("/reservas");

  const paidRow = rowFor(page, "QA-RATE-PAID");
  await expect(paidRow).toHaveCount(1);
  await paidRow.getByRole("button", { name: "Editar", exact: true }).click();

  const form = editForm(page);
  const adjustment = form.getByTestId("reservation-total-adjustment");
  await expect(adjustment).toBeVisible();
  await expect(adjustment).toContainText("La corrección cambia el saldo y deja intactos los cobros y devoluciones registrados");
  await adjustment.getByTestId("reservation-total-adjustment-amount").fill("115");
  await adjustment.getByTestId("reservation-total-adjustment-reason").fill("Corrección contable sin cambiar el cobro recibido");

  const paidUpdate = page.waitForResponse((response) =>
    new URL(response.url()).pathname === `/api/reservations/${ids.directPaid}` &&
      response.request().method() === "PATCH"
  );
  await form.getByRole("button", { name: "Guardar cambios", exact: true }).click();
  expect((await paidUpdate).status()).toBe(200);
  await expect(page.getByText("Reserva actualizada", { exact: true })).toBeVisible();

  expect(patchRequests).toHaveLength(1);
  expect(patchRequests[0]).toEqual({
    id: ids.directPaid,
    payload: expect.objectContaining({
      total_amount: 115,
      paid_total_change_reason: "Corrección contable sin cambiar el cobro recibido"
    })
  });
  expect(paymentWrites).toHaveLength(0);
  expect(paymentSummaryReads.filter((read) => read.id === ids.directPaid).length).toBeGreaterThan(0);
  expect(paymentSummaryReads.filter((read) => read.id === ids.directPaid).every((read) => read.transactionIds.join(",") === "870201")).toBe(true);
});
