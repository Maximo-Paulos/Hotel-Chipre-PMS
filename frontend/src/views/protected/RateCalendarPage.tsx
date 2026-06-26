import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { RateCalendarGrid } from "../../components/RateCalendarGrid";
import { useCategories } from "../../hooks/useCategories";
import { useBulkUpsertRates, useRateCalendar, resolveRateCalendarRange } from "../../hooks/useRateCalendar";

const currentYear = new Date().getFullYear();
const yearOptions = [currentYear, currentYear + 1, currentYear + 2];

const toNumberOrNull = (value: string): number | null => {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
};

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
  const bulkSave = useBulkUpsertRates(categoryId);

  const defaultRange = useMemo(() => resolveRateCalendarRange(year), [year]);
  const [fromDate, setFromDate] = useState(defaultRange.dateFrom);
  const [toDate, setToDate] = useState(defaultRange.dateTo);
  const [basePrice, setBasePrice] = useState("");
  const [priceCash, setPriceCash] = useState("");
  const [priceTransfer, setPriceTransfer] = useState("");
  const [priceMercadopago, setPriceMercadopago] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    setFromDate(defaultRange.dateFrom);
    setToDate(defaultRange.dateTo);
  }, [defaultRange]);

  const handleSaveRates = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaveError(null);
    const price = toNumberOrNull(basePrice);
    if (price === null) {
      setSaveError("Ingresá un precio base válido (≥ 0).");
      return;
    }
    if (toDate < fromDate) {
      setSaveError("La fecha final debe ser mayor o igual a la inicial.");
      return;
    }
    bulkSave.mutate(
      {
        from_date: fromDate,
        to_date: toDate,
        price,
        price_cash: toNumberOrNull(priceCash),
        price_transfer: toNumberOrNull(priceTransfer),
        price_mercadopago: toNumberOrNull(priceMercadopago)
      },
      {
        onError: (err) => setSaveError(err.message)
      }
    );
  };

  return (
    <div className="space-y-6" data-testid="rate-calendar-page">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
          <h1 className="text-2xl font-semibold text-slate-900">Calendario de tarifas y disponibilidad</h1>
          <p className="text-sm text-slate-600">
            Revisá ocupación y tarifas por canal, y editá los precios diarios por rango de fechas.
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

      {selectedCategory ? (
        <form
          onSubmit={handleSaveRates}
          data-testid="rate-editor"
          className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
        >
          <p className="text-sm font-semibold text-slate-900">Editar precios por rango</p>
          <p className="mb-3 text-xs text-slate-500">
            Aplica el precio a todas las fechas del rango (upsert). El precio base es obligatorio; los precios por
            medio de pago son opcionales.
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <label className="flex flex-col gap-1 text-sm text-slate-700">
              <span className="font-medium">Desde</span>
              <input
                type="date"
                value={fromDate}
                onChange={(event) => setFromDate(event.target.value)}
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm text-slate-700">
              <span className="font-medium">Hasta</span>
              <input
                type="date"
                value={toDate}
                onChange={(event) => setToDate(event.target.value)}
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm text-slate-700">
              <span className="font-medium">Precio base *</span>
              <input
                type="number"
                min={0}
                step="0.01"
                value={basePrice}
                onChange={(event) => setBasePrice(event.target.value)}
                placeholder="0.00"
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm text-slate-700">
              <span className="font-medium">Precio efectivo</span>
              <input
                type="number"
                min={0}
                step="0.01"
                value={priceCash}
                onChange={(event) => setPriceCash(event.target.value)}
                placeholder="opcional"
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm text-slate-700">
              <span className="font-medium">Precio transferencia</span>
              <input
                type="number"
                min={0}
                step="0.01"
                value={priceTransfer}
                onChange={(event) => setPriceTransfer(event.target.value)}
                placeholder="opcional"
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm text-slate-700">
              <span className="font-medium">Precio Mercado Pago</span>
              <input
                type="number"
                min={0}
                step="0.01"
                value={priceMercadopago}
                onChange={(event) => setPriceMercadopago(event.target.value)}
                placeholder="opcional"
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </label>
          </div>
          {saveError ? (
            <p className="mt-3 rounded-md bg-rose-50 p-2 text-sm text-rose-700">{saveError}</p>
          ) : null}
          {bulkSave.isSuccess && !saveError ? (
            <p className="mt-3 rounded-md bg-emerald-50 p-2 text-sm text-emerald-700">
              Tarifas guardadas: {bulkSave.data.created} creadas, {bulkSave.data.updated} actualizadas.
            </p>
          ) : null}
          <div className="mt-3 flex justify-end">
            <button
              type="submit"
              disabled={bulkSave.isPending}
              data-testid="rate-editor-save"
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-70"
            >
              {bulkSave.isPending ? "Guardando..." : "Guardar tarifas"}
            </button>
          </div>
        </form>
      ) : null}

      {calendarQuery.data ? <RateCalendarGrid calendar={calendarQuery.data} /> : null}
    </div>
  );
}
