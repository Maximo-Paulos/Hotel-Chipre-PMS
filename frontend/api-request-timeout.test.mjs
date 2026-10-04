import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import test from "node:test";
import ts from "typescript";

const clientSource = await readFile(new URL("./src/api/client.ts", import.meta.url), "utf8");

function loadClient(fetchImpl) {
  const source = clientSource.replace("import.meta.env.VITE_API_URL", "undefined");
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
  }).outputText;
  const module = { exports: {} };

  vm.runInNewContext(
    compiled,
    {
      module,
      exports: module.exports,
      require: () => ({ broadcastDomainChange() {} }),
      fetch: fetchImpl,
      AbortController,
      Headers,
      URL,
      setTimeout,
      clearTimeout,
      atob,
      window: { location: { pathname: "/dashboard", assign() {} } }
    },
    { filename: "frontend/src/api/client.ts" }
  );

  return module.exports;
}

const waitForAbort = (_url, { signal }) => new Promise((_resolve, reject) => {
  if (signal.aborted) reject(signal.reason);
  else signal.addEventListener("abort", () => reject(signal.reason), { once: true });
});

test("apiFetch aborts a request at its finite deadline and reports a retryable timeout", async () => {
  const client = loadClient(waitForAbort);

  await assert.rejects(
    client.apiFetch("/api/reports/occupancy", { timeoutMs: 20 }),
    (error) => error.status === 408 && /tardó demasiado/i.test(error.message)
  );
  assert.equal(client.DEFAULT_API_REQUEST_TIMEOUT_MS, 20_000);
  assert.equal(client.DEFAULT_API_MUTATION_TIMEOUT_MS, 60_000);
});

test("a timed-out mutation warns operators to check its state before repeating it", async () => {
  const client = loadClient(waitForAbort);

  await assert.rejects(
    client.apiFetch("/api/payments", { method: "POST", timeoutMs: 20 }),
    (error) => error.status === 408 && /revisá el estado antes de repetir/i.test(error.message)
  );
});

test("apiFetch forwards caller cancellation without converting it into a timeout", async () => {
  const client = loadClient(waitForAbort);
  const controller = new AbortController();
  const request = client.apiFetch("/api/reservations/actions/pending", {
    signal: controller.signal,
    timeoutMs: 5_000
  });

  controller.abort(new DOMException("Query was cancelled", "AbortError"));

  await assert.rejects(request, (error) => error.name === "AbortError");
});
