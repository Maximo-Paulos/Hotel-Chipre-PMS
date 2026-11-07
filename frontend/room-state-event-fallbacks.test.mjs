import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));

test("room event history uses contextual missing-value labels in Spanish and English", async () => {
  const locales = await Promise.all(["es", "en"].map(async (language) => {
    const source = await readFile(path.join(frontendRoot, "src", "locales", language, "appshell.json"), "utf8");
    return [language, JSON.parse(source).analyticsRoomEvents];
  }));
  const translations = Object.fromEntries(locales);

  assert.equal(translations.es.roomUnavailable, "Habitación no disponible");
  assert.equal(translations.es.noteMissing, "Sin nota registrada");
  assert.equal(translations.en.roomUnavailable, "Room unavailable");
  assert.equal(translations.en.noteMissing, "No note recorded");

  const component = await readFile(path.join(frontendRoot, "src/views/protected/analytics/AnalyticsPages.tsx"), "utf8");
  assert.match(component, /analyticsRoomEvents\.roomUnavailable/u);
  assert.match(component, /event\.reason_note\?\.trim\(\) \|\| t\("analyticsRoomEvents\.noteMissing"\)/u);
});
