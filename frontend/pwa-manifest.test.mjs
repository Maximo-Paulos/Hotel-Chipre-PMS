import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const publicRoot = path.join(frontendRoot, "public");

function readPngDimensions(filePath) {
  const buffer = fs.readFileSync(filePath);
  assert.deepEqual([...buffer.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10], `${filePath} is not a PNG`);
  return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) };
}

test("PWA manifest declares installable metadata and real icon files", () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(publicRoot, "manifest.webmanifest"), "utf8"));

  assert.equal(manifest.name, "Hotel Chipre PMS");
  assert.equal(manifest.short_name, "Chipre PMS");
  assert.equal(manifest.lang, "es");
  assert.equal(manifest.display, "standalone");
  assert.equal(manifest.start_url, "/");
  assert.equal(manifest.scope, "/");
  assert.equal(manifest.theme_color, "#12324f");
  assert.equal(manifest.background_color, "#12324f");

  const iconSizes = new Set();
  for (const icon of manifest.icons) {
    const iconPath = path.join(publicRoot, icon.src.replace(/^\//, ""));
    assert.ok(fs.existsSync(iconPath), `missing manifest icon: ${icon.src}`);
    const dimensions = readPngDimensions(iconPath);
    const actualSize = `${dimensions.width}x${dimensions.height}`;
    assert.equal(actualSize, icon.sizes, `wrong dimensions for ${icon.src}`);
    iconSizes.add(actualSize);
  }

  assert.ok(iconSizes.has("192x192"));
  assert.ok(iconSizes.has("512x512"));
  assert.ok(manifest.icons.some((icon) => icon.purpose === "maskable" && icon.sizes === "192x192"));
  assert.ok(manifest.icons.some((icon) => icon.purpose === "maskable" && icon.sizes === "512x512"));
});

test("service worker keeps operational API responses out of the shell cache", () => {
  const serviceWorker = fs.readFileSync(path.join(publicRoot, "sw.js"), "utf8");
  assert.match(serviceWorker, /const NEVER_CACHE_PREFIXES = \["\/api", "\/health"\]/);
  assert.match(serviceWorker, /NEVER_CACHE_PREFIXES\.some\(\(prefix\) => url\.pathname\.startsWith\(prefix\)\)/);
});

test("application shell exposes explicit offline and stale-data messaging", () => {
  const appShell = fs.readFileSync(path.join(frontendRoot, "src/ui/AppShell.tsx"), "utf8");
  const spanishShell = fs.readFileSync(path.join(frontendRoot, "src/locales/es/appshell.json"), "utf8");
  assert.match(appShell, /useOnlineStatus/);
  assert.match(appShell, /data-testid="offline-banner"/);
  assert.match(spanishShell, /pueden estar desactualizados/);
});
