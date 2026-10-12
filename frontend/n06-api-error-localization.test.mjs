import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));

test("API fallback errors follow the selected locale and never use browser status text", async () => {
  const client = await readFile(path.join(frontendRoot, "src/api/client.ts"), "utf8");

  assert.match(client, /formatErrorDetail\(detail\) \|\| requestFailureFallback\(\)/u);
  assert.match(client, /i18n\?\.language\?\.toLowerCase\(\)\.startsWith\("en"\)/u);
  assert.match(client, /The request could not be completed\. Please try again\./u);
  assert.match(client, /No se pudo completar la solicitud\. Intentá de nuevo\./u);
  assert.match(client, /error instanceof TypeError && !signal\?\.aborted/u);
  assert.match(client, /throw new ApiError\(0, requestFailureFallback\(\)\)/u);
  assert.doesNotMatch(client, /response\.statusText\s*\|\|/u);
});

test("Spanish check-in field validation messages map to translated labels", async () => {
  const drawer = await readFile(
    path.join(frontendRoot, "src/components/ReservationDetailDrawer.tsx"),
    "utf8",
  );
  const localizedFields = [
    ["El nombre es obligatorio", "firstName"],
    ["El apellido es obligatorio", "lastName"],
    ["El tipo de documento (DNI/pasaporte) es obligatorio", "documentType"],
    ["El número de documento es obligatorio", "documentNumber"],
    ["La nacionalidad es obligatoria", "nationality"],
    ["El país es obligatorio", "country"],
    ["El lugar de nacimiento es obligatorio", "birthPlace"],
    ["El país de nacimiento es obligatorio", "birthCountry"],
    ["El estado civil es obligatorio", "maritalStatus"],
    ["La ocupación es obligatoria", "occupation"],
    ["El huésped debe aceptar los términos y condiciones", "termsAccepted"],
  ];

  for (const [message, field] of localizedFields) {
    assert.ok(
      drawer.includes(`"${message}": "drawer.checkinCapture.requiredFields.${field}"`),
      `Missing localized check-in mapping for ${field}`,
    );
  }
});
