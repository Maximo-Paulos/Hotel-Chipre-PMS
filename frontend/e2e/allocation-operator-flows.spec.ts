import { expect, test, type Page } from "@playwright/test";

const receptionist = {
  email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
  password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!"
};

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(receptionist.email);
  await page.locator('input[type="password"]').fill(receptionist.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

const waitlistEntry = {
  id: 741,
  hotel_id: 1,
  guest_id: 742,
  category_id: 743,
  promoted_reservation_id: null,
  check_in_date: "2026-11-10",
  check_out_date: "2026-11-12",
  num_adults: 2,
  num_children: 0,
  status: "waiting",
  priority: 10,
  notes: "Prefiere cama doble",
  contact_phone: null,
  created_at: "2026-10-25T12:00:00Z",
  promoted_at: null,
  expired_at: null
};

test("reception reviews the engine's waitlist suggestion before creating a reservation", async ({ page }) => {
  await login(page);

  let promotionPayload: Record<string, unknown> | null = null;
  let suggestionsFail = false;
  let suggestedRoomId = 208;
  const suggestionFingerprint = () => suggestedRoomId === 208 ? "a".repeat(64) : "b".repeat(64);
  await page.route("**/api/waitlist**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname === "/api/waitlist/suggestions") {
      if (suggestionsFail) {
        await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Propuesta temporalmente no disponible." }) });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([{
          entry_id: waitlistEntry.id,
          guest_id: waitlistEntry.guest_id,
          guest_name: "Ada Prueba",
          category_id: waitlistEntry.category_id,
          check_in_date: waitlistEntry.check_in_date,
          check_out_date: waitlistEntry.check_out_date,
          priority: waitlistEntry.priority,
          suggested_room_id: suggestedRoomId,
          suggested_room_number: String(suggestedRoomId),
          expected_entry_fingerprint: suggestionFingerprint(),
          reason: "Habitación compatible disponible para todo el período.",
          allocation_basis: "feasibility_only_no_price_snapshot"
        }])
      });
      return;
    }
    if (url.pathname === "/api/waitlist/" && request.method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([waitlistEntry]) });
      return;
    }
    if (url.pathname === `/api/waitlist/${waitlistEntry.id}/promote` && request.method() === "POST") {
      promotionPayload = request.postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ waitlist_entry: { ...waitlistEntry, status: "promoted" }, reservation: { id: 880 } })
      });
      return;
    }
    await route.continue();
  });
  await page.route("**/api/guests/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([{ id: waitlistEntry.guest_id, first_name: "Ada", last_name: "Prueba" }])
    });
  });
  await page.route("**/api/rooms/categories", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([{ id: waitlistEntry.category_id, name: "Doble estándar", code: "DBL", max_occupancy: 2, base_price_per_night: 50000 }])
    });
  });

  await page.goto("/operacion/lista-espera");
  await expect(page.getByText("Propuesta del motor: habitación 208")).toBeVisible();
  await expect(page.getByRole("button", { name: "Revisar propuesta" })).toBeEnabled();
  await expect.poll(() => promotionPayload).toBeNull();

  await page.getByRole("button", { name: "Revisar propuesta" }).click();
  await expect(page.getByText("La propuesta todavía no crea una reserva. Recepción debe confirmarla.")).toBeVisible();
  const confirmWaitlistButton = page.getByRole("button", { name: "Confirmar reserva en Hab. 208" });
  await expect(confirmWaitlistButton).toBeEnabled();
  expect(promotionPayload).toBeNull();

  suggestionsFail = true;
  await page.getByRole("button", { name: "Actualizar propuestas del motor" }).click();
  await expect(page.getByText("La propuesta anterior no se puede confirmar porque no fue posible actualizarla. Volvé a calcular antes de continuar.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Sin propuesta válida para confirmar" })).toBeDisabled();
  expect(promotionPayload).toBeNull();

  suggestionsFail = false;
  await page.getByRole("button", { name: "Actualizar propuestas del motor" }).click();
  await expect(confirmWaitlistButton).toBeEnabled();

  suggestedRoomId = 209;
  await confirmWaitlistButton.click();
  await expect(page.getByText("La propuesta cambió o quedó desactualizada: ahora sugiere la habitación 209. Revisá la asignación actual y confirmala de nuevo.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Confirmar reserva en Hab. 209" })).toBeEnabled();
  expect(promotionPayload).toBeNull();

  await page.getByRole("button", { name: "Confirmar reserva en Hab. 209" }).click();
  await expect(page.getByText("Entrada promovida a reserva.")).toBeVisible();
  expect(promotionPayload).toMatchObject({
    room_id: 209,
    expected_entry_fingerprint: "b".repeat(64),
    notes: "Prefiere cama doble"
  });
});

