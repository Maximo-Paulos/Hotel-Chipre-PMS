import { expect, test } from "@playwright/test";

test.use({ screenshot: "off", video: "off", trace: "off" });

const receptionist = {
  email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
  password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!"
};

test("F-027: reception can open quick reservation from the reservations page", async ({ page }) => {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(receptionist.email);
  await page.locator('input[type="password"]').fill(receptionist.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard");
  await expect(page.getByTestId("session-role")).toHaveText("Recepción");
  const quickReservation = page.getByRole("link", { name: "Reserva rápida", exact: true });
  const reservationForm = page.locator("form").filter({ hasText: "Datos de la reserva" });

  await page.goto("/dashboard");
  await expect(quickReservation).toBeVisible();
  await quickReservation.click();
  await expect(reservationForm).toBeVisible({ timeout: 3_000 });
  await expect(page).toHaveURL(/\/reservas$/);

  await page.goto("/reservas");
  await expect(reservationForm).toHaveCount(0);
  await quickReservation.click();
  await expect(reservationForm).toBeVisible({ timeout: 3_000 });
});

const localIsoDate = (offsetDays: number) => {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
};

const displayDate = (isoDate: string) => `${isoDate.slice(8, 10)}/${isoDate.slice(5, 7)}/${isoDate.slice(0, 4)}`;

for (const browserLocale of ["es-AR", "en-US"] as const) {
  test.describe(`F-027 interface language with ${browserLocale} browser locale`, () => {
    test.use({ locale: browserLocale });

    for (const locale of ["es", "en"] as const) {
      test(`F-027: unavailable room error follows the ${locale} interface language`, async ({ page }) => {
    const category = "Standard E2E";
    const expectedMessage = locale === "es"
      ? `No hay habitaciones disponibles en la categoría ${category} para las fechas seleccionadas.`
      : `No rooms are available in ${category} for the selected dates.`;
    let reservationPostIntercepted = false;
    let reservationPostPayload: Record<string, unknown> | null = null;

    await page.route("**/api/config/interface-language", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ interface_language: locale })
      })
    );
    await page.route(/\/api\/bookings\/price-quote\?/, async (route) => {
      const url = new URL(route.request().url());
      const checkInDate = url.searchParams.get("check_in_date") ?? "2026-10-30";
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "ok",
          category_id: Number(url.searchParams.get("category_id")) || 1,
          check_in_date: checkInDate,
          check_out_date: url.searchParams.get("check_out_date") ?? "2026-11-01",
          nights: 2,
          nightly_rate: 100000,
          subtotal_amount: 200000,
          tax_amount: 0,
          fee_amount: 0,
          commission_amount: 0,
          net_amount: 200000,
          total_amount: 200000,
          deposit_amount: 60000,
          currency_code: "ARS",
          pricing_payment_method: null,
          quote_token: "synthetic-e2e-quote-token",
          expires_at: "2026-10-01T12:00:00Z",
          breakdown: [{ date: checkInDate, price: 100000, base_price: 100000, source: "category_base", promotions_applied: [] }],
          promotions_applied: []
        })
      });
    });
    await page.route(/\/api\/reservations\/?$/, async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      reservationPostIntercepted = true;
      reservationPostPayload = route.request().postDataJSON() as Record<string, unknown>;
      return route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ detail: `No rooms available in category ${category} for the requested dates` })
      });
    });

    await page.goto("/login");
    await page.locator('input[type="email"]').fill(receptionist.email);
    await page.locator('input[type="password"]').fill(receptionist.password);
    await page.getByTestId("login-submit").click();
    await page.waitForURL("**/dashboard");
    await page.goto("/reservas");

    const main = page.locator("main");
    await expect(main.getByRole("heading", { name: locale === "es" ? "Reservas" : "Reservations", exact: true })).toBeVisible();
    await main.getByRole("button", { name: /^(crear reserva|create reservation)$/i }).click();
    const form = page.locator("form").filter({ hasText: /Datos de la reserva|Reservation details/ });
    await form.getByTestId("guest-search-input").fill("Huesped");
    const guestResult = form.getByTestId("guest-search-results").getByRole("button").filter({ hasText: "Huesped E2E" });
    await expect(guestResult).toBeVisible();
    await guestResult.click();
    await form.getByLabel(/Categoría|Category/i).selectOption({ label: category });
    const checkIn = form.getByLabel("Check-in", { exact: true });
    const checkOut = form.getByLabel("Check-out", { exact: true });
    const checkInIso = localIsoDate(30);
    const checkOutIso = localIsoDate(32);
    await expect(checkIn).toHaveAttribute("placeholder", locale === "es" ? "DD/MM/AAAA" : "DD/MM/YYYY");
    await checkIn.fill(checkInIso);
    await checkOut.fill(checkOutIso);
    await expect(checkIn).toHaveValue(displayDate(checkInIso));
    await expect(checkOut).toHaveValue(displayDate(checkOutIso));
    await expect(form.getByText(locale === "es" ? "Tarifa base de la categoría" : "Category base rate", { exact: true })).toBeVisible();

    const submit = form.getByRole("button", { name: /^(crear|create)$/i });
    await expect(submit).toBeEnabled();
    await submit.click();
    await expect.poll(() => reservationPostIntercepted).toBe(true);
    expect(reservationPostPayload?.check_in_date).toBe(checkInIso);
    expect(reservationPostPayload?.check_out_date).toBe(checkOutIso);
    const error = form.getByTestId("reservation-submit-error");
    await expect(error).toBeVisible();
    await expect(error).toHaveText(expectedMessage);
    await expect(error).not.toContainText("No rooms available in category");
      });
    }
  });
}

