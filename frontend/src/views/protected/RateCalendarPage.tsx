import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { RateCalendarGrid } from "../../components/RateCalendarGrid";
import { RateEditorGrid, type PriceField } from "../../components/RateEditorGrid";
import { RateEditorMobileCards } from "../../components/RateEditorMobileCards";
import { useCategories } from "../../hooks/useCategories";
import { useEffectivePermissions } from "../../hooks/usePermissions";
import {
  todayIso,
  useBulkUpsertRates,
  useBulkUpdateRateField,
  useCategoryDailyRates,
  usePricePeriods,
  usePricePeriodMutations,
  useRateCalendar,
  useUpsertDailyRate,
  type SingleRateInput,
  type PricePeriodInput
} from "../../hooks/useRateCalendar";

const RANGE_LABEL = new Intl.DateTimeFormat("es-AR", { day: "2-digit", month: "short", year: "numeric" });

const WEEKDAY_FILTERS = [
  { value: 1, label: "Lun" },
  { value: 2, label: "Mar" },
  { value: 3, label: "Mie" },
  { value: 4, label: "Jue" },
  { value: 5, label: "Vie" },
  { value: 6, label: "Sab" },
  { value: 0, label: "Dom" }
];

const PRICE_FIELD_LABEL: Record<PriceField, string> = {
  price: "Precio base",
  price_cash: "Efectivo",
  price_transfer: "Transferencia",
  price_mercadopago: "Mercado Pago",
  price_paypal: "PayPal",
  price_credit_card: "Tarjeta de crédito"
};

const BULK_FIELD_OPTIONS: Array<{ value: PriceField; label: string }> = [
  { value: "price", label: "Precio base" },
  { value: "price_cash", label: "Efectivo" },
  { value: "price_transfer", label: "Transferencia" },
  { value: "price_mercadopago", label: "Mercado Pago" },
  { value: "price_paypal", label: "PayPal" },
  { value: "price_credit_card", label: "Tarjeta de crédito" }
];

const BULK_ACTION_OPTIONS = [
  { value: "set", label: "Fijar valor" },
  { value: "amount_delta", label: "Ajustar $" },
  { value: "percent_delta", label: "Ajustar %" }
] as const;

const toNumberOrNull = (value: string): number | null => {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
};

const formatRange = (from: string, to: string) =>
  `${RANGE_LABEL.format(new Date(`${from}T00:00:00`))} -> ${RANGE_LABEL.format(new Date(`${to}T00:00:00`))}`;