test("a future room block applies a valid allocation plan only after explicit confirmation", async ({ page }) => {
  await login(page);

  let previewPayload: Record<string, unknown> | null = null;
  let createPayload: Record<string, unknown> | null = null;
  let extensionPreviewPayload: Record<string, unknown> | null = null;
  let extensionPayload: Record<string, unknown> | null = null;
  let previewOutcome: "failed" | "unassigned" | "complete" = "failed";
  let blockRecord: Record<string, unknown> | null = null;
  await page.route("**/api/rooms/", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([{
        id: 41,
        room_number: "101",
        floor: 1,
        category_id: 43,
        status: "available",
        housekeeping_status: "clean",
        is_active: true
      }])
    });
  });
  await page.route("**/api/rooms/categories", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([{ id: 43, name: "Doble estándar", code: "DBL", max_occupancy: 2, base_price_per_night: 50000 }])
    });
  });
  await page.route("**/api/reservations/occupancy-grid**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        rooms: [],
        reservations: [{
          id: 502,
          version: 1,
          room_id: 41,
          confirmation_code: "R-502",
          check_in_date: "2026-11-10",
          check_out_date: "2026-11-12",
          status: "pending",
          guest_name: "Ada Prueba",
          num_adults: 2,
          num_children: 0,
          operational_balance_due: 0
        }, {
          id: 503,
          version: 1,
          room_id: 41,
          confirmation_code: "R-503",
          check_in_date: "2026-11-12",
          check_out_date: "2026-11-14",
          status: "pending",
          guest_name: "Grace Prueba",
          num_adults: 1,
          num_children: 0,
          operational_balance_due: 0
        }],
        unassigned: [],
        blocks: []
      })
    });
  });
  await page.route("**/api/room-blocks/allocation-preview", async (route) => {
    previewPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        room_id: 41,
        starts_at: "2026-11-10",
        ends_at: "2026-11-12",
        is_indefinite: false,
        reservation_count: 1,
        protected_reservation_count: 0,
        requires_confirmation: true,
        allocation_run: {
          run_id: 790,
          status: previewOutcome === "failed" ? "failed" : "succeeded",
          trigger_type: "room_block_proposal",
          objective_score: 1,
          solver_summary: previewOutcome === "complete"
            ? "Se encontró una reasignación factible para el bloqueo."
            : previewOutcome === "unassigned"
              ? "El motor no encontró habitación de destino para la reserva."
              : "No se encontró una solución completa para estas fechas.",
          error_message: null,
          policy_version_id: 3,
          horizon_start: "2026-11-10",
          horizon_end: "2026-11-12",
          created_at: "2026-10-25T12:00:00Z",
          explanations: [],
          metrics: [],
          assignments: previewOutcome === "complete" ? [{
            id: 1,
            reservation_id: 502,
            source_room_id: 41,
            room_id: 42,
            status: "proposed",
            explanation_summary: "La habitación destino admite la categoría y las fechas."
          }] : previewOutcome === "unassigned" ? [{
            id: 2,
            reservation_id: 502,
            source_room_id: 41,
            room_id: null,
            status: "proposed",
            explanation_summary: "No hay una habitación compatible para todas las fechas."
          }] : []
        }
      })
    });
  });
  await page.route("**/api/room-blocks/", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(blockRecord ? [blockRecord] : []) });
      return;
    }
    if (route.request().method() === "POST") {
      createPayload = route.request().postDataJSON() as Record<string, unknown>;
      blockRecord = {
        id: 791,
        hotel_id: 1,
        room_id: 41,
        reason_code: "maintenance",
        reason_note: "Prueba de propuesta",
        starts_at: "2026-11-10",
        ends_at: "2026-11-12",
        is_indefinite: false,
        created_by_user_id: 1,
        resolved_by_user_id: null,
        resolved_at: null,
        created_at: "2026-10-25T12:00:00Z",
        updated_at: "2026-10-25T12:00:00Z"
      };
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(blockRecord)
      });
      return;
    }
    await route.continue();
  });
  await page.route("**/api/room-blocks/791/allocation-preview", async (route) => {
    extensionPreviewPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        block_id: 791,
        room_id: 41,
        previous_ends_at: "2026-11-12",
        ends_at: "2026-11-14",
        reservation_count: 1,
        protected_reservation_count: 0,
        overlapping_block_count: 0,
        requires_confirmation: true,
        allocation_run: {
          run_id: 792,
          status: "succeeded",
          trigger_type: "room_block_proposal",
          objective_score: 1,
          solver_summary: "Se encontró una reasignación factible para la extensión.",
          error_message: null,
          policy_version_id: 3,
          horizon_start: "2026-11-12",
          horizon_end: "2026-11-14",
          created_at: "2026-10-25T12:00:00Z",
          explanations: [],
          metrics: [],
          assignments: [{
            id: 3,
            reservation_id: 503,
            source_room_id: 41,
            room_id: 44,
            status: "proposed",
            explanation_summary: "La habitación destino admite la categoría y las fechas."
          }]
        }
      })
    });
  });
  await page.route("**/api/room-blocks/791/extend", async (route) => {
    extensionPayload = route.request().postDataJSON() as Record<string, unknown>;
    blockRecord = { ...blockRecord, ends_at: "2026-11-14" };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(blockRecord) });
  });

  await page.goto("/habitaciones");
  const blockForm = page.locator("form").filter({ has: page.getByRole("button", { name: "Calcular propuesta" }) });
  await blockForm.getByLabel("Habitación").selectOption("41");
  await blockForm.getByLabel("Desde").fill("2026-11-10");
  await blockForm.getByLabel("Hasta").fill("2026-11-12");
  await blockForm.getByLabel("Detalle").fill("Prueba de propuesta");

  const confirmButton = page.getByRole("button", { name: "Confirmar bloqueo y reasignaciones" });
  await expect(confirmButton).toBeDisabled();
  await blockForm.getByRole("button", { name: "Calcular propuesta" }).click();
  await expect(page.getByText("Reservas que se superponen con este bloqueo: 1.")).toBeVisible();
  await expect(page.getByText("El motor no encontró un plan completo que pueda confirmarse. No se creará el bloqueo. Revisá las reservas protegidas o probá otro período y volvé a calcular.")).toBeVisible();
  await expect(confirmButton).toBeDisabled();
  expect(createPayload).toBeNull();
  await blockForm.getByRole("button", { name: "Descartar propuesta" }).click();
  await expect(page.getByText("Reservas que se superponen con este bloqueo: 1.")).toHaveCount(0);
  expect(createPayload).toBeNull();

  previewOutcome = "unassigned";
  await blockForm.getByRole("button", { name: "Calcular propuesta" }).click();
  await expect(page.getByText("El motor deja 1 reservas sin habitación. El bloqueo no se puede confirmar con ese resultado.")).toBeVisible();
  await expect(page.getByText(/R-502.*Sin habitación/)).toBeVisible();
  await expect(confirmButton).toBeDisabled();
  expect(createPayload).toBeNull();

  previewOutcome = "complete";
  await blockForm.getByRole("button", { name: "Calcular propuesta" }).click();
  await expect(page.getByText("Reservas que se superponen con este bloqueo: 1.")).toBeVisible();
  await expect(page.getByText("Cambios de asignación propuestos por el motor: 1.")).toBeVisible();
  await expect(page.getByText(/R-502.*Habitación \(ID 42\)/)).toBeVisible();
  await expect(confirmButton).toBeEnabled();
  expect(previewPayload).toMatchObject({ room_id: 41, starts_at: "2026-11-10", ends_at: "2026-11-12" });
  expect(createPayload).toBeNull();

  await confirmButton.click();
  await expect(page.getByText("Bloqueo creado.")).toBeVisible();
  expect(createPayload).toMatchObject({ room_id: 41, allocation_run_id: 790 });

  await page.getByRole("button", { name: "Extender" }).click();
  await page.getByLabel("Nueva fecha de fin exclusiva (la habitación queda libre desde esa fecha)").fill("2026-11-14");
  await page.getByRole("button", { name: "Calcular propuesta de extensión" }).click();
  await expect(page.getByText("Período agregado: 1 reservas (0 requieren revisión) y 0 bloqueos superpuestos.")).toBeVisible();
  await expect(page.getByText("Cambios de asignación propuestos por el motor: 1.")).toBeVisible();
  await expect(page.getByText(/R-503.*Habitación \(ID 44\)/)).toBeVisible();
  const confirmExtensionButton = page.getByRole("button", { name: "Confirmar extensión y reasignaciones" });
  await expect(confirmExtensionButton).toBeEnabled();
  expect(extensionPreviewPayload).toMatchObject({ ends_at: "2026-11-14" });
  expect(extensionPayload).toBeNull();

  await confirmExtensionButton.click();
  await expect(page.getByText("Bloqueo extendido.")).toBeVisible();
  expect(extensionPayload).toMatchObject({ ends_at: "2026-11-14", allocation_run_id: 792 });
});
