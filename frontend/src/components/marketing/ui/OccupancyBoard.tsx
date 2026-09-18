import { Fragment } from "react";

import { reservationStatusConfig } from "../../../utils/reservationStatus";
import type { ReservationStatus } from "../../../api/reservations";

/**
 * The occupancy board as the product actually renders it.
 *
 * This is a faithful copy of src/components/OccupancyGrid.tsx, not an
 * interpretation: same sticky "Habitación" column with "Hab. N / Piso N",
 * same slate-900 category bands, same day headers from the es-AR short
 * format, same per-night chips (the app repeats the guest name in every
 * night cell rather than drawing one bar across the stay), same diagonal
 * hatch for a blocked room, and the status colours come from
 * reservationStatusConfig -- the app's own source of truth -- rather than
 * being redefined here.
 *
 * It is markup instead of a screenshot so it stays sharp at any size and
 * reflows on a phone. The week shown matches the demo hotel used for the
 * product screenshots further down the page.
 */

type Stay = {
  guest: string;
  /** 1-indexed first night of the visible window. */
  start: number;
  nights: number;
  status: ReservationStatus;
};

type Row = { room: string; floor: number; stays: Stay[]; blocked?: { start: number; nights: number } };
type Group = { category: string; rows: Row[] };

// Five nights is what fits on screen at once beside the headline; the app
// itself paints a 30-day window inside the same horizontal scroller, which
// is why this table keeps its overflow-x rather than shrinking the cells.
const DAYS = ["jue 10-09", "vie 11-09", "sáb 12-09", "dom 13-09", "lun 14-09"];
const TODAY_INDEX = 0;

const GROUPS: Group[] = [
  {
    category: "Standard",
    rows: [
      { room: "101", floor: 1, stays: [{ guest: "Valentina Ferrari", start: 1, nights: 2, status: "checked_in" }] },
      { room: "102", floor: 1, stays: [{ guest: "Martín Quiroga", start: 1, nights: 4, status: "checked_in" }] },
      { room: "103", floor: 1, stays: [{ guest: "Lucía Benítez", start: 1, nights: 2, status: "deposit_paid" }] },
      { room: "104", floor: 1, stays: [{ guest: "Diego Lombardi", start: 2, nights: 3, status: "fully_paid" }] }
    ]
  },
  {
    category: "Superior con vista",
    rows: [
      { room: "201", floor: 2, stays: [{ guest: "Camila Ruiz Díaz", start: 1, nights: 5, status: "checked_in" }] },
      {
        room: "202",
        floor: 2,
        stays: [{ guest: "Julián Sosa", start: 1, nights: 3, status: "checked_in" }],
        blocked: { start: 4, nights: 2 }
      },
      { room: "203", floor: 2, stays: [{ guest: "Agustina Ojeda", start: 4, nights: 2, status: "pending" }] }
    ]
  },
  {
    category: "Suite",
    rows: [
      { room: "301", floor: 3, stays: [{ guest: "Ignacio Peralta", start: 1, nights: 4, status: "fully_paid" }] },
      { room: "302", floor: 3, stays: [{ guest: "Sofía Arrieta", start: 2, nights: 5, status: "checked_in" }] }
    ]
  }
];

const stayAt = (row: Row, dayIndex: number): Stay | undefined =>
  row.stays.find((stay) => dayIndex >= stay.start && dayIndex < stay.start + stay.nights);

const isBlockedAt = (row: Row, dayIndex: number) =>
  Boolean(row.blocked && dayIndex >= row.blocked.start && dayIndex < row.blocked.start + row.blocked.nights);

// Same hatch the grid paints on a blocked night.
const BLOCKED_CELL =
  "bg-[repeating-linear-gradient(45deg,#e2e8f0,#e2e8f0_6px,#f8fafc_6px,#f8fafc_12px)]";

export function OccupancyBoard() {
  let rowIndex = 0;

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-float lg:rounded-r-none lg:border-r-0">
      <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Operación</p>
          <p className="font-sans text-sm font-semibold text-slate-900">Planilla de ocupación</p>
        </div>
        <p className="numeric hidden text-xs text-slate-500 sm:block">10 de sept — 14 de sept</p>
      </div>

      <div className="overflow-x-auto">
        {/* table-fixed so the night columns keep an even width and the guest
            chips truncate, exactly the way the real grid behaves once the
            window is narrower than the stay names. */}
        <table className="w-full table-fixed border-separate border-spacing-0 font-sans">
          <thead>
            <tr>
              <th className="w-[38%] border-b border-r border-slate-200 bg-white px-3 py-2 text-left sm:w-[26%]">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Habitación</span>
              </th>
              {DAYS.map((day, index) => (
                <th
                  key={day}
                  className={`border-b border-r border-slate-200 px-1 py-2 text-center ${
                    index === TODAY_INDEX ? "bg-brand-50" : "bg-white"
                  }`}
                >
                  <span className="numeric text-[0.6875rem] font-semibold text-slate-700">{day}</span>
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {GROUPS.map((group) => (
              <Fragment key={group.category}>
                <tr>
                  <th
                    scope="row"
                    className="sticky left-0 z-20 border-b border-r border-slate-200 bg-slate-100 px-3 py-2 text-left"
                  >
                    <span className="text-xs font-semibold uppercase leading-tight tracking-wide text-slate-600">
                      {group.category}
                    </span>
                  </th>
                  {DAYS.map((day) => (
                    <td
                      key={`${group.category}-${day}`}
                      className="border-b border-r border-slate-200 bg-slate-100"
                    />
                  ))}
                </tr>

                {group.rows.map((row) => {
                  rowIndex += 1;
                  return (
                    <tr key={row.room} data-seq="row" style={{ ["--i" as string]: rowIndex + 2 }}>
                      <th
                        scope="row"
                        className="sticky left-0 z-20 border-b border-r border-slate-200 bg-white px-3 py-2 text-left align-top"
                      >
                        <p className="numeric text-sm font-medium text-slate-900">Hab. {row.room}</p>
                        <p className="text-xs text-slate-500">Piso {row.floor}</p>
                      </th>

                      {DAYS.map((day, index) => {
                        const dayNumber = index + 1;
                        const stay = stayAt(row, dayNumber);
                        const blocked = isBlockedAt(row, dayNumber);

                        if (blocked) {
                          return (
                            <td
                              key={`${row.room}-${day}`}
                              className={`border-b border-r border-slate-200 p-1 align-top ${BLOCKED_CELL}`}
                            >
                              <span className="block truncate px-2 py-1.5 text-xs font-medium text-slate-500">
                                Mantenimiento
                              </span>
                            </td>
                          );
                        }

                        return (
                          <td
                            key={`${row.room}-${day}`}
                            className="border-b border-r border-slate-200 p-1 align-top"
                          >
                            {stay ? (
                              <span
                                className={`block w-full truncate rounded-lg px-2 py-1.5 text-left text-xs font-semibold shadow-sm ${
                                  reservationStatusConfig[stay.status].className
                                }`}
                              >
                                {stay.guest}
                              </span>
                            ) : null}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* The legend is the app's own status vocabulary, not a marketing one. */}
      <ul className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-slate-200 px-4 py-3 text-xs text-slate-600">
        {(["checked_in", "fully_paid", "deposit_paid", "pending"] as ReservationStatus[]).map((status) => (
          <li key={status} className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className={`h-3 w-4 rounded ${reservationStatusConfig[status].className}`}
            />
            {reservationStatusConfig[status].label}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default OccupancyBoard;
