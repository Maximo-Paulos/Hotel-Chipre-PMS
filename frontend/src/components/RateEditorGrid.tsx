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
const MONTH = new Intl.DateTimeFormat("es-AR", { month: "short" });
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

function markInvalid(input: HTMLInputElement, value: number | null) {
  input.value = value === null ? "" : String(value);
  input.setAttribute("aria-invalid", "true");
  input.select();
  window.setTimeout(() => {
    if (input.isConnected) {
      input.setAttribute("aria-invalid", "false");
    }
  }, 1200);
}

type Column = {
  index: number;
  row: DailyRateRangeRow;
  dayNum: string;
  weekday: string;
  month: string;
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
        "sticky left-0 z-20 h-10 w-[260px] min-w-[260px] border-b border-r border-slate-200 bg-white px-4 py-2 text-left align-middle",
        className
      )}
    >
      <span className="block text-sm font-medium text-slate-800">{children}</span>
      {sub ? <span className="block text-[11px] text-slate-400">{sub}</span> : null}
    </th>
  );
}

// Move focus to the same price row in the previous/next date column, so the
// grid behaves like a spreadsheet for fast rate entry.
function focusSibling(el: HTMLElement, field: string, col: number, dir: number) {
  const table = el.closest("table");
  if (!table) return false;
  const next = table.querySelector<HTMLInputElement>(`input[data-field="${field}"][data-col="${col + dir}"]`);
  if (next) {
    el.dataset.skipBlurCommit = "true";
    next.focus();
    next.select();
    return true;
  }
  return false;
}

