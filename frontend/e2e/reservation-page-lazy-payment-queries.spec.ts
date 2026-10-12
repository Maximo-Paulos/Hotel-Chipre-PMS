import { expect, test } from "@playwright/test";

import { loginAsStepUpOwner } from "./support/step-up-owner";

test("reservation list defers cash and surcharge reads until a payment form opens", async ({ page }, testInfo) => {
  await loginAsStepUpOwner(page, "cash-business", testInfo.project.name);

  const paymentLookupReads = new Map<string, number>([
    ["/api/cash-register/sessions", 0],
    ["/api/payment-surcharges", 0]
  ]);
  let reservationListReads = 0;
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname.replace(/\/+$/, "");
    if (request.method() === "GET" && path === "/api/reservations") reservationListReads += 1;
    if (request.method() === "GET" && paymentLookupReads.has(path)) {
      paymentLookupReads.set(path, (paymentLookupReads.get(path) ?? 0) + 1);
    }
  });

  await page.goto("/reservas");
  await expect(page.locator("main").getByRole("heading", { name: "Reservas", exact: true })).toBeVisible();
  await expect.poll(() => reservationListReads).toBeGreaterThan(0);
  await page.waitForTimeout(250);
  expect(Object.fromEntries(paymentLookupReads)).toEqual({
    "/api/cash-register/sessions": 0,
    "/api/payment-surcharges": 0
  });

  const cashSessionsResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/cash-register/sessions" && response.status() === 200
  );
  const surchargesResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/payment-surcharges" && response.status() === 200
  );
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();
  await Promise.all([cashSessionsResponse, surchargesResponse]);

  expect(Object.fromEntries(paymentLookupReads)).toEqual({
    "/api/cash-register/sessions": 1,
    "/api/payment-surcharges": 1
  });
});
