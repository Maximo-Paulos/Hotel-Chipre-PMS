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
  "src/auth/ActionStepUpProvider.tsx",
  "src/views/protected/OccupancyPlanningPage.tsx"
];
const localeFiles = ["auth.json", "common.json", "appshell.json", "dashboard.json", "guests.json", "rooms.json", "reservations.json"];
const spanishLiteralPatterns = [
  /"[^"\r\n]*[áéíóúÁÉÍÓÚñÑ¿¡][^"\r\n]*"/gu,
  /'[^'\r\n]*[áéíóúÁÉÍÓÚñÑ¿¡][^'\r\n]*'/gu,
  /`[^`\r\n]*[áéíóúÁÉÍÓÚñÑ¿¡][^`\r\n]*`/gu
];
const backendCheckinValidationMessages = new Set([
  "El nombre es obligatorio",
  "El apellido es obligatorio",
  "El tipo de documento (DNI/pasaporte) es obligatorio",
  "El número de documento es obligatorio",
  "La nacionalidad es obligatoria",
  "El país es obligatorio",
  "El lugar de nacimiento es obligatorio",
  "El país de nacimiento es obligatorio",
  "El estado civil es obligatorio",
  "La ocupación es obligatoria",
  "El huésped debe aceptar los términos y condiciones"
]);

test("migrated auth screens keep Spanish UI literals in es/auth.json", async () => {
  const violations = [];

  for (const relativePath of migratedFiles) {
    const source = await readFile(new URL(relativePath, import.meta.url.replace(/[^/]+$/, "")), "utf8");
    for (const pattern of spanishLiteralPatterns) {
      for (const match of source.matchAll(pattern)) {
        // This exact phrase identifies the backend's Spanish configuration
        // error so the UI can replace it with its localized message. It is a
        // protocol sentinel, not text rendered to the operator.
        if (relativePath === "src/views/protected/ReservationsPage.tsx" && match[0] === '"correo del hotel no está disponible"') continue;
        // These values are server validation protocol sentinels in the
        // check-in drawer; its rendering path maps them to locale keys.
        if (
          relativePath === "src/components/ReservationDetailDrawer.tsx" &&
          backendCheckinValidationMessages.has(match[0].slice(1, -1))
        ) continue;
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

test("reservation group manual-rate notice uses its declared Spanish error key", async () => {
  const source = await readFile(new URL("src/views/protected/ReservationsPage.tsx", import.meta.url.replace(/[^/]+$/, "")), "utf8");
  const locale = JSON.parse(await readFile(new URL("src/locales/es/reservations.json", import.meta.url.replace(/[^/]+$/, "")), "utf8"));

  assert.equal(locale.page.errors.groupManualRateUnsupported, "Los grupos requieren una cotización por habitación y no admiten tarifa manual.");
  assert.match(source, /t\("page\.errors\.groupManualRateUnsupported"\)/);
  assert.doesNotMatch(source, /t\("page\.form\.groupManualRateUnsupported"\)/);
});

test("reservation and room views use declared localized keys", async () => {
  const read = (path) => readFile(new URL(path, import.meta.url), "utf8");
  const [reservations, drawer, rooms, spanishReservations, englishReservations, spanishRooms, englishRooms, spanishCommon, englishCommon] = await Promise.all([
    read("src/views/protected/ReservationsPage.tsx"),
    read("src/components/ReservationDetailDrawer.tsx"),
    read("src/views/protected/RoomsPage.tsx"),
    read("src/locales/es/reservations.json").then(JSON.parse),
    read("src/locales/en/reservations.json").then(JSON.parse),
    read("src/locales/es/rooms.json").then(JSON.parse),
    read("src/locales/en/rooms.json").then(JSON.parse),
    read("src/locales/es/common.json").then(JSON.parse),
    read("src/locales/en/common.json").then(JSON.parse)
  ]);

  for (const locale of [spanishReservations, englishReservations]) {
    assert.ok(locale.drawer.errors.manualPaymentReferenceRequired);
    for (const key of ["refundAppliedAmountUnavailable", "refundMustUseOriginalCurrency", "refundNightAmountInvalid", "refundNightAmountExceedsSource", "refundNightRoundingMismatch", "refundSourceRequired", "refundReasonRequired"]) {
      assert.ok(locale.drawer.errors[key], `drawer.errors.${key} must be localized`);
    }
    for (const key of ["communicationAccepted", "communicationUnknown", "communicationFailed", "communicationPending"]) {
      assert.ok(locale.page.errors[key], `page.errors.${key} must be localized`);
    }
    assert.ok(locale.page.details.communicationResend);
  }
  for (const locale of [spanishRooms, englishRooms]) assert.ok(locale.blocks.roomFallback);
  assert.equal(spanishCommon.saving, "Guardando...");
  assert.equal(englishCommon.saving, "Saving...");

  assert.match(reservations, /t\("drawer\.errors\.manualPaymentReferenceRequired"\)/);
  assert.match(reservations, /t\("drawer\.errors\.refundAppliedAmountUnavailable"\)/);
  assert.match(reservations, /t\("drawer\.errors\.priorReceiptOtherCurrency"\)/);
  assert.match(reservations, /t\("drawer\.errors\.paymentFxQuoteUnavailable"\)/);
  assert.match(reservations, /t\("drawer\.errors\.voucherFinancialSummaryUnavailable"\)/);
  assert.match(reservations, /t\("page\.errors\.communicationAccepted"\)/);
  assert.match(reservations, /t\("page\.details\.communicationResend"\)/);
  assert.match(reservations, /t\("common:saving"\)/);
  assert.doesNotMatch(reservations, /t\("page\.errors\.manualPaymentReferenceRequired"\)/);
  assert.doesNotMatch(reservations, /t\("page\.messages\.communication(?:Accepted|Unknown|Failed|Pending)"\)/);
  assert.match(drawer, /t\("drawer\.errors\.manualPaymentReferenceRequired"\)/);
  assert.doesNotMatch(drawer, /t\("page\.errors\.manualPaymentReferenceRequired"\)/);
  assert.match(drawer, /missing required guest data\|faltan datos obligatorios del huésped/i);
  assert.match(drawer, /must be paid first\|debe abonarse/i);
  assert.match(rooms, /t\("blocks\.roomFallback"\)/);
  assert.doesNotMatch(rooms, /t\("inventory\.roomFallback"\)/);
});