test.describe("F-027 reservation creation in English with an English browser locale", () => {
  test.use({ locale: "en-US" });

  test("reception completes quick reservation with day-first dates and an ISO API payload", async ({ page }) => {
    const category = "Standard E2E";
    let reservationPayload: Record<string, unknown> | null = null;
    const checkInIso = localIsoDate(30);
    const checkOutIso = localIsoDate(32);
    const createdReservation = {
      id: 9003,
      confirmation_code: "F027-EN-CREATED",
      guest_id: 1,
      guest: { id: 1, first_name: "Huesped", last_name: "E2E" },
      room_id: null,
      category_id: 1,
      category_name: category,
      check_in_date: checkInIso,
      check_out_date: checkOutIso,
      total_amount: 200000,
      amount_paid: 0,
      deposit_amount: 60000,
      status: "pending",
      source: "direct",
      num_adults: 1,
      num_children: 0,
      currency_code: "ARS",
      allocation_status: "unassigned",
      version: 1
    };

    await page.route("**/api/config/interface-language", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ interface_language: "en" })
      })
    );
    await page.route(/\/api\/bookings\/price-quote\?/, async (route) => {
      const url = new URL(route.request().url());
      const checkInDate = url.searchParams.get("check_in_date") ?? checkInIso;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "ok",
          category_id: Number(url.searchParams.get("category_id")) || 1,
          check_in_date: checkInDate,
          check_out_date: url.searchParams.get("check_out_date") ?? checkOutIso,
          nights: 2,
          nightly_rate: 100000,
          subtotal_amount: 200000,
          tax_amount: 0,
          fee_amount: 0,
          commission_amount: 0,
          net_amount: 200000,
          total_amount: 200000,
          deposit_amount: 60000,
          currency_code: "ARS",
          pricing_payment_method: null,
          quote_token: "synthetic-f027-en-quote",
          expires_at: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
          breakdown: [{ date: checkInDate, price: 100000, base_price: 100000, source: "category_base", promotions_applied: [] }],
          promotions_applied: []
        })
      });
    });
    await page.route(/\/api\/reservations\/?$/, async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      reservationPayload = route.request().postDataJSON() as Record<string, unknown>;
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(createdReservation)
      });
    });

    await page.goto("/login");
    await page.locator('input[type="email"]').fill(receptionist.email);
    await page.locator('input[type="password"]').fill(receptionist.password);
    await page.getByTestId("login-submit").click();
    await page.waitForURL("**/dashboard");
    const quickReservation = page.getByRole("link", { name: "Quick reservation", exact: true });
    await expect(quickReservation).toBeVisible();
    await quickReservation.click();
    await expect(page).toHaveURL(/\/reservas$/);
    const form = page.locator("form").filter({ hasText: "Reservation details" });
    await expect(form).toBeVisible();
    await form.getByTestId("guest-search-input").fill("Huesped");
    const guestResult = form.getByTestId("guest-search-results").getByRole("button").filter({ hasText: "Huesped E2E" });
    await expect(guestResult).toBeVisible();
    await guestResult.click();
    const categorySelect = form.getByRole("combobox", { name: /^Category$/i });
    await expect(categorySelect).toHaveCount(1);
    await categorySelect.selectOption({ label: category });

    const checkIn = form.getByLabel("Check-in", { exact: true });
    const checkOut = form.getByLabel("Check-out", { exact: true });
    await expect(checkIn).toHaveAttribute("placeholder", "DD/MM/YYYY");
    await checkIn.fill(displayDate(checkInIso));
    await checkOut.fill(displayDate(checkOutIso));
    await expect(form.getByText("Category base rate", { exact: true })).toBeVisible();
    await form.getByRole("button", { name: "Create", exact: true }).click();

    await expect.poll(() => reservationPayload).not.toBeNull();
    expect(reservationPayload).toMatchObject({
      guest_id: 1,
      category_id: 1,
      check_in_date: checkInIso,
      check_out_date: checkOutIso,
      quote_token: "synthetic-f027-en-quote"
    });
    await expect(page.getByText("Reservation created", { exact: true })).toBeVisible();
    await expect(form).toHaveCount(0);
  });
});


