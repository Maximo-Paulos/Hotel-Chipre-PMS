import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("./src/hooks/useReservations.ts", import.meta.url), "utf8");

test("reservation list retries one pool-exhaustion 503 using the bounded server delay", () => {
  assert.match(source, /const retryTransientServiceUnavailable = \(failureCount: number, error: unknown\) =>\s+error instanceof ApiError && error\.status === 503 && failureCount < 1/);
  assert.match(source, /const transientServiceUnavailableRetryDelay = \(_failureCount: number, error: unknown\) =>\s+error instanceof ApiError \? error\.retryAfterMs \?\? 1000 : 1000/);

  for (const hookName of ["useReservations", "usePendingReservationActions", "usePendingCancellationReviews"]) {
    const hook = source.match(new RegExp(`export function ${hookName}\\([^]*?\\n\\}`))?.[0] ?? "";
    assert.ok(hook, `${hookName} must remain defined`);
    assert.match(hook, /retry: retryTransientServiceUnavailable/);
    assert.match(hook, /retryDelay: transientServiceUnavailableRetryDelay/);
  }
});
