import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("./src/hooks/useReservations.ts", import.meta.url), "utf8");

test("reservation list retries one pool-exhaustion 503 using the bounded server delay", () => {
  const listQuery = source.match(/export function useReservations\(filters: ReservationFilters\) \{([\s\S]*?)\n\}/)?.[1] ?? "";

  assert.ok(listQuery, "useReservations must remain defined");
  assert.match(listQuery, /retry: \(failureCount, error\) => error instanceof ApiError && error\.status === 503 && failureCount < 1/);
  assert.match(listQuery, /retryDelay: \(_failureCount, error\) => error instanceof ApiError \? error\.retryAfterMs \?\? 1000 : 1000/);
});
