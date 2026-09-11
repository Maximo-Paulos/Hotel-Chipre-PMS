import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { transformSync } from "esbuild";

// csvCell.ts is plain TypeScript with no imports, so a one-shot esbuild
// transform is enough to exercise the real source without a test runner.
const source = readFileSync(new URL("./src/utils/csvCell.ts", import.meta.url), "utf8");
const { code } = transformSync(source, { loader: "ts", format: "esm" });
const { toCsvCell } = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);

test("leading formula characters are neutralised", () => {
  for (const payload of ["=HYPERLINK(\"http://x\")", "+1+1", "-2+3", "@SUM(A1)", "\tcmd", "\rcmd"]) {
    assert.ok(toCsvCell(payload).replace(/^"/, "").startsWith("'"), `not neutralised: ${JSON.stringify(payload)}`);
  }
});

test("quotes, commas and newlines are quoted and escaped", () => {
  assert.equal(toCsvCell('Hotel "Río", Sur'), '"Hotel ""Río"", Sur"');
  assert.equal(toCsvCell("línea\nsiguiente"), '"línea\nsiguiente"');
});

test("plain values and empties pass through", () => {
  assert.equal(toCsvCell("dueno@hotel.com"), "dueno@hotel.com");
  assert.equal(toCsvCell(22), "22");
  assert.equal(toCsvCell(null), "");
  assert.equal(toCsvCell(undefined), "");
});

test("a formula that also needs quoting gets both treatments", () => {
  assert.equal(toCsvCell('=cmd|"/c calc",A1'), `"'=cmd|""/c calc"",A1"`);
});
