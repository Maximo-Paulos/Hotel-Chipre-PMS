import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { RateCalendarGrid } from "../../components/RateCalendarGrid";
import { useCategories } from "../../hooks/useCategories";
import { useRateCalendar } from "../../hooks/useRateCalendar";

const currentYear = new Date().getFullYear();
const yearOptions = [currentYear, currentYear + 1, currentYear + 2];

export function RateCalendarPage() {
  const categoriesQuery = useCategories();
  const categories = useMemo(() => categoriesQuery.data ?? [], [categoriesQuery.data]);
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [year, setYear] = useState(currentYear);

  useEffect(() => {
    if (categories.length === 0) {
      setCategoryId(null);
      return;
    }

    setCategoryId((current) => {
      if (current && categories.some((category) => category.id === current)) {
        return current;
      }
      return categories[0]?.id ?? null;
    });
  }, [categories]);

  const selectedCategory = useMemo(
    () => categories.find((category) => category.id === categoryId) ?? null,
    [categories, categoryId]
  );

  const calendarQuery = useRateCalendar(categoryId, year);

  return (
    <div className="space-y-6" data-testid="rate-calendar-page">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
          <h1 className="text-2xl font-semibold text-slate-900">Calendario de tarifas y disponibilidad</h1>
          <p className="text-sm text-slate-600">
            Vista anual en modo lectura para revisar ocupación, tarifas y restricciones por canal.
          </p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          <label className="flex min-w-[220px] flex-col gap-1 text-sm text-slate-700">
            <span className="font-medium">Categoría</span>
            <select
              data-testid="rate-calendar-category"
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              value={categoryId ?? ""}
              onChange={(event) => setCategoryId(Number(event.target.value))}
              disabled={categoriesQuery.isLoading || categories.length === 0}
            >
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name} · {category.code}
                </option>
              ))}
            </select>
          </label>
          <label className="flex w-full min-w-[160px] flex-col gap-1 text-sm text-slate-700 sm:w-auto">
            <span className="font-medium">Año</span>
            <select
              data-testid="rate-calendar-year"
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              value={year}
              onChange={(event) => setYear(Number(event.target.value))}
            >
              {yearOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      {categoriesQuery.isLoading ? (
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">Cargando...</div>
      ) : null}

      {categoriesQuery.isError ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          No se pudieron cargar las categorías: {(categoriesQuery.error as Error).message}
        </div>
      ) : null}

      {!categoriesQuery.isLoading && !categoriesQuery.isError && categories.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-600 shadow-sm">
          <p>No hay categorías configuradas para mostrar el calendario.</p>
          <Link to="/habitaciones" className="mt-2 inline-flex font-semibold text-brand-700 underline underline-offset-2">
            Ir a Habitaciones
          </Link>
        </div>
      ) : null}

      {selectedCategory ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-slate-900">
                {selectedCategory.name} · {selectedCategory.code}
              </p>
              <p className="text-xs text-slate-500">
                {year === currentYear ? "Desde hoy hasta el cierre del año actual." : "Vista del año calendario completo."}
              </p>
            </div>
            {calendarQuery.isFetching ? <p className="text-xs text-slate-500">Cargando...</p> : null}
          </div>
        </div>
      ) : null}

      {calendarQuery.isLoading ? (
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">Cargando...</div>
      ) : null}

      {calendarQuery.isError ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          No se pudo cargar el calendario: {(calendarQuery.error as Error).message}
        </div>
      ) : null}

      {calendarQuery.data?.meta.total_rooms === 0 ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          La categoría no tiene habitaciones activas. El calendario muestra tarifas, pero la disponibilidad real es cero.
        </div>
      ) : null}

      {calendarQuery.data ? <RateCalendarGrid calendar={calendarQuery.data} /> : null}
    </div>
  );
}
