import { type ReactNode } from "react";
import cx from "clsx";

import type { DailyRateRangeRow, RateCalendarResponse } from "../api/rate-calendar";
import type { SingleRateInput } from "../hooks/useRateCalendar";

type RateEditorGridProps = {
  dailyRates: DailyRateRangeRow[];
  calendar?: RateCalendarResponse;
  currencyCode: string;
  onSaveCell: (payload: SingleRateInput) => void;
  disabled?: boolean;
};

type PriceField = "price" | "price_cash" | "price_transfer" | "price_mercadopago";

const PRICE_ROWS: Array<{ field: PriceField; label: string; hint: string; required?: boolean }> = [
  { field: "price", label: "Precio base", hint: "Tarifa mostrada por defecto", required: true },
  { field: "price_cash", label: "Efectivo", hint: "Opcional" },
  { field: "price_transfer", label: "Transferencia", hint: "Opcional" },
  { field: "price_mercadopago", label: "Mercado Pago", hint: "Opcional" }
];

const DATE_LABEL = new Intl.DateTimeFormat("es-AR", { weekday: "short", day: "2-digit", month: "2-digit" });
const INTEGER_LABEL = new Intl.NumberFormat("es-AR");

const SOURCE_LABEL: Record<DailyRateRangeRow["source"], string> = {
  daily_rate: "Precio fijado para esta fecha",
  price_period: "Heredado de un período de precios",
  category_pricing: "Heredado del precio base de la categoría",
  none: "Sin precio configurado"
};

function StickyLabelCell({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <th
      scope="row"
      className={cx(
        "sticky left-0 z-20 w-[240px] min-w-[240px] border-b border-r border-slate-200 bg-white px-4 py-3 text-left align-middle",
        className
      )}
    >
      {children}
    </th>
  );
}

function parseInput(raw: string): { value: number | null; valid: boolean } {
  const trimmed = raw.trim();
  if (trimmed === "") return { value: null, valid: true };
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed) || parsed < 0) return { value: null, valid: false };
  return { value: parsed, valid: true };
}