export function RateEditorGrid({ dailyRates, calendar, currencyCode, onSaveCell, disabled }: RateEditorGridProps) {
  const calendarByDate = new Map((calendar?.days ?? []).map((day) => [day.date, day]));
  const symbol = currencySymbol(currencyCode);

  const columns: Column[] = dailyRates.map((row, index) => {
    const day = calendarByDate.get(row.date);
    const d = new Date(`${row.date}T00:00:00`);
    const dow = d.getDay();
    return {
      index,
      row,
      dayNum: String(d.getDate()).padStart(2, "0"),
      weekday: WEEKDAY.format(d).replace(".", ""),
      month: MONTH.format(d).replace(".", ""),
      isWeekend: dow === 0 || dow === 6,
      isToday: Boolean(day?.is_today),
      open: day ? day.status === "open" : true,
      forSale: day ? day.for_sale : null,
      reserved: day ? day.reserved : null
    };
  });

  const commit = (input: HTMLInputElement, row: DailyRateRangeRow, field: PriceField, raw: string) => {
    const { value, valid } = parseInput(raw);
    const current = row[field] ?? null;
    if (!valid || (field === "price" && value === null)) {
      markInvalid(input, current);
      return false;
    }
    input.setAttribute("aria-invalid", "false");
    if (value === current) return true;

    onSaveCell({
      date: row.date,
      price: field === "price" ? (value as number) : row.price,
      price_cash: field === "price_cash" ? value : row.price_cash ?? null,
      price_transfer: field === "price_transfer" ? value : row.price_transfer ?? null,
      price_mercadopago: field === "price_mercadopago" ? value : row.price_mercadopago ?? null
    });
    return true;
  };

  const colTint = (c: Column) =>
    c.isToday ? "bg-blue-50/80" : c.isWeekend ? "bg-slate-50/80" : "bg-white";

  return (
    <div
      data-testid="rate-editor-grid"
      className="overflow-x-auto bg-white"
    >
      <table className="w-max min-w-full border-separate border-spacing-0 text-sm">
        <thead>
          <tr>
            <th className="sticky left-0 top-0 z-30 h-16 w-[260px] min-w-[260px] border-b border-r border-slate-200 bg-white px-4 py-3 text-left">
              <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">Campo / fecha</p>
              <p className="truncate text-sm font-semibold text-slate-900">{calendar?.meta.category_name ?? "Categoría"}</p>
            </th>
            {columns.map((c) => (
              <th
                key={c.row.date}
                className={cx(
                  "sticky top-0 z-10 h-16 min-w-[96px] border-b border-r border-slate-200 px-2 py-2 text-center align-middle",
                  colTint(c),
                  c.isToday && "ring-1 ring-inset ring-blue-300"
                )}
              >
                <div className="flex flex-col items-center gap-0.5 leading-tight">
                  <span
                    className={cx(
                      "text-[11px] font-medium uppercase",
                      c.isToday ? "text-blue-700" : c.isWeekend ? "text-slate-500" : "text-slate-400"
                    )}
                  >
                    {c.weekday}
                  </span>
                  <span className={cx("text-lg font-semibold", c.isToday ? "text-blue-700" : "text-slate-800")}>
                    {c.dayNum}
                  </span>
                  <span className="text-[10px] font-medium uppercase text-slate-400">{c.month}</span>
                  {c.isToday ? (
                    <span className="rounded-full bg-blue-100 px-1.5 py-0.5 text-[10px] font-semibold text-blue-700">Hoy</span>
                  ) : null}
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
                className={cx("min-w-[96px] border-b border-r border-slate-200 px-2 py-2 text-center", colTint(c))}
              >
                <span
                  aria-label={c.open ? "Disponible" : "Cerrado"}
                  className={cx(
                    "inline-flex rounded-full px-2 py-1 text-xs font-semibold",
                    c.open ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"
                  )}
                  title={c.open ? "Disponible" : "Cerrado"}
                >
                  {c.open ? "Abierto" : "Cerrado"}
                </span>
              </td>
            ))}
          </tr>
          <tr>
            <RowLabel>Para vender</RowLabel>
            {columns.map((c) => (
              <td
                key={`av-${c.row.date}`}
                className={cx(
                  "min-w-[96px] border-b border-r border-slate-200 px-2 py-2 text-center text-sm",
                  colTint(c)
                )}
              >
                {c.forSale === null ? (
                  "—"
                ) : (
                  <span className={cx("font-semibold", c.forSale > 0 ? "text-slate-700" : "text-rose-500")}>
                    {INTEGER_LABEL.format(c.forSale)}
                  </span>
                )}
              </td>
            ))}
          </tr>
          <tr>
            <RowLabel>Reservadas</RowLabel>
            {columns.map((c) => (
              <td
                key={`rs-${c.row.date}`}
                className={cx(
                  "min-w-[96px] border-b border-r border-slate-200 px-2 py-2 text-center text-sm text-slate-600",
                  colTint(c)
                )}
              >
                {c.reserved === null ? "—" : INTEGER_LABEL.format(c.reserved)}
              </td>
            ))}
          </tr>

          {/* Editable price rows */}
          {PRICE_ROWS.map((priceRow, idx) => (
            <tr key={priceRow.field}>
              <RowLabel
                sub={symbol}
                className={cx(idx === 0 && "border-t-2 border-t-slate-200", priceRow.required && "bg-blue-50/40")}
              >
                {priceRow.label}
                {priceRow.required ? <span className="ml-0.5 text-blue-500">*</span> : null}
              </RowLabel>
              {columns.map((c) => {
                const row = c.row;
                const value = row[priceRow.field] ?? null;
                const inherited = priceRow.field === "price" && row.source !== "daily_rate";
                return (
                  <td
                    key={`${priceRow.field}-${row.date}`}
                    className={cx(
                      "min-w-[96px] border-b border-r border-slate-200 p-0.5",
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
                      data-field={priceRow.field}
                      data-col={c.index}
                      defaultValue={value ?? ""}
                      aria-label={`${priceRow.label} ${row.date}`}
                      aria-invalid="false"
                      title={priceRow.field === "price" ? SOURCE_LABEL[row.source] : undefined}
                      placeholder={priceRow.required ? "0" : "—"}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          if (commit(event.currentTarget, row, priceRow.field, event.currentTarget.value)) {
                            focusSibling(event.currentTarget, priceRow.field, c.index, event.shiftKey ? -1 : 1);
                          }
                        }
                      }}
                      onBlur={(event) => {
                        if (event.currentTarget.dataset.skipBlurCommit === "true") {
                          delete event.currentTarget.dataset.skipBlurCommit;
                          return;
                        }
                        commit(event.currentTarget, row, priceRow.field, event.currentTarget.value);
                      }}
                      className={cx(
                        "h-10 w-full rounded-lg px-2 text-right text-sm tabular-nums outline-none transition-shadow",
                        "bg-white/80 ring-1 ring-inset ring-slate-200/80 hover:ring-blue-300",
                        "focus:bg-white focus:ring-2 focus:ring-blue-500 disabled:opacity-50",
                        "aria-[invalid=true]:bg-rose-50 aria-[invalid=true]:ring-rose-400",
                        inherited ? "italic text-slate-400" : "font-medium text-slate-900"
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
