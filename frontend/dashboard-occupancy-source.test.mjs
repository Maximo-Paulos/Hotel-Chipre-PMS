import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = async (path) => readFile(new URL(path, import.meta.url), "utf8");

test("dashboard occupancy uses the Reports daily aggregate and gates it by the existing permission", async () => {
  const [dashboard, reportsHook, reportApi] = await Promise.all([
    source("./src/views/protected/DashboardPage.tsx"),
    source("./src/hooks/useReports.ts"),
    source("./src/api/reports.ts")
  ]);

  assert.match(dashboard, /useOccupancyReport\(today, today, canViewOperationalReports\)/);
  assert.match(dashboard, /hasPermission\("reports:operational:view"\)/);
  assert.match(dashboard, /\$\{occupancy\.rate\}%/);
  assert.match(dashboard, /permissionUnavailable/);
  assert.doesNotMatch(dashboard, /useRooms|room\.status === "occupied"/);
  assert.match(reportsHook, /queryFn: \(\{ signal \}\) => getOccupancyReport\(startDate, endDate, session, signal\)/);
  assert.match(reportsHook, /enabled: enabled && Boolean\(startDate && endDate\)/);
  assert.match(reportApi, /\/api\/reports\/occupancy\?/);
});

test("reservations and reports read queries forward their TanStack abort signal and stop retrying hidden timeouts", async () => {
  const [reservationHooks, reportHooks, reservationApi] = await Promise.all([
    source("./src/hooks/useReservations.ts"),
    source("./src/hooks/useReports.ts"),
    source("./src/api/reservations.ts")
  ]);

  assert.match(reservationHooks, /queryFn: \(\{ signal \}\) => listReservations\(filters, session, signal\)/);
  assert.match(reservationHooks, /queryFn: \(\{ signal \}\) => listPendingReservationActions\(limit, session, signal\)/);
  assert.match(reservationHooks, /retry: false/);
  assert.match(reportHooks, /queryFn: \(\{ signal \}\) => getDailyOperationalReport\(reportDate, session, signal\)/);
  assert.match(reportHooks, /queryFn: \(\{ signal \}\) => getOccupancyReport\(startDate, endDate, session, signal\)/);
  assert.match(reservationApi, /listPendingReservationActions = \(limit = 100, session\?: SessionLike, signal\?: AbortSignal\)/);
});