test.describe("F-027 with an English browser locale", () => {
  test.use({ locale: "en-US" });

  test("Spanish interface keeps recalculation in preview until reception confirms applying changes", async ({ page }) => {
    const allocationRequests: Array<{ apply: boolean }> = [];
    const unexpectedDialogs: string[] = [];
    const dismissUnexpectedDialog = async (dialog: { message(): string; dismiss(): Promise<void> }) => {
      unexpectedDialogs.push(dialog.message());
      await dialog.dismiss();
    };
    page.on("dialog", dismissUnexpectedDialog);
    await page.route("**/api/config/interface-language", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ interface_language: "es" }) })
    );
    await page.route("**/api/reservations/allocation/recalculate", async (route) => {
      allocationRequests.push(route.request().postDataJSON() as { apply: boolean });
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          run_id: 1,
          status: "completed",
          objective_score: 0,
          assignments_created: 0,
          unassigned_count: 0,
          moved_count: 0
        })
      });
    });

    await page.goto("/login");
    await page.locator('input[type="email"]').fill(receptionist.email);
    await page.locator('input[type="password"]').fill(receptionist.password);
    await page.getByTestId("login-submit").click();
    await page.waitForURL("**/dashboard");
    await page.goto("/reservas");

    const main = page.locator("main");
    await expect(main.getByRole("heading", { name: "Reservas", exact: true })).toBeVisible();
    const applyChanges = main.getByRole("checkbox", { name: "Aplicar cambios" });
    const recalculate = main.getByRole("button", { name: "Recalcular asignación", exact: true });
    await expect(applyChanges).not.toBeChecked();

    await recalculate.click();
    await expect.poll(() => allocationRequests.length).toBe(1);
    expect(allocationRequests[0]?.apply).toBe(false);
    expect(unexpectedDialogs).toEqual([]);

    page.off("dialog", dismissUnexpectedDialog);
    await applyChanges.check();
    const cancelledConfirmation = page.waitForEvent("dialog");
    const cancelledClick = recalculate.click();
    const cancelledDialog = await cancelledConfirmation;
    expect(cancelledDialog.message()).toBe("¿Querés aplicar estos cambios de asignación? El sistema puede mover reservas entre habitaciones.");
    await cancelledDialog.dismiss();
    await cancelledClick;
    expect(allocationRequests).toHaveLength(1);

    const confirmation = page.waitForEvent("dialog");
    const applyClick = recalculate.click();
    const dialog = await confirmation;
    expect(dialog.message()).toBe("¿Querés aplicar estos cambios de asignación? El sistema puede mover reservas entre habitaciones.");
    await dialog.accept();
    await applyClick;
    await expect.poll(() => allocationRequests.length).toBe(2);
    expect(allocationRequests[1]?.apply).toBe(true);
  });
});

