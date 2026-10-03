import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

const credentials = {
  email: process.env.E2E_OWNER_EMAIL || "owner@e2e.com",
  password: process.env.E2E_OWNER_PASSWORD || "E2ePass1234!"
};

test("owner exports the selected local date range as an Excel-compatible CSV", async ({ page }) => {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });

  await page.goto("/caja");
  const fromInput = page.getByTestId("cash-export-from");
  const toInput = page.getByTestId("cash-export-to");
  const selectedLocalDate = await fromInput.inputValue();
  await toInput.fill(selectedLocalDate);
  const exportButton = page.getByRole("button", { name: "Exportar CSV", exact: true });
  await expect(exportButton).toBeEnabled({ timeout: 20_000 });

  const responsePromise = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/cash-register/export.csv" && response.request().method() === "GET"
  );
  const downloadPromise = page.waitForEvent("download");
  await exportButton.click();
  const response = await responsePromise;
  expect(response.ok()).toBeTruthy();
  const download = await downloadPromise;
  const downloadedPath = await download.path();
  expect(downloadedPath).toBeTruthy();
  const csvBytes = await readFile(downloadedPath!);
  const csv = csvBytes.toString("utf8");
  expect(csvBytes.subarray(0, 3)).toEqual(Buffer.from([0xef, 0xbb, 0xbf]));
  expect(csv).toContain("fecha_local;hotel_id;");
  expect(csv).toContain("\r\n");
  expect(new URL(response.url()).searchParams.get("from")).toBe(selectedLocalDate);
  expect(new URL(response.url()).searchParams.get("to")).toBe(selectedLocalDate);

  expect(download.suggestedFilename()).toBe(`caja-${selectedLocalDate}-${selectedLocalDate}.csv`);
  await expect(page.getByText("Exportación de caja descargada.", { exact: true })).toBeVisible();
});
