import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("./src/utils/analyticsValue.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
}).outputText;
const module = { exports: {} };
vm.runInNewContext(compiled, {
  module,
  exports: module.exports,
  require: () => ({ formatMoney: (amount, currency) => `${currency}:${amount}` })
});

const { formatAnalyticsTableValue } = module.exports;

test("analytics detail trusts explicit availability metadata for aggregated values", () => {
  assert.equal(
    formatAnalyticsTableValue("1234.50", "revenue_net_ars", { unavailable_currencies: [] }),
    "ARS:1234.5"
  );
  assert.equal(
    formatAnalyticsTableValue("1234.50", "revenue_net_ars", { unavailable_currencies: ["USD"] }),
    "ARS:1234.5"
  );
  assert.equal(
    formatAnalyticsTableValue("1234.50", "revenue_net_ars", { unavailable_currencies: ["ARS"] }),
    "No disponible"
  );
  assert.equal(
    formatAnalyticsTableValue("1234.50", "value_ars", { value_ars_available: true }),
    "ARS:1234.5"
  );
  assert.equal(
    formatAnalyticsTableValue("1234.50", "value_ars", { value_ars_available: false }),
    "No disponible"
  );
});

test("legacy analytics payloads keep the source-currency safety fallback", () => {
  assert.equal(formatAnalyticsTableValue("120", "revenue_net_ars", { source_currency: "ARS" }), "ARS:120");
  assert.equal(formatAnalyticsTableValue("120", "revenue_net_ars", {}), "No disponible");
});
