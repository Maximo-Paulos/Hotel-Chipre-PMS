import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const migratedFiles = [
  "src/views/public/LoginPage.tsx",
  "src/views/public/RegisterOwnerPage.tsx",
  "src/ui/AppShell.tsx",
  "src/views/protected/DashboardPage.tsx",
  "src/views/protected/GuestsPage.tsx",
  "src/components/GuestQuickCreatePanel.tsx",
  "src/views/protected/RoomsPage.tsx",
  "src/components/ReservationDetailDrawer.tsx",
  "src/views/protected/ReservationsPage.tsx",
  "src/views/protected/OccupancyPlanningPage.tsx"
];
const localeFiles = ["auth.json", "common.json", "appshell.json", "dashboard.json", "guests.json", "rooms.json", "reservations.json"];
const spanishLiteralPatterns = [
  /"[^"\r\n]*[áéíóúÁÉÍÓÚñÑ¿¡][^"\r\n]*"/gu,
  /'[^'\r\n]*[áéíóúÁÉÍÓÚñÑ¿¡][^'\r\n]*'/gu,
  /`[^`\r\n]*[áéíóúÁÉÍÓÚñÑ¿¡][^`\r\n]*`/gu
];

test("migrated auth screens keep Spanish UI literals in es/auth.json", async () => {
  const violations = [];

  for (const relativePath of migratedFiles) {
    const source = await readFile(new URL(relativePath, import.meta.url.replace(/[^/]+$/, "")), "utf8");
    for (const pattern of spanishLiteralPatterns) {
      for (const match of source.matchAll(pattern)) {
        violations.push(`${relativePath}: ${match[0]}`);
      }
    }
  }

  assert.deepEqual(violations, [], `Spanish UI literals found outside locale files:\n${violations.join("\n")}`);
});

test("English and Spanish starter namespaces keep the same key shape", async () => {
  const flattenKeys = (value, prefix = "") =>
    Object.entries(value).flatMap(([key, nested]) => {
      const path = prefix ? `${prefix}.${key}` : key;
      return nested && typeof nested === "object" ? flattenKeys(nested, path) : [path];
    });

  for (const fileName of localeFiles) {
    const [spanish, english] = await Promise.all(
      ["es", "en"].map(async (language) => {
        const contents = await readFile(new URL(`src/locales/${language}/${fileName}`, import.meta.url), "utf8");
        return flattenKeys(JSON.parse(contents)).sort();
      })
    );
    assert.deepEqual(english, spanish, `${fileName} must expose the same keys in en and es`);
  }
});