export function RateEditorGrid({ dailyRates, calendar, currencyCode, onSaveCell, disabled }: RateEditorGridProps) {
  const calendarByDate = new Map((calendar?.days ?? []).map((day) => [day.date, day]));
  const currencyPrefix = currencyCode === "USD" ? "US$" : currencyCode === "ARS" ? "AR$" : currencyCode;

  const commit = (row: DailyRateRangeRow, field: PriceField, raw: string) => {
    const { value, valid } = parseInput(raw);
    if (!valid) return; // invalid input: ignore, the input keeps the typed value until blur reverts via key
    // The base price is mandatory (>= 0); clearing it is a no-op.
    if (field === "price" && value === null) return;

    const current = row[field] ?? null;
    if (value === current) return; // unchanged

    onSaveCell({
      date: row.date,
      price: field === "price" ? (value as number) : row.price,
      price_cash: field === "price_cash" ? value : row.price_cash ?? null,
      price_transfer: field === "price_transfer" ? value : row.price_transfer ?? null,
      price_mercadopago: field === "price_mercadopago" ? value : row.price_mercadopago ?? null
    });
  };

  return (
    <div
      data-testid="rate-editor-grid"
      className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm"
    >
      <table className="w-max min-w-full border-separate border-spacing-0">
        <thead>
          <tr>
            <th className="sticky left-0 top-0 z-30 w-[240px] min-w-[240px] border-b border-r border-slate-200 bg-white px-4 py-3 text-left">
              <p className="text-xs uppercase tracking-wide text-slate-500">Editar precios</p>
              <p className="text-sm font-semibold text-slate-900">Clic en una celda para cambiar</p>
            </th>
            {dailyRates.map((row) => {
              const day = calendarByDate.get(row.date);
              return (
                <th
                  key={row.date}
                  className="sticky top-0 z-10 min-w-[104px] border-b border-slate-200 bg-white px-3 py-3 text-center align-top"
                >
                  <div className="flex flex-col items-center gap-1">
                    <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      {DATE_LABEL.format(new Date(`${row.date}T00:00:00`))}
                    </span>
                    {day?.is_today ? (
                      <span className="rounded-full bg-brand-100 px-2 py-0.5 text-[11px] font-semibold text-brand-700">
                        Hoy
                      </span>
                    ) : null}
                  </div>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {/* Availability context (read-only) */}
          <tr>
            <StickyLabelCell className="bg-slate-50">
              <span className="text-sm font-semibold text-slate-900">Estado</span>
            </StickyLabelCell>
            {dailyRates.map((row) => {
              const day = calendarByDate.get(row.date);
              const open = day ? day.status === "open" : true;
              return (
                <td
                  key={`status-${row.date}`}
                  className="min-w-[104px] border-b border-slate-200 bg-slate-50 px-3 py-2 text-center"
                >
                  <span
                    className={cx(
                      "inline-flex rounded-full px-2 py-1 text-xs font-semibold",
                      open ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-700"
                    )}
                  >
                    {open ? "Disponible" : "Cerrado"}
                  </span>
                </td>
              );
            })}
          </tr>
          <tr>
            <StickyLabelCell>
              <span className="text-sm font-medium text-slate-900">Disponibles</span>
            </StickyLabelCell>
            {dailyRates.map((row) => {
              const day = calendarByDate.get(row.date);
              return (
                <td
                  key={`for-sale-${row.date}`}
                  className="min-w-[104px] border-b border-slate-200 px-3 py-2 text-center text-sm text-slate-700"
                >
                  {day ? INTEGER_LABEL.format(day.for_sale) : "—"}
                </td>
              );
            })}
          </tr>
          <tr>
            <StickyLabelCell>
              <span className="text-sm font-medium text-slate-900">Reservadas</span>
            </StickyLabelCell>
            {dailyRates.map((row) => {
              const day = calendarByDate.get(row.date);
              return (
                <td
                  key={`reserved-${row.date}`}
                  className="min-w-[104px] border-b border-slate-200 px-3 py-2 text-center text-sm text-slate-700"
                >
                  {day ? INTEGER_LABEL.format(day.reserved) : "—"}
                </td>
              );
            })}
          </tr>

          {/* Editable price rows */}
          {PRICE_ROWS.map((priceRow) => (
            <tr key={priceRow.field}>
              <StickyLabelCell className={priceRow.required ? "bg-brand-50/40" : undefined}>
                <div className="space-y-0.5">
                  <p className="text-sm font-semibold text-slate-900">
                    {priceRow.label}
                    {priceRow.required ? <span className="ml-1 text-brand-600">*</span> : null}
                  </p>
                  <p className="text-xs text-slate-500">{priceRow.hint}</p>
                </div>
              </StickyLabelCell>
              {dailyRates.map((row) => {
                const value = row[priceRow.field] ?? null;
                const inherited = priceRow.field === "price" && row.source !== "daily_rate";
                return (
                  <td
                    key={`${priceRow.field}-${row.date}`}
                    className="min-w-[104px] border-b border-slate-200 px-1.5 py-1.5 text-center"
                  >
                    <div className="relative flex items-center">
                      <span className="pointer-events-none absolute left-2 text-[11px] text-slate-400">
                        {currencyPrefix}
                      </span>
                      <input
                        // Remount with fresh defaultValue whenever server data changes.
                        key={`${row.date}-${priceRow.field}-${value ?? "null"}-${row.source}`}
                        type="number"
                        min={0}
                        step="0.01"
                        inputMode="decimal"
                        disabled={disabled}
                        defaultValue={value ?? ""}
                        title={priceRow.field === "price" ? SOURCE_LABEL[row.source] : undefined}
                        placeholder={priceRow.required ? "0" : "—"}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            (event.target as HTMLInputElement).blur();
                          }
                        }}
                        onBlur={(event) => commit(row, priceRow.field, event.target.value)}
                        className={cx(
                          "w-full rounded-md border px-1 py-1.5 pl-7 text-right text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 disabled:opacity-60",
                          inherited
                            ? "border-dashed border-slate-300 italic text-slate-500"
                            : "border-slate-200 text-slate-900"
                        )}
                      />
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="border-t border-slate-100 px-4 py-2 text-xs text-slate-500">
        El <span className="font-medium">Precio base</span> es obligatorio. Los precios en
        <span className="mx-1 italic text-slate-500">cursiva con borde punteado</span>
        son heredados (del período o del precio de categoría) hasta que fijes uno propio para esa fecha.
        Editá una celda y salí del campo (o Enter) para guardar.
      </p>
    </div>
  );
}
