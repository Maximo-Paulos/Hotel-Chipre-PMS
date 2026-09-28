import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { transformSync } from "esbuild";

const source = readFileSync(new URL("./src/utils/escapeHtml.ts", import.meta.url), "utf8");
const { code } = transformSync(source, { loader: "ts", format: "esm" });
const { escapeHtml, resolveVoucherOperationalBalance } = await import(
  `data:text/javascript;base64,${Buffer.from(code).toString("base64")}`
);

test("voucher text escapes markup and all HTML-significant characters", () => {
  assert.equal(
    escapeHtml(`<img src=x onerror="alert('x')"> & guest`),
    "&lt;img src=x onerror=&quot;alert(&#39;x&#39;)&quot;&gt; &amp; guest"
  );
});

test("voucher text preserves ordinary Unicode and safely stringifies values", () => {
  assert.equal(escapeHtml("Máximo & huéspedes"), "Máximo &amp; huéspedes");
  assert.equal(escapeHtml(42), "42");
  assert.equal(escapeHtml(null), "");
  assert.equal(escapeHtml(undefined), "");
});

test("voucher chooses the operational balance and never falls back to lodging-only due", () => {
  assert.equal(resolveVoucherOperationalBalance(5000, 0), 5000);
  assert.equal(resolveVoucherOperationalBalance(undefined, 0), 0);
  assert.equal(resolveVoucherOperationalBalance(undefined, null), null);
  assert.equal(resolveVoucherOperationalBalance(Number.NaN, -1), null);
});
