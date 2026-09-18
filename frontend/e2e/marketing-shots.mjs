/**
 * Captures the product screenshots the public site uses.
 *
 * Not a test: it is an asset generator, so it lives outside the Playwright
 * projects and never runs in CI. It drives the demo hotel seeded by
 * scripts/seed_marketing_demo.py, hides the operator-only debug chrome that
 * has no business on a marketing page, and writes viewport-sized captures
 * (never fullPage -- the previous batch reached 1280x13582 and was unusable),
 * downscaled and encoded to WebP in the browser so this stays a single
 * command with no image-processing dependency.
 *
 * Usage, from the repo root, with the demo stack already up:
 *
 *   .venv/bin/python scripts/seed_marketing_demo.py
 *   DATABASE_URL=sqlite:///$PWD/demo-marketing.db ... uvicorn app.main:app --port 8041
 *   VITE_API_URL=http://127.0.0.1:8041/api npm run dev -- --port 5174
 *   node e2e/marketing-shots.mjs
 */
import { chromium } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";

const BASE_URL = process.env.SHOTS_BASE_URL || "http://localhost:5174";
const EMAIL = process.env.SHOTS_EMAIL || "ana@hotelchipre.com.ar";
const PASSWORD = process.env.SHOTS_PASSWORD || "DemoChipre1234!";
const OUT_DIR = new URL("../public/marketing/screenshots/", import.meta.url).pathname;

/** Operator-only chrome: real, but noise on a landing page. */
const HIDE_CSS = `
  [data-testid="app-topbar"],
  [data-testid="realtime-status"],
  [data-testid="role-preview"],
  [data-testid="viewing-as-banner"],
  [data-testid="offline-banner"] { display: none !important; }
  /* React Query devtools only exist in the dev build. */
  .tsqd-parent-container, [aria-label="Open Tanstack query devtools"] { display: none !important; }
`;

const SHOTS = [
  { name: "dashboard", nav: "/dashboard", wait: "Visión general" },
  { name: "planilla", nav: "/operacion/planilla", wait: "Planilla de ocupación" },
  { name: "reservas", nav: "/reservas", wait: /reserva/i },
  { name: "caja", nav: "/caja", wait: /caja/i },
  { name: "tarifas", nav: "/operacion/tarifas", wait: /tarifa/i },
  { name: "analitica", nav: "/analytics", wait: /analítica|analitica|panel/i }
];

const VIEWPORTS = [
  { suffix: "", width: 1440, height: 900 },
  { suffix: "-mobile", width: 390, height: 844 }
];

async function login(page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: "networkidle" });
  await page.locator('input[type="email"]').fill(EMAIL);
  await page.locator('input[type="password"]').fill(PASSWORD);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
  await page.addStyleTag({ content: HIDE_CSS });
}

/**
 * Captured at deviceScaleFactor 2 for retina, then re-encoded at 0.75 of that
 * (so 1.5x) as WebP. Chromium already has an encoder, which keeps this script
 * free of an image-processing dependency.
 */
async function toWebp(page, pngBuffer) {
  const dataUrl = await page.evaluate(async (base64) => {
    const image = new Image();
    image.src = `data:image/png;base64,${base64}`;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(image.width * 0.75);
    canvas.height = Math.round(image.height * 0.75);
    const context = canvas.getContext("2d");
    context.imageSmoothingQuality = "high";
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/webp", 0.82);
  }, pngBuffer.toString("base64"));
  return Buffer.from(dataUrl.split(",")[1], "base64");
}

async function capture(page, shot, suffix) {
  // Client-side navigation: a full page load drops the in-memory session.
  await page.evaluate((path) => {
    window.history.pushState({}, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, shot.nav);
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(1200);
  await page.addStyleTag({ content: HIDE_CSS });

  const png = await page.screenshot();
  const file = `${OUT_DIR}${shot.name}${suffix}.webp`;
  await writeFile(file, await toWebp(page, png));
  console.log(`  ${shot.name}${suffix} -> ${Math.round((await import("node:fs")).statSync(file).size / 1024)} KB`);
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  const browser = await chromium.launch();

  for (const viewport of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      deviceScaleFactor: 2,
      locale: "es-AR"
    });
    const page = await context.newPage();
    console.log(`${viewport.width}x${viewport.height}`);
    await login(page);
    for (const shot of SHOTS) {
      try {
        await capture(page, shot, viewport.suffix);
      } catch (error) {
        console.error(`  ${shot.name}${viewport.suffix} FAILED: ${error.message}`);
      }
    }
    await context.close();
  }

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
