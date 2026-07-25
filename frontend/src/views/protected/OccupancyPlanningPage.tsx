import { useEffect, useMemo, useState } from "react";

import { OccupancyGrid } from "../../components/OccupancyGrid";
import { useReservationDrawer } from "../../hooks/useReservationDrawer";
import { addDaysIso, todayIso } from "../../hooks/useRateCalendar";
import { useOccupancyGrid, usePrefetchOccupancyGrid } from "../../hooks/useReservations";

const WINDOW_DAYS = 30;

function buildDayRange(from: string, count: number): string[] {
  return Array.from({ length: count }, (_, i) => addDaysIso(from, i));
}

const RANGE_LABEL = new Intl.DateTimeFormat("es-AR", { day: "2-digit", month: "short", year: "numeric" });

export function OccupancyPlanningPage() {
  const [windowStart, setWindowStart] = useState(todayIso());
  const windowEnd = useMemo(() => addDaysIso(windowStart, WINDOW_DAYS), [windowStart]);
  const days = useMemo(() => buildDayRange(windowStart, WINDOW_DAYS), [windowStart]);
  const today = todayIso();

  const gridQuery = useOccupancyGrid(windowStart, windowEnd);
  const prefetch = usePrefetchOccupancyGrid();
  const { openReservation } = useReservationDrawer();

  // Prefetch the previous/next windows so ±30 navigation feels instant --
  // the "infinite calendar" the plan asks for, without virtualized scroll.
  useEffect(() => {
    const prevStart = addDaysIso(windowStart, -WINDOW_DAYS);
    const nextStart = addDaysIso(windowStart, WINDOW_DAYS);
    prefetch(prevStart, addDaysIso(prevStart, WINDOW_DAYS));
    prefetch(nextStart, addDaysIso(nextStart, WINDOW_DAYS));
  }, [windowStart, prefetch]);

  return (
    <div className="space-y-4" data-testid="occupancy-planning-page">
      <header className="flex flex-col gap-3 rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-200 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Planilla de ocupación</h1>
          <p className="mt-1 text-sm text-slate-600">
            {RANGE_LABEL.format(new Date(`${windowStart}T00:00:00`))} — {RANGE_LABEL.format(new Date(`${addDaysIso(windowStart, WINDOW_DAYS - 1)}T00:00:00`))}
            {gridQuery.isFetching ? " · Actualizando..." : ""}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            data-testid="occupancy-prev-window"
            onClick={() => setWindowStart((current) => addDaysIso(current, -WINDOW_DAYS))}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
          >
            ← 30 días
          </button>
          <button
            type="button"
            onClick={() => setWindowStart(today)}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
          >
            Hoy
          </button>
          <button
            type="button"
            data-testid="occupancy-next-window"
            onClick={() => setWindowStart((current) => addDaysIso(current, WINDOW_DAYS))}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
          >
            30 días →
          </button>
        </div>
      </header>

      {gridQuery.isLoading ? (
        <div className="rounded-3xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">Cargando planilla...</div>
      ) : null}

      {gridQuery.isError ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          No se pudo cargar la planilla: {(gridQuery.error as Error).message}
        </div>
      ) : null}

      {gridQuery.data && gridQuery.data.rooms.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-600 shadow-sm">
          No hay habitaciones cargadas para mostrar la planilla.
        </div>
      ) : null}

      {gridQuery.data && gridQuery.data.rooms.length > 0 ? (
        <OccupancyGrid data={gridQuery.data} days={days} todayIso={today} onSelectReservation={openReservation} />
      ) : null}
    </div>
  );
}
