import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("./src/hooks/useReservations.ts", import.meta.url), "utf8");

test("reservation reads retry one transient 408 timeout or pool-exhaustion 503", () => {
  assert.match(source, /const retryTransientServiceUnavailable = \(failureCount: number, error: unknown\) =>\s+error instanceof ApiError && \(error\.status === 408 \|\| error\.status === 503\) && failureCount < 1/);
  assert.match(source, /const transientServiceUnavailableRetryDelay = \(_failureCount: number, error: unknown\) =>\s+error instanceof ApiError \? error\.retryAfterMs \?\? 1000 : 1000/);

  for (const hookName of ["useReservations", "usePendingReservationActions", "usePendingCancellationReviews"]) {
    const hook = source.match(new RegExp(`export function ${hookName}\\([^]*?\\n\\}`))?.[0] ?? "";
    assert.ok(hook, `${hookName} must remain defined`);
    assert.match(hook, /retry: retryTransientServiceUnavailable/);
    assert.match(hook, /retryDelay: transientServiceUnavailableRetryDelay/);
  }
});

test("shared operational and movement queries use the bounded transient read retry", async () => {
  const [main, tasks, reservations] = await Promise.all([
    readFile(new URL("./src/main.tsx", import.meta.url), "utf8"),
    readFile(new URL("./src/views/protected/OperationalTasksPage.tsx", import.meta.url), "utf8"),
    readFile(new URL("./src/views/protected/ReservationsPage.tsx", import.meta.url), "utf8")
  ]);

  assert.match(main, /if \(error instanceof ApiError && error\.status === 408\) return failureCount < 1/);
  for (const hookName of ["tasksQuery", "handoffsQuery"]) {
    const hook = tasks.match(new RegExp(`const ${hookName} = useQuery\\(\\{[^]*?\\n  \\}\\);`))?.[0] ?? "";
    assert.ok(hook, `${hookName} must remain defined`);
    assert.doesNotMatch(hook, /retry:\s*false/);
  }
  assert.match(reservations, /const movementGroupsQuery = useQuery<RoomMovementGroup\[]>\(\{[\s\S]*?queryFn: \(\) => listRoomMovementGroups\(6, session\)/);
});
