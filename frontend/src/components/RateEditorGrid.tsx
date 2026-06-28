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

const PRICE_ROWS: Array<{ field: PriceField; label: string; required?: boolean }> = [
  { field: "price", label: "Precio base", required: true },
  { field: "price_cash", label: "Efectivo" },
  { field: "price_transfer", label: "Transferencia" },
  { field: "price_mercadopago", label: "Mercado Pago" }
];

const WEEKDAY = new Intl.DateTimeFormat("es-AR", { weekday: "short" });
const INTEGER_LABEL = new Intl.NumberFormat("es-AR");

const SOURCE_LABEL: Record<DailyRateRangeRow["source"], string> = {
  daily_rate: "Precio fijado para esta fecha",
  price_period: "Heredado de un período de precios",
  category_pricing: "Heredado del precio base de la categoría",
  none: "Sin precio configurado"
};

function currencySymbol(code: string) {
  return code === "USD" ? "US$" : code === "ARS" ? "AR$" : code;
}

function parseInput(raw: string): { value: number | null; valid: boolean } {
  const trimmed = raw.trim();
  if (trimmed === "") return { value: null, valid: true };
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed) || parsed < 0) return { value: null, valid: false };
  return { value: parsed, valid: true };
}

type Column = {
  row: DailyRateRangeRow;
  dayNum: string;
  weekday: string;
  isWeekend: boolean;
  isToday: boolean;
  open: boolean;
  forSale: number | null;
  reserved: number | null;
};

function RowLabel({ children, sub, className }: { children: ReactNode; sub?: string; className?: string }) {
  return (
    <th
      scope="row"
      className={cx(
        "sticky left-0 z-20 w-[176px] min-w-[176px] border-b border-r border-slate-200 bg-white px-3 py-2 text-left align-middle",
        className
      )}
    >
      <span className="block text-sm font-medium text-slate-800">{children}</span>
      {sub ? <span className="block text-[11px] text-slate-400">{sub}</span> : null}
    </th>
  );
}

export function RateEditorGrid({ dailyRates, calendar, currencyCode, onSaveCell, disabled }: RateEditorGridProps) {
  const calendarByDate = new Map((calendar?.days ?? []).map((day) => [day.date, day]));
  const symbol = currencySymbol(currencyCode);

  const columns: Column[] = dailyRates.map((row) => {
    const day = calendarByDate.get(row.date);
    const d = new Date(`${row.date}T00:00:00`);
    const dow = d.getDay();
    return {
      row,
      dayNum: String(d.getDate()).padStart(2, "0"),
      weekday: WEEKDAY.format(d).replace(".", ""),
      isWeekend: dow === 0 || dow === 6,
      isToday: Boolean(day?.is_today),
      open: day ? day.status === "open" : true,
      forSale: day ? day.for_sale : null,
      reserved: day ? day.reserved : null
    };
  });

  const commit = (row: DailyRateRangeRow, field: PriceField, raw: string) => {
    const { value, valid } = parseInput(raw);
    if (!valid) return;
    if (field === "price" && value === null) return; // base is mandatory; clearing is a no-op
    const current = row[field] ?? null;
    if (value === current) return;

    onSaveCell({
      date: row.date,
      price: field === "price" ? (value as number) : row.price,
      price_cash: field === "price_cash" ? value : row.price_cash ?? null,
      price_transfer: field === "price_transfer" ? value : row.price_transfer ?? null,
      price_mercadopago: field === "price_mercadopago" ? value : row.price_mercadopago ?? null
    });
  };

  const colTint = (c: Column) =>
    c.isToday ? "bg-brand-50/70" : c.isWeekend ? "bg-slate-50/80" : "bg-white";

  return (
    <div
      data-testid="rate-editor-grid"
      className="overflow-x-auto rounded-xl border border-slate-200 bg-white"
    >
      <table className="w-max min-w-full border-separate border-spacing-0 text-sm">
        <thead>
          <tr>
            <th className="sticky left-0 top-0 z-30 w-[176px] min-w-[176px] border-b border-r border-slate-200 bg-white px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">
              {calendar?.meta.category_name ?? "Categoría"}
            </th>
            {columns.map((c) => (
              <th
                key={c.row.date}
                className={cx(
                  "sticky top-0 z-10 min-w-[84px] border-b border-l border-slate-100 px-2 py-1.5 text-center align-middle",
                  colTint(c),
                  c.isToday && "ring-1 ring-inset ring-brand-300"
                )}
              >
                <div className="flex flex-col items-center leading-tight">
                  <span
                    className={cx(
                      "text-[11px] font-medium uppercase",
                      c.isToday ? "text-brand-700" : c.isWeekend ? "text-slate-500" : "text-slate-400"
                    )}
                  >
                    {c.weekday}
                  </span>
                  <span className={cx("text-base font-semibold", c.isToday ? "text-brand-700" : "text-slate-800")}>
                    {c.dayNum}
                  </span>
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {/* Availability context (read-only) */}
          <tr>
            <RowLabel className="bg-slate-50/70">Estado</RowLabel>
            {columns.map((c) => (
              <td
                key={`st-${c.row.date}`}
                className={cx("min-w-[84px] border-b border-l border-slate-100 px-2 py-1.5 text-center", colTint(c))}
              >
                <span
                  className={cx(
                    "inline-block h-2.5 w-2.5 rounded-full",
                    c.open ? "bg-emerald-500" : "bg-rose-400"
                  )}
                  title={c.open ? "Disponible" : "Cerrado"}
                />
              </td>
            ))}
          </tr>
          <tr>
            <RowLabel sub="libres / reservadas">Disponibilidad</RowLabel>
            {columns.map((c) => (
              <td
                key={`av-${c.row.date}`}
                className={cx(
                  "min-w-[84px] border-b border-l border-slate-100 px-2 py-1.5 text-center text-xs text-slate-500",
                  colTint(c)
                )}
              >
                {c.forSale === null ? (
                  "—"
                ) : (
                  <span>
                    <span className={cx("font-semibold", c.forSale > 0 ? "text-slate-700" : "text-rose-500")}>
                      {INTEGER_LABEL.format(c.forSale)}
                    </span>
                    <span className="text-slate-300"> / {INTEGER_LABEL.format(c.reserved ?? 0)}</span>
                  </span>
                )}
              </td>
            ))}
          </tr>

          {/* Editable price rows */}
          {PRICE_ROWS.map((priceRow, idx) => (
            <tr key={priceRow.field}>
              <RowLabel
                sub={symbol}
                className={cx(idx === 0 && "border-t-2 border-t-slate-200", priceRow.required && "bg-brand-50/30")}
              >
                {priceRow.label}
                {priceRow.required ? <span className="ml-0.5 text-brand-500">*</span> : null}
              </RowLabel>
              {columns.map((c) => {
                const row = c.row;
                const value = row[priceRow.field] ?? null;
                const inherited = priceRow.field === "price" && row.source !== "daily_rate";
                return (
                  <td
                    key={`${priceRow.field}-${row.date}`}
                    className={cx(
                      "min-w-[84px] border-b border-l border-slate-100 p-0",
                      idx === 0 && "border-t-2 border-t-slate-200",
                      colTint(c)
                    )}
                  >
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
                        "h-9 w-full bg-transparent px-2 text-right text-sm tabular-nums outline-none transition-colors",
                        "hover:bg-brand-50/60 focus:bg-white focus:ring-2 focus:ring-inset focus:ring-brand-400 disabled:opacity-50",
                        inherited ? "italic text-slate-400" : "font-medium text-slate-900",
                        priceRow.required && !inherited && "text-slate-900"
                      )}
                    />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
