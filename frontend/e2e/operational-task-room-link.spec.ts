import { expect, test, type Page } from "@playwright/test";

const manager = {
  email: process.env.E2E_MANAGER_EMAIL || "manager@e2e.com",
  password: process.env.E2E_MANAGER_PASSWORD || "E2eManager1234!"
};

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(manager.email);
  await page.locator('input[type="password"]').fill(manager.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test("a room linked to an operational task survives saving and reload", async ({ page }) => {
  const title = `QA room-linked task ${Date.now()}`;
  await login(page);
  await page.goto("/operacion/tareas");

  const form = page.locator("form").filter({ hasText: "Agregar pendiente" });
  await expect(form).toBeVisible();
  await form.getByLabel("Título").fill(title);
  await form.getByLabel("Habitación (opcional)").selectOption({ label: "Habitación 101" });

  const createResponsePromise = page.waitForResponse((response) =>
    response.request().method() === "POST" && new URL(response.url()).pathname === "/api/operational-tasks"
  );
  await form.getByRole("button", { name: "Agregar", exact: true }).click();
  const createResponse = await createResponsePromise;
  expect(createResponse.status()).toBe(201);
  const created = await createResponse.json() as { room_id: number | null; room_number: string | null };
  expect(created.room_id).not.toBeNull();
  expect(created.room_number).toBe("101");

  const task = page.locator("article").filter({ hasText: title });
  await expect(task).toContainText("Habitación 101");
  await page.reload();
  await expect(page.locator("article").filter({ hasText: title })).toContainText("Habitación 101");
});
