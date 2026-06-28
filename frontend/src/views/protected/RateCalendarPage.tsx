import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { RateCalendarGrid } from "../../components/RateCalendarGrid";
import { RateEditorGrid } from "../../components/RateEditorGrid";
import { useCategories } from "../../hooks/useCategories";
import {
  todayIso,
  useBulkUpsertRates,
  useCategoryDailyRates,
  useRateCalendar,
  useUpsertDailyRate,
  type SingleRateInput
} from "../../hooks/useRateCalendar";

const RANGE_LABEL = new Intl.DateTimeFormat("es-AR", { day: "2-digit", month: "short", year: "numeric" });

const toNumberOrNull = (value: string): number | null => {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
};

const formatRange = (from: string, to: string) =>
  `${RANGE_LABEL.format(new Date(`${from}T00:00:00`))} -> ${RANGE_LABEL.format(new Date(`${to}T00:00:00`))}`;

const yearStart = (year: number) => {
  const today = todayIso();
  const currentYear = Number(today.slice(0, 4));
  return year === currentYear ? today : `${year}-01-01`;
};

const yearEnd = (year: number) => `${year}-12-31`;

function Pill({ children, tone = "default" }: { children: React.ReactNode; tone?: "default" | "blue" | "green" | "amber" | "violet" }) {
  const styles = {
    default: "border-slate-200 bg-slate-100 text-slate-700",
    blue: "border-blue-200 bg-blue-50 text-blue-700",
    green: "border-emerald-200 bg-emerald-50 text-emerald-700",
    amber: "border-amber-200 bg-amber-50 text-amber-700",
    violet: "border-violet-200 bg-violet-50 text-violet-700"
  };
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${styles[tone]}`}>
      {children}
    </span>
  );
}

export function RateCalendarPage() {
  const categoriesQuery = useCategories();
  const categories = useMemo(() => categoriesQuery.data ?? [], [categoriesQuery.data]);
  const [categoryId, setCategoryId] = useState<number | null>(null);

  const currentYear = Number(todayIso().slice(0, 4));
  const yearOptions = useMemo(() => [currentYear, currentYear + 1, currentYear + 2], [currentYear]);
  const [selectedYear, setSelectedYear] = useState(currentYear);
  const dateFrom = useMemo(() => yearStart(selectedYear), [selectedYear]);
  const dateTo = useMemo(() => yearEnd(selectedYear), [selectedYear]);

  useEffect(() => {
    if (categories.length === 0) {
      setCategoryId(null);
      return;
    }
    setCategoryId((current) =>
      current && categories.some((c) => c.id === current) ? current : categories[0]?.id ?? null
    );
  }, [categories]);

  const selectedCategory = useMemo(
    () => categories.find((c) => c.id === categoryId) ?? null,
    [categories, categoryId]
  );

  const calendarQuery = useRateCalendar(categoryId, dateFrom, dateTo);
  const dailyRatesQuery = useCategoryDailyRates(categoryId, dateFrom, dateTo);
  const cellSave = useUpsertDailyRate(categoryId);
  const bulkSave = useBulkUpsertRates(categoryId);

  const [cellError, setCellError] = useState<string | null>(null);
  const handleSaveCell = (payload: SingleRateInput) => {
    setCellError(null);
    cellSave.mutate(payload, { onError: (err) => setCellError(err.message) });
  };

  const [fromDate, setFromDate] = useState(dateFrom);
  const [toDate, setToDate] = useState(dateTo);
  const [basePrice, setBasePrice] = useState("");
  const [priceCash, setPriceCash] = useState("");
  const [priceTransfer, setPriceTransfer] = useState("");
  const [priceMercadopago, setPriceMercadopago] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    setFromDate(dateFrom);
    setToDate(dateTo);
  }, [dateFrom, dateTo]);

  const handleSaveRates = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaveError(null);
    const price = toNumberOrNull(basePrice);
    if (price === null) {
      setSaveError("Ingresá un precio base válido (>= 0).");
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
      { onError: (err) => setSaveError(err.message) }
    );
  };

  const inputClass =
    "h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm shadow-sm outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100";
  const labelClass = "flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500";
  const currencyCode = calendarQuery.data?.meta.hotel_currency_code ?? "ARS";
  const totalRooms = calendarQuery.data?.meta.total_rooms ?? null;

  return (
    <div className="space-y-4" data-testid="rate-calendar-page">
      <header className="rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <div className="grid gap-4 2xl:grid-cols-[1fr_auto] 2xl:items-end">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">Calendario de tarifas y disponibilidad</h1>
            <div className="mt-2 flex flex-wrap gap-2">
              <Pill tone="blue">Moneda principal: {currencyCode}</Pill>
              <Pill tone="violet">Vista anual: {selectedYear}</Pill>
              <Pill tone="amber">Canales OTA en lectura</Pill>
            </div>
          </div>

          {categories.length > 0 ? (
            <div className="grid w-full gap-3 sm:grid-cols-[minmax(220px,1fr)_140px] 2xl:w-auto 2xl:grid-cols-[minmax(260px,420px)_140px]">
              <label className={labelClass}>
                Categoría
                <select
                  data-testid="rate-calendar-category"
                  className={`${inputClass} normal-case tracking-normal text-slate-900`}
                  value={categoryId ?? ""}
                  onChange={(event) => setCategoryId(Number(event.target.value))}
                  disabled={categoriesQuery.isLoading}
                >
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name} · {category.code}
                    </option>
                  ))}
                </select>
              </label>

              <label className={labelClass}>
                Año
                <select
                  className={`${inputClass} normal-case tracking-normal text-slate-900`}
                  value={selectedYear}
                  onChange={(event) => setSelectedYear(Number(event.target.value))}
                >
                  {yearOptions.map((year) => (
                    <option key={year} value={year}>
                      {year}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          ) : null}
        </div>
      </header>

      {categoriesQuery.isError ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          No se pudieron cargar las categorías: {(categoriesQuery.error as Error).message}
        </div>
      ) : null}

      {!categoriesQuery.isLoading && !categoriesQuery.isError && categories.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-600 shadow-sm">
          <p>No hay categorías configuradas para mostrar el calendario.</p>
          <Link to="/habitaciones" className="mt-2 inline-flex font-semibold text-brand-700 underline underline-offset-2">
            Ir a Habitaciones
          </Link>
        </div>
      ) : null}

      {calendarQuery.data?.meta.total_rooms === 0 ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          La categoría no tiene habitaciones activas: podés cargar precios, pero la disponibilidad real es cero.
        </div>
      ) : null}

      {dailyRatesQuery.isLoading ? (
        <div className="rounded-3xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">Cargando calendario...</div>
      ) : null}

      {dailyRatesQuery.isError ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          No se pudo cargar la planilla: {(dailyRatesQuery.error as Error).message}
        </div>
      ) : null}

      {selectedCategory && dailyRatesQuery.data ? (
        <main className="space-y-4">
          <section className="overflow-hidden rounded-3xl bg-white shadow-sm ring-1 ring-slate-200" data-testid="rate-editor-section">
            <div className="grid gap-3 border-b border-slate-200 p-4 lg:grid-cols-[1fr_auto] lg:items-start">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-bold text-slate-900">{selectedCategory.name}</h2>
                  <Pill tone="green">{formatRange(dateFrom, dateTo)}</Pill>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {selectedCategory.code}
                  {totalRooms !== null ? ` · ${totalRooms} habitaciones activas` : ""}
                  {calendarQuery.isFetching || dailyRatesQuery.isFetching ? " · Actualizando..." : ""}
                </p>
              </div>

              <div className="flex flex-col items-stretch gap-2 sm:items-end">
                <button
                  type="button"
                  disabled
                  className="rounded-2xl bg-slate-200 px-6 py-3 text-sm font-bold text-slate-500"
                  title="La publicación a canales se habilita desde integraciones conectadas."
                >
                  Sin cambios pendientes
                </button>
                <div className="flex flex-wrap justify-end gap-2">
                  {cellSave.isPending ? <Pill>Guardando...</Pill> : null}
                  {cellSave.isSuccess && !cellError ? <Pill tone="green">Guardado</Pill> : null}
                  <Pill tone="amber">Mapeos OTA</Pill>
                </div>
              </div>
            </div>

            {cellError ? <p className="mx-4 mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{cellError}</p> : null}

            <RateEditorGrid
              dailyRates={dailyRatesQuery.data}
              calendar={calendarQuery.data}
              currencyCode={currencyCode}
              onSaveCell={handleSaveCell}
              disabled={cellSave.isPending}
            />

            {calendarQuery.data ? (
              <div className="border-t-2 border-slate-200">
                <RateCalendarGrid calendar={calendarQuery.data} showHeader={false} showSummaryRows={false} />
              </div>
            ) : null}

            <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-slate-200 px-4 py-3 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-full bg-emerald-500" /> Disponible
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-full bg-rose-400" /> Cerrado / sin cupo
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="italic text-slate-400">cursiva</span> precio heredado
              </span>
              <span>Enter avanza por la fila.</span>
            </div>
          </section>

          <section className="rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
            <div className="flex flex-col gap-3 2xl:flex-row 2xl:items-start 2xl:justify-between">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Edición masiva</h2>
                <p className="mt-1 text-xs text-slate-500">Aplicá un precio a todas las fechas del rango seleccionado.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Pill tone="blue">Rango</Pill>
                <Pill>Hotel / tarifa diaria</Pill>
              </div>
            </div>

            <form onSubmit={handleSaveRates} data-testid="rate-editor" id="rate-bulk-panel" className="mt-4">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-7">
                <label className={labelClass}>
                  Desde
                  <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className={`${inputClass} normal-case tracking-normal text-slate-900`} />
                </label>
                <label className={labelClass}>
                  Hasta
                  <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className={`${inputClass} normal-case tracking-normal text-slate-900`} />
                </label>
                <label className={labelClass}>
                  Canal
                  <input className={`${inputClass} normal-case tracking-normal text-slate-500`} value="Venta directa / Hotel" readOnly />
                </label>
                <label className={labelClass}>
                  Campo
                  <input className={`${inputClass} normal-case tracking-normal text-slate-500`} value="Precio base y medios" readOnly />
                </label>
                <label className={labelClass}>
                  Precio base *
                  <input type="number" min={0} step="0.01" value={basePrice} onChange={(e) => setBasePrice(e.target.value)} placeholder="0.00" className={`${inputClass} normal-case tracking-normal text-slate-900`} />
                </label>
                <label className={labelClass}>
                  Efectivo
                  <input type="number" min={0} step="0.01" value={priceCash} onChange={(e) => setPriceCash(e.target.value)} placeholder="opcional" className={`${inputClass} normal-case tracking-normal text-slate-900`} />
                </label>
                <label className={labelClass}>
                  Transferencia
                  <input type="number" min={0} step="0.01" value={priceTransfer} onChange={(e) => setPriceTransfer(e.target.value)} placeholder="opcional" className={`${inputClass} normal-case tracking-normal text-slate-900`} />
                </label>
                <label className={labelClass}>
                  Mercado Pago
                  <input type="number" min={0} step="0.01" value={priceMercadopago} onChange={(e) => setPriceMercadopago(e.target.value)} placeholder="opcional" className={`${inputClass} normal-case tracking-normal text-slate-900`} />
                </label>
              </div>

              {saveError ? <p className="mt-3 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{saveError}</p> : null}
              {bulkSave.isSuccess && !saveError ? (
                <p className="mt-3 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-700">
                  Tarifas guardadas: {bulkSave.data.created} creadas, {bulkSave.data.updated} actualizadas.
                </p>
              ) : null}

              <div className="mt-4 flex flex-wrap justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setBasePrice("");
                    setPriceCash("");
                    setPriceTransfer("");
                    setPriceMercadopago("");
                    setSaveError(null);
                  }}
                  className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
                >
                  Limpiar
                </button>
                <button
                  type="submit"
                  disabled={bulkSave.isPending}
                  data-testid="rate-editor-save"
                  className="rounded-2xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-70"
                >
                  {bulkSave.isPending ? "Guardando..." : "Aplicar al calendario"}
                </button>
              </div>
            </form>
          </section>
        </main>
      ) : null}
    </div>
  );
}