test.describe("F-027 task due date with an English browser locale", () => {
  test.use({ locale: "en-US", timezoneId: "America/Argentina/Buenos_Aires" });

  test("shows day-first 24-hour input and sends the selected local time as UTC", async ({ page }) => {
    const housekeeping = {
      email: process.env.E2E_HOUSEKEEPING_EMAIL || "housekeeping@e2e.com",
      password: process.env.E2E_HOUSEKEEPING_PASSWORD || "E2eHousekeeping1234!"
    };
    let createdTask: Record<string, unknown> | null = null;

    await page.route("**/api/operational-tasks", async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      createdTask = route.request().postDataJSON() as Record<string, unknown>;
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: 9001,
          hotel_id: 1,
          task_type: "housekeeping",
          status: "pending",
          priority: "medium",
          title: "Revisar fecha de vencimiento",
          due_at: createdTask.due_at,
          version: 1,
          created_at: "2026-09-30T12:00:00Z",
          updated_at: "2026-09-30T12:00:00Z"
        })
      });
    });

    await page.goto("/login");
    await page.locator('input[type="email"]').fill(housekeeping.email);
    await page.locator('input[type="password"]').fill(housekeeping.password);
    await page.getByTestId("login-submit").click();
    await page.waitForURL("**/habitaciones");
    await page.goto("/operacion/tareas");

    const dueAt = page.getByLabel("Vencimiento (opcional)", { exact: true });
    await expect(dueAt).toHaveAttribute("placeholder", "DD/MM/AAAA HH:MM");
    await dueAt.fill("02/11/2026 16:25");
    await expect(dueAt).toHaveValue("02/11/2026 16:25");
    await page.getByLabel("Título", { exact: true }).fill("Revisar fecha de vencimiento");
    await page.getByRole("button", { name: "Agregar", exact: true }).click();

    await expect.poll(() => createdTask).not.toBeNull();
    expect(createdTask?.due_at).toBe("2026-11-02T19:25:00.000Z");
  });
});

test("F-027 reservation file translates allocation and payment enum values", async ({ page }) => {
  const reservation = {
    id: 9001,
    confirmation_code: "F027-ENUM",
    guest_id: 1,
    guest: { id: 1, first_name: "Huésped", last_name: "Sintético" },
    room_id: null,
    category_id: 1,
    category_name: "Standard E2E",
    check_in_date: "2026-11-01",
    check_out_date: "2026-11-03",
    total_amount: 200000,
    amount_paid: 50000,
    deposit_amount: 60000,
    status: "pending",
    source: "direct",
    num_adults: 1,
    num_children: 0,
    currency_code: "ARS",
    allocation_status: "unassigned",
    version: 1
  };

  await page.route("**/api/config/interface-language", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ interface_language: "es" }) })
  );
  await page.route(/\/api\/reservations\/(?:\?.*)?$/, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([reservation]) })
  );
  await page.route(/\/api\/reservations\/9001$/, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(reservation) })
  );
  await page.route("**/api/reservations/9001/operations-summary", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        reservation_id: 9001,
        confirmation_code: "F027-ENUM",
        status: "pending",
        source: "direct",
        allocation_status: "unassigned",
        requires_manual_review: false,
        payment_collection_model: "hotel_collect",
        settlement_status: "pending",
        pending_action_count: 0,
        pending_actions: [],
        financial_summary: {
          reservation_id: 9001,
          confirmation_code: "F027-ENUM",
          status: "pending",
          currency_code: "ARS",
          total_amount: 200000,
          deposit_required: 60000,
          amount_paid: 50000,
          hotel_received_amount: 50000,
          ota_prepaid_amount: 0,
          balance_due: 150000,
          operational_total_amount: 200000,
          operational_balance_due: 150000,
          billing_adjustment_total: 0,
          payment_collection_model: "hotel_collect",
          settlement_status: "pending",
          has_financial_reconciliation_gap: false,
          financial_reconciliation_gap: null,
          transactions: [],
          billing_adjustments: [],
          completed_payments: 1
        },
        open_adjustments: []
      })
    })
  );
  await page.route("**/api/payments/summary/9001", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        reservation_id: 9001,
        confirmation_code: "F027-ENUM",
        status: "pending",
        currency_code: "ARS",
        total_amount: 200000,
        deposit_required: 60000,
        amount_paid: 50000,
        balance_due: 150000,
        completed_payments: 1,
        transactions: [{
          id: 9002,
          amount: 50000,
          currency: "ARS",
          method: "cash",
          type: "deposit",
          status: "completed",
          created_at: "2026-09-30T12:00:00Z"
        }]
      })
    })
  );
  await page.route("**/api/reservations/9001/communications", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
  );

  await page.goto("/login");
  await page.locator('input[type="email"]').fill(receptionist.email);
  await page.locator('input[type="password"]').fill(receptionist.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard");
  await page.goto("/reservas");

  const reservationRow = page.getByRole("row").filter({ hasText: "F027-ENUM" });
  await expect(reservationRow).toBeVisible();
  await reservationRow.getByRole("button", { name: "Ficha", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Reserva F027-ENUM/ })).toBeVisible();
  await expect(page.getByText("Sin habitación asignada", { exact: true })).toBeVisible();
  await expect(page.getByText("Seña · Efectivo · Confirmado", { exact: true })).toBeVisible();
  await expect(page.getByText("unassigned", { exact: true })).toHaveCount(0);
});