const getIsoWeekday = (iso: string) => new Date(`${iso}T00:00:00`).getDay();

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
  const { hasPermission } = useEffectivePermissions();
  const canEditRates = hasPermission("rates:update");
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
  const bulkFieldSave = useBulkUpdateRateField(categoryId);
  const periodsQuery = usePricePeriods(categoryId);
  const periodMutations = usePricePeriodMutations(categoryId);
  const [periodForm, setPeriodForm] = useState<PricePeriodInput>({
    category_id: categoryId ?? 0,
    name: "",
    start_date: dateFrom,
    end_date: dateTo,
    price_per_night: 0,
    priority: 0,
    is_active: true
  });

  const [cellError, setCellError] = useState<string | null>(null);
  const handleSaveCell = async (payload: SingleRateInput) => {
    setCellError(null);
    try {
      await cellSave.mutateAsync(payload);
    } catch (err: unknown) {
      setCellError(err instanceof Error ? err.message : "No se pudo guardar la tarifa.");
    }
  };

  const [fromDate, setFromDate] = useState(dateFrom);
  const [toDate, setToDate] = useState(dateTo);
  const [basePrice, setBasePrice] = useState("");
  const [priceCash, setPriceCash] = useState("");
  const [priceTransfer, setPriceTransfer] = useState("");
  const [priceMercadopago, setPriceMercadopago] = useState("");
  const [pricePaypal, setPricePaypal] = useState("");
  const [priceCreditCard, setPriceCreditCard] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [bulkMode, setBulkMode] = useState<"range" | "weekdays">("range");
  const [bulkEditKind, setBulkEditKind] = useState<"all" | "field">("all");
  const [bulkField, setBulkField] = useState<PriceField>("price_transfer");
  const [bulkAction, setBulkAction] = useState<(typeof BULK_ACTION_OPTIONS)[number]["value"]>("set");
  const [bulkFieldValue, setBulkFieldValue] = useState("");
  const [selectedWeekdays, setSelectedWeekdays] = useState<number[]>([]);
  const [selectionAnchor, setSelectionAnchor] = useState<{ field: PriceField; date: string } | null>(null);
  const [selectedRange, setSelectedRange] = useState<{
    field: PriceField;
    startDate: string;
    endDate: string;
  } | null>(null);

  useEffect(() => {
    setFromDate(dateFrom);
    setToDate(dateTo);
    setPeriodForm((current) => ({ ...current, category_id: categoryId ?? 0, start_date: dateFrom, end_date: dateTo }));
  }, [dateFrom, dateTo, categoryId]);

  const handleCreatePeriod = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!categoryId || !periodForm.name.trim() || periodForm.end_date < periodForm.start_date) return;
    try {
      await periodMutations.create.mutateAsync({ ...periodForm, category_id: categoryId, name: periodForm.name.trim() });
    } catch {
      // The mutation state renders the error below the form.
    }
  };

  const rangeRows = useMemo(
    () => (dailyRatesQuery.data ?? []).filter((row) => row.date >= fromDate && row.date <= toDate),
    [dailyRatesQuery.data, fromDate, toDate]
  );

  const weekdaySet = useMemo(() => new Set(selectedWeekdays), [selectedWeekdays]);

  const excludedDates = useMemo(() => {
    if (bulkMode !== "weekdays") return [];
    return rangeRows.filter((row) => !weekdaySet.has(getIsoWeekday(row.date))).map((row) => row.date);
  }, [bulkMode, rangeRows, weekdaySet]);

  const affectedDateCount = bulkMode === "weekdays" ? rangeRows.length - excludedDates.length : rangeRows.length;

  const setNumberInput = (setter: React.Dispatch<React.SetStateAction<string>>, value?: number | null) => {
    setter(value === null || value === undefined ? "" : String(value));
  };

  const handleSelectCell = (field: PriceField, date: string) => {
    const row = dailyRatesQuery.data?.find((item) => item.date === date);
    if (row) {
      setNumberInput(setBasePrice, row.price);
      setNumberInput(setPriceCash, row.price_cash);
      setNumberInput(setPriceTransfer, row.price_transfer);
      setNumberInput(setPriceMercadopago, row.price_mercadopago);
      setNumberInput(setPricePaypal, row.price_paypal);
      setNumberInput(setPriceCreditCard, row.price_credit_card);
    }

    if (selectionAnchor && selectionAnchor.field === field) {
      const startDate = selectionAnchor.date <= date ? selectionAnchor.date : date;
      const endDate = selectionAnchor.date <= date ? date : selectionAnchor.date;
      setSelectedRange({ field, startDate, endDate });
      setFromDate(startDate);
      setToDate(endDate);
      setSelectionAnchor(null);
      return;
    }

    setSelectionAnchor({ field, date });
    setSelectedRange({ field, startDate: date, endDate: date });
    setFromDate(date);
    setToDate(date);
  };

  const toggleWeekday = (weekday: number) => {
    setSelectedWeekdays((current) =>
      current.includes(weekday)
        ? current.filter((item) => item !== weekday)
        : [...current, weekday].sort((a, b) => a - b)
    );
  };

  const handleSaveRates = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canEditRates) return;
    setSaveError(null);
    const price = toNumberOrNull(basePrice);
    if (bulkEditKind === "all" && price === null) {
      setSaveError("Ingresá un precio base válido (>= 0).");
      return;
    }
    if (toDate < fromDate) {
      setSaveError("La fecha final debe ser mayor o igual a la inicial.");
      return;
    }
    if (bulkMode === "weekdays" && selectedWeekdays.length === 0) {
      setSaveError("Elegí al menos un día de semana para aplicar la edición.");
      return;
    }
    if (bulkMode === "weekdays" && affectedDateCount <= 0) {
      setSaveError("No hay fechas afectadas dentro del rango y los días elegidos.");
      return;
    }
    if (bulkEditKind === "field") {
      const value = Number(bulkFieldValue.trim());
      if (!Number.isFinite(value)) {
        setSaveError("Ingresá un valor válido para la edición rápida.");
        return;
      }
      try {
        await bulkFieldSave.mutateAsync({
          from_date: fromDate,
          to_date: toDate,
          field: bulkField,
          mode: bulkAction,
          value,
          exclude_dates: excludedDates
        });
      } catch (err: unknown) {
        setSaveError(err instanceof Error ? err.message : "No se pudieron guardar las tarifas.");
      }
      return;
    }

    if (price === null) {
      setSaveError("Ingresá un precio base válido (>= 0).");
      return;
    }

    try {
      await bulkSave.mutateAsync({
        from_date: fromDate,
        to_date: toDate,
        price,
        price_cash: toNumberOrNull(priceCash),
        price_transfer: toNumberOrNull(priceTransfer),
        price_mercadopago: toNumberOrNull(priceMercadopago),
        price_credit_card: toNumberOrNull(priceCreditCard),
        exclude_dates: excludedDates
      });
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : "No se pudieron guardar las tarifas.");
    }
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
                  {!canEditRates ? <Pill>Solo lectura</Pill> : null}
                  <Pill tone="amber">Mapeos OTA</Pill>
                </div>
              </div>
            </div>

            {cellError ? <p className="mx-4 mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{cellError}</p> : null}

            {/* Dense spreadsheet grid: needs real width for a day-per-column
                layout, so it's desktop/tablet only (md and up). */}
            <div className="hidden md:block">
              <RateEditorGrid
                dailyRates={dailyRatesQuery.data}
                calendar={calendarQuery.data}
                currencyCode={currencyCode}
                onSaveCell={handleSaveCell}
                onSelectCell={handleSelectCell}
                selectedRange={selectedRange}
                disabled={!canEditRates || cellSave.isPending}
              />
            </div>
            {/* Mobile alternative: card-per-day, step-through-the-week flow. */}
            <div className="md:hidden">
              <RateEditorMobileCards
                dailyRates={dailyRatesQuery.data}
                currencyCode={currencyCode}
                onSaveCell={handleSaveCell}
                disabled={!canEditRates || cellSave.isPending}
              />
            </div>

            {calendarQuery.data ? (
              <div className="border-t-2 border-slate-200">
                <RateCalendarGrid
                  calendar={calendarQuery.data}
                  showHeader={false}
                  showSummaryRows={false}
                  excludeProviderCodes={["direct"]}
                />
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
                <Pill tone="blue">{bulkMode === "weekdays" ? "Días de semana" : "Rango"}</Pill>
                <Pill>Hotel / tarifa diaria</Pill>
              </div>
            </div>

            <form onSubmit={handleSaveRates} data-testid="rate-editor" id="rate-bulk-panel" className="mt-4">
              {!canEditRates ? (
                <p className="mb-4 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600" role="status">
                  Tenés permiso para ver las tarifas, pero no para editarlas.
                </p>
              ) : null}
              <fieldset disabled={!canEditRates} className="contents">
              <div className="mb-4 flex flex-col gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-3 xl:flex-row xl:items-center xl:justify-between">
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setBulkMode("range")}
                    className={`rounded-xl px-3 py-2 text-sm font-semibold ${
                      bulkMode === "range"
                        ? "bg-blue-600 text-white"
                        : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    Rango
                  </button>
                  <button
                    type="button"
                    onClick={() => setBulkMode("weekdays")}
                    className={`rounded-xl px-3 py-2 text-sm font-semibold ${
                      bulkMode === "weekdays"
                        ? "bg-blue-600 text-white"
                        : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    Días de semana
                  </button>
                </div>

                {bulkMode === "weekdays" ? (
                  <div className="flex flex-wrap items-center gap-2">
                    {WEEKDAY_FILTERS.map((day) => {
                      const active = selectedWeekdays.includes(day.value);
                      return (
                        <button
                          key={day.value}
                          type="button"
                          aria-pressed={active}
                          onClick={() => toggleWeekday(day.value)}
                          className={`h-9 min-w-10 rounded-xl px-3 text-sm font-semibold ${
                            active
                              ? "bg-slate-900 text-white"
                              : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-100"
                          }`}
                        >
                          {day.label}
                        </button>
                      );
                    })}
                  </div>
                ) : null}

                <div className="text-xs font-medium text-slate-500">
                  {selectedRange ? (
                    <span>
                      Selección: {PRICE_FIELD_LABEL[selectedRange.field]} · {formatRange(selectedRange.startDate, selectedRange.endDate)}
                    </span>
                  ) : (
                    <span>Click en una celda para cargar sus importes; segundo click en la misma fila arma el rango.</span>
                  )}
                  <span className="ml-2 text-slate-700">
                    {affectedDateCount > 0 ? `${affectedDateCount} fechas afectadas` : "Sin fechas afectadas"}
                  </span>
                </div>
              </div>

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
                  Tipo de edición
                  <select
                    aria-label="Tipo de edición"
                    value={bulkEditKind}
                    onChange={(e) => setBulkEditKind(e.target.value as "all" | "field")}
                    className={`${inputClass} normal-case tracking-normal text-slate-900`}
                  >
                    <option value="all">Varios importes</option>
                    <option value="field">Un campo rápido</option>
                  </select>
                </label>
                {bulkEditKind === "field" ? (
                  <>
                    <label className={labelClass}>
                      Campo rápido
                      <select
                        aria-label="Campo rápido"
                        value={bulkField}
                        onChange={(e) => setBulkField(e.target.value as PriceField)}
                        className={`${inputClass} normal-case tracking-normal text-slate-900`}
                      >
                        {BULK_FIELD_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className={labelClass}>
                      Acción
                      <select
                        aria-label="Acción"
                        value={bulkAction}
                        onChange={(e) => setBulkAction(e.target.value as typeof bulkAction)}
                        className={`${inputClass} normal-case tracking-normal text-slate-900`}
                      >
                        {BULK_ACTION_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className={labelClass}>
                      Valor
                      <input
                        aria-label="Valor"
                        type="number"
                        step="0.01"
                        value={bulkFieldValue}
                        onChange={(e) => setBulkFieldValue(e.target.value)}
                        placeholder={bulkAction === "percent_delta" ? "Ej: -10" : "0.00"}
                        className={`${inputClass} normal-case tracking-normal text-slate-900`}
                      />
                    </label>
                  </>
                ) : (
                  <>
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
                    <label className={labelClass}>
                      PayPal
                      <input type="number" min={0} step="0.01" value={pricePaypal} onChange={(e) => setPricePaypal(e.target.value)} placeholder="opcional" className={`${inputClass} normal-case tracking-normal text-slate-900`} />
                    </label>
                    <label className={labelClass}>
                      Tarjeta de crédito
                      <input type="number" min={0} step="0.01" value={priceCreditCard} onChange={(e) => setPriceCreditCard(e.target.value)} placeholder="opcional" className={`${inputClass} normal-case tracking-normal text-slate-900`} />
                    </label>
                  </>
                )}
              </div>

              {saveError ? <p className="mt-3 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{saveError}</p> : null}
              {(bulkSave.isSuccess || bulkFieldSave.isSuccess) && !saveError ? (
                <p className="mt-3 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-700">
                  Tarifas guardadas: {(bulkFieldSave.data ?? bulkSave.data)?.created ?? 0} creadas,{" "}
                  {(bulkFieldSave.data ?? bulkSave.data)?.updated ?? 0} actualizadas.
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
                    setPricePaypal("");
                    setPriceCreditCard("");
                    setBulkFieldValue("");
                    setSaveError(null);
                    setSelectedWeekdays([]);
                    setSelectionAnchor(null);
                    setSelectedRange(null);
                  }}
                  className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
                >
                  Limpiar
                </button>
                <button
                  type="submit"
                  disabled={bulkSave.isPending || bulkFieldSave.isPending}
                  data-testid="rate-editor-save"
                  className="rounded-2xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-70"
                >
                  {bulkSave.isPending || bulkFieldSave.isPending ? "Guardando..." : "Aplicar al calendario"}
                </button>
              </div>
              </fieldset>
            </form>
          </section>

          <section className="rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-200" data-testid="price-periods-section">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Precio por temporada</h2>
                <p className="mt-1 text-xs text-slate-500">Definí precios para temporadas. Una tarifa diaria puntual gana sobre la temporada; la temporada gana sobre el precio base.</p>
              </div>
              {!canEditRates ? <Pill>Solo lectura</Pill> : null}
            </div>
            {periodsQuery.isError ? <p className="mt-3 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">No se pudieron cargar las temporadas.</p> : null}
            {periodsQuery.isLoading ? <p className="mt-3 text-sm text-slate-600">Cargando temporadas...</p> : null}
            {!periodsQuery.isLoading && !periodsQuery.isError && (periodsQuery.data ?? []).length === 0 ? <p className="mt-3 rounded-xl bg-slate-50 p-3 text-sm text-slate-600">No hay temporadas para esta categoría.</p> : null}
            <div className="mt-3 space-y-2">
              {(periodsQuery.data ?? []).map((period) => (
                <div key={period.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 px-3 py-2 text-sm">
                  <div>
                    <p className="font-semibold text-slate-900">{period.name} · {period.price_per_night} {currencyCode}</p>
                    <p className="text-xs text-slate-500">{period.start_date} → {period.end_date} · prioridad {period.priority} · {period.is_active ? "Activa" : "Inactiva"}</p>
                  </div>
                  {canEditRates ? <button type="button" className="rounded-lg border border-rose-200 px-3 py-1 text-xs font-semibold text-rose-700" onClick={() => void periodMutations.remove.mutateAsync(period.id).catch(() => undefined)} disabled={periodMutations.remove.isPending}>Eliminar</button> : null}
                </div>
              ))}
            </div>
            <form onSubmit={handleCreatePeriod} className="mt-4 grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-3 md:grid-cols-2 xl:grid-cols-6">
              <label className={labelClass}>Nombre<input required className={`${inputClass} normal-case tracking-normal text-slate-900`} value={periodForm.name} onChange={(event) => setPeriodForm((current) => ({ ...current, name: event.target.value }))} placeholder="Temporada alta" disabled={!canEditRates} /></label>
              <label className={labelClass}>Desde<input required type="date" className={`${inputClass} normal-case tracking-normal text-slate-900`} value={periodForm.start_date} onChange={(event) => setPeriodForm((current) => ({ ...current, start_date: event.target.value }))} disabled={!canEditRates} /></label>
              <label className={labelClass}>Hasta<input required type="date" className={`${inputClass} normal-case tracking-normal text-slate-900`} value={periodForm.end_date} onChange={(event) => setPeriodForm((current) => ({ ...current, end_date: event.target.value }))} disabled={!canEditRates} /></label>
              <label className={labelClass}>Precio por noche<input required min={0} step="0.01" type="number" className={`${inputClass} normal-case tracking-normal text-slate-900`} value={periodForm.price_per_night} onChange={(event) => setPeriodForm((current) => ({ ...current, price_per_night: Number(event.target.value) }))} disabled={!canEditRates} /></label>
              <label className={labelClass}>Prioridad<input min={0} type="number" className={`${inputClass} normal-case tracking-normal text-slate-900`} value={periodForm.priority} onChange={(event) => setPeriodForm((current) => ({ ...current, priority: Number(event.target.value) }))} disabled={!canEditRates} /></label>
              <button type="submit" className="self-end rounded-2xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" disabled={!canEditRates || periodMutations.create.isPending || !categoryId}>{periodMutations.create.isPending ? "Guardando..." : "Agregar temporada"}</button>
            </form>
            {periodMutations.create.isError || periodMutations.remove.isError ? <p className="mt-2 text-sm text-rose-700">No se pudo actualizar la temporada.</p> : null}
          </section>
        </main>
      ) : null}
    </div>
  );
}
