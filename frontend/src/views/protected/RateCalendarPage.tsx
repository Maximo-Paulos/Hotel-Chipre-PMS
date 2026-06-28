import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { RateCalendarGrid } from "../../components/RateCalendarGrid";
import { RateEditorGrid } from "../../components/RateEditorGrid";
import { useCategories } from "../../hooks/useCategories";
import {
  addDaysIso,
  todayIso,
  useBulkUpsertRates,
  useCategoryDailyRates,
  useRateCalendar,
  useUpsertDailyRate,
  type SingleRateInput
} from "../../hooks/useRateCalendar";

const WINDOW_OPTIONS = [
  { days: 14, label: "2 semanas" },
  { days: 30, label: "30 días" },
  { days: 60, label: "60 días" }
];

const RANGE_LABEL = new Intl.DateTimeFormat("es-AR", { day: "2-digit", month: "short" });

const toNumberOrNull = (value: string): number | null => {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
};

const formatRange = (from: string, to: string) =>
  `${RANGE_LABEL.format(new Date(`${from}T00:00:00`))} – ${RANGE_LABEL.format(new Date(`${to}T00:00:00`))}`;

export function RateCalendarPage() {
  const categoriesQuery = useCategories();
  const categories = useMemo(() => categoriesQuery.data ?? [], [categoriesQuery.data]);
  const [categoryId, setCategoryId] = useState<number | null>(null);

  // Date window (Booking-style): a start date + a span, navigable with prev/next.
  const [windowStart, setWindowStart] = useState<string>(() => todayIso());
  const [windowDays, setWindowDays] = useState<number>(14);
  const dateFrom = windowStart;
  const dateTo = useMemo(() => addDaysIso(windowStart, windowDays - 1), [windowStart, windowDays]);

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

  // Bulk "apply to range" panel (collapsed by default to keep the view clean).
  const [showBulk, setShowBulk] = useState(false);
  const [showChannels, setShowChannels] = useState(false);
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
      { onError: (err) => setSaveError(err.message) }
    );
  };

  const inputClass =
    "rounded-lg border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";
  const focusRing =
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1";
  const navBtn =
    "inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition-colors hover:bg-slate-50 disabled:opacity-50 " +
    focusRing;

  return (
    <div className="space-y-5" data-testid="rate-calendar-page">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
        <h1 className="text-2xl font-semibold text-slate-900">Tarifas y disponibilidad</h1>
        <p className="text-sm text-slate-600">
          Editá el precio de cada categoría por fecha, directo en la planilla.
        </p>
      </header>

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

      {/* Toolbar: category + date window navigation, all in one row. */}
      {categories.length > 0 ? (
        <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm lg:flex-row lg:items-center lg:justify-between">
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <span className="font-medium">Categoría</span>
            <select
              data-testid="rate-calendar-category"
              className={inputClass}
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

          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className={navBtn} onClick={() => setWindowStart((s) => addDaysIso(s, -windowDays))} aria-label="Período anterior">
              ‹
            </button>
            <input
              type="date"
              className={inputClass}
              value={windowStart}
              onChange={(event) => event.target.value && setWindowStart(event.target.value)}
            />
            <button type="button" className={navBtn} onClick={() => setWindowStart((s) => addDaysIso(s, windowDays))} aria-label="Período siguiente">
              ›
            </button>
            <button
              type="button"
              className={
                "inline-flex h-9 items-center rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-600 shadow-sm hover:bg-slate-50 " +
                focusRing
              }
              onClick={() => setWindowStart(todayIso())}
            >
              Hoy
            </button>
            <div className="ml-1 inline-flex overflow-hidden rounded-lg border border-slate-200">
              {WINDOW_OPTIONS.map((opt) => (
                <button
                  key={opt.days}
                  type="button"
                  aria-pressed={windowDays === opt.days}
                  onClick={() => setWindowDays(opt.days)}
                  className={
                    windowDays === opt.days
                      ? "bg-brand-600 px-3 py-2 text-xs font-semibold text-white " + focusRing
                      : "bg-white px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50 " + focusRing
                  }
                >
                  {opt.label}
                </button>
              ))}
            </div>
            {calendarQuery.isFetching || dailyRatesQuery.isFetching ? (
              <span className="text-xs text-slate-400">Actualizando…</span>
            ) : null}
          </div>
        </div>
      ) : null}

      {calendarQuery.data?.meta.total_rooms === 0 ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          La categoría no tiene habitaciones activas: podés cargar precios, pero la disponibilidad real es cero.
        </div>
      ) : null}

      {dailyRatesQuery.isLoading ? (
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">Cargando planilla…</div>
      ) : null}

      {dailyRatesQuery.isError ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          No se pudo cargar la planilla: {(dailyRatesQuery.error as Error).message}
        </div>
      ) : null}

      {/* Primary tool: editable per-date grid. */}
      {selectedCategory && dailyRatesQuery.data ? (
        <section className="space-y-2" data-testid="rate-editor-section">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium text-slate-700">
              {selectedCategory.name} · <span className="text-slate-400">{formatRange(dateFrom, dateTo)}</span>
            </p>
            <div className="flex items-center gap-3">
              {cellSave.isPending ? (
                <span className="text-xs font-medium text-slate-500">Guardando…</span>
              ) : cellSave.isSuccess && !cellError ? (
                <span className="text-xs font-medium text-emerald-600">Guardado ✓</span>
              ) : null}
              <button
                type="button"
                onClick={() => setShowBulk((v) => !v)}
                aria-expanded={showBulk}
                aria-controls="rate-bulk-panel"
                className={
                  "rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 shadow-sm hover:bg-slate-50 " +
                  focusRing
                }
              >
                {showBulk ? "Ocultar carga masiva" : "Aplicar a un rango"}
              </button>
            </div>
          </div>

          {cellError ? <p className="rounded-md bg-rose-50 p-2 text-sm text-rose-700">{cellError}</p> : null}

          {showBulk ? (
            <form
              onSubmit={handleSaveRates}
              data-testid="rate-editor"
              id="rate-bulk-panel"
              className="rounded-lg border border-slate-200 bg-slate-50/60 p-3"
            >
              <p className="mb-3 text-xs text-slate-500">
                Aplica un mismo precio a todas las fechas del rango (sobrescribe). El precio base es obligatorio;
                <span className="font-medium"> un campo opcional vacío borra ese precio</span> en todo el rango.
              </p>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                  Desde
                  <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className={inputClass} />
                </label>
                <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                  Hasta
                  <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className={inputClass} />
                </label>
                <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                  Precio base *
                  <input type="number" min={0} step="0.01" value={basePrice} onChange={(e) => setBasePrice(e.target.value)} placeholder="0.00" className={inputClass} />
                </label>
                <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                  Efectivo
                  <input type="number" min={0} step="0.01" value={priceCash} onChange={(e) => setPriceCash(e.target.value)} placeholder="opcional" className={inputClass} />
                </label>
                <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                  Transferencia
                  <input type="number" min={0} step="0.01" value={priceTransfer} onChange={(e) => setPriceTransfer(e.target.value)} placeholder="opcional" className={inputClass} />
                </label>
                <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                  Mercado Pago
                  <input type="number" min={0} step="0.01" value={priceMercadopago} onChange={(e) => setPriceMercadopago(e.target.value)} placeholder="opcional" className={inputClass} />
                </label>
              </div>
              {saveError ? <p className="mt-3 rounded-md bg-rose-50 p-2 text-sm text-rose-700">{saveError}</p> : null}
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
                  {bulkSave.isPending ? "Guardando…" : "Aplicar al rango"}
                </button>
              </div>
            </form>
          ) : null}

          <RateEditorGrid
            dailyRates={dailyRatesQuery.data}
            calendar={calendarQuery.data}
            currencyCode={calendarQuery.data?.meta.hotel_currency_code ?? "ARS"}
            onSaveCell={handleSaveCell}
            disabled={cellSave.isPending}
          />

          {/* Legend */}
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 px-1 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-emerald-500" /> Disponible
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-rose-400" /> Cerrado / sin cupo
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="italic text-slate-400">cursiva</span> precio heredado (aún no fijado para esa fecha)
            </span>
            <span>Editá una celda y salí del campo (o Enter) para guardar.</span>
          </div>
        </section>
      ) : null}

      {/* Secondary, collapsible: read-only OTA channel view. */}
      {calendarQuery.data ? (
        <section className="space-y-2">
          <button
            type="button"
            onClick={() => setShowChannels((v) => !v)}
            aria-expanded={showChannels}
            aria-controls="rate-channel-grid"
            className={
              "flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 text-left shadow-sm hover:bg-slate-50 " +
              focusRing
            }
          >
            <span>
              <span className="text-sm font-semibold text-slate-900">Canales OTA (lectura)</span>
              <span className="ml-2 text-xs text-slate-500">Directo · Booking · Expedia — tarifas y restricciones publicadas</span>
            </span>
            <span className="text-slate-400">{showChannels ? "▲" : "▼"}</span>
          </button>
          {showChannels ? (
            <div id="rate-channel-grid">
              <RateCalendarGrid calendar={calendarQuery.data} />
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
