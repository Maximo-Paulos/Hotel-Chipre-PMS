import { useEffect, useState } from "react";

import type { DailyRateRangeRow } from "../api/rate-calendar";
import type { SingleRateInput } from "../hooks/useRateCalendar";

import type { PriceField } from "./RateEditorGrid";

// Mobile alternative to RateEditorGrid's dense spreadsheet: a card-per-day,
// step-through-the-week flow. Desktop keeps the grid (see RateCalendarPage,
// which renders this component only below the `md` breakpoint).

const PRICE_FIELDS: Array<{ field: PriceField; label: string; required?: boolean }> = [
  { field: "price", label: "Precio base", required: true },
  { field: "price_cash", label: "Efectivo" },
  { field: "price_transfer", label: "Transferencia" },
  { field: "price_mercadopago", label: "Mercado Pago" },
  { field: "price_paypal", label: "PayPal" },
  { field: "price_credit_card", label: "Tarjeta de crédito" }
];

const WEEKDAY_LABEL = new Intl.DateTimeFormat("es-AR", { weekday: "long" });
const DAY_LABEL = new Intl.DateTimeFormat("es-AR", { day: "2-digit", month: "short" });
const WINDOW_SIZE = 7;

type RateEditorMobileCardsProps = {
  dailyRates: DailyRateRangeRow[];
  currencyCode: string;
  onSaveCell: (payload: SingleRateInput) => void;
  disabled?: boolean;
};

// ponytail: parses "" -> null, otherwise a non-negative number or invalid.
function parseField(raw: string): { value: number | null; valid: boolean } {
  const trimmed = raw.trim();
  if (trimmed === "") return { value: null, valid: true };
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed) || parsed < 0) return { value: null, valid: false };
  return { value: parsed, valid: true };
}

function RateDayCard({
  row,
  currencyCode,
  onSaveCell,
  disabled
}: {
  row: DailyRateRangeRow;
  currencyCode: string;
  onSaveCell: (payload: SingleRateInput) => void;
  disabled?: boolean;
}) {
  const [values, setValues] = useState<Record<PriceField, string>>({
    price: row.price != null ? String(row.price) : "",
    price_cash: row.price_cash != null ? String(row.price_cash) : "",
    price_transfer: row.price_transfer != null ? String(row.price_transfer) : "",
    price_mercadopago: row.price_mercadopago != null ? String(row.price_mercadopago) : "",
    price_paypal: row.price_paypal != null ? String(row.price_paypal) : "",
    price_credit_card: row.price_credit_card != null ? String(row.price_credit_card) : ""
  });
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const date = new Date(`${row.date}T00:00:00`);

  const handleSave = () => {
    setError(null);
    setSaved(false);
    const parsed: Record<PriceField, number | null> = {} as Record<PriceField, number | null>;
    for (const { field } of PRICE_FIELDS) {
      const { value, valid } = parseField(values[field]);
      if (!valid) {
        setError(`Valor inválido en "${PRICE_FIELDS.find((f) => f.field === field)?.label}".`);
        return;
      }
      parsed[field] = value;
    }
    if (parsed.price === null) {
      setError("El precio base es obligatorio.");
      return;
    }
    onSaveCell({
      date: row.date,
      price: parsed.price,
      price_cash: parsed.price_cash,
      price_transfer: parsed.price_transfer,
      price_mercadopago: parsed.price_mercadopago,
      price_paypal: parsed.price_paypal,
      price_credit_card: parsed.price_credit_card
    });
    setSaved(true);
  };

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm" data-testid="rate-editor-mobile-card">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold capitalize text-slate-900">{WEEKDAY_LABEL.format(date)}</p>
          <p className="text-xs text-slate-500">{DAY_LABEL.format(date)}</p>
        </div>
        <span
          className={`rounded-full px-2 py-1 text-xs font-semibold ${
            row.source === "none" ? "bg-rose-100 text-rose-700" : "bg-emerald-100 text-emerald-700"
          }`}
        >
          {row.source === "none" ? "Sin precio" : "Disponible"}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        {PRICE_FIELDS.map(({ field, label, required }) => (
          <label key={field} className="text-xs font-semibold text-slate-600">
            {label}
            {required ? <span className="ml-0.5 text-blue-500">*</span> : null}
            <input
              type="number"
              min={0}
              step="0.01"
              inputMode="decimal"
              disabled={disabled}
              value={values[field]}
              onChange={(e) => {
                setSaved(false);
                setValues((prev) => ({ ...prev, [field]: e.target.value }));
              }}
              aria-label={`${label} ${row.date}`}
              placeholder={required ? "0" : "—"}
              className="mt-1 h-11 w-full rounded-lg border border-slate-200 px-2 text-right text-sm tabular-nums outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100 disabled:opacity-50"
            />
          </label>
        ))}
      </div>

      {error ? <p className="mt-2 text-xs font-medium text-rose-700">{error}</p> : null}
      {saved && !error ? <p className="mt-2 text-xs font-medium text-emerald-700">Guardado.</p> : null}

      <button
        type="button"
        onClick={handleSave}
        disabled={disabled}
        className="mt-3 min-h-11 w-full rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-70"
      >
        Guardar {DAY_LABEL.format(date)} ({currencyCode})
      </button>
    </article>
  );
}

export function RateEditorMobileCards({ dailyRates, currencyCode, onSaveCell, disabled }: RateEditorMobileCardsProps) {
  const [offset, setOffset] = useState(0);
  const firstDate = dailyRates[0]?.date;

  // A new category/year selection swaps the whole dailyRates window -- jump
  // back to the start instead of leaving the user on a now-meaningless offset.
  useEffect(() => {
    setOffset(0);
  }, [firstDate]);

  const visible = dailyRates.slice(offset, offset + WINDOW_SIZE);
  const canGoBack = offset > 0;
  const canGoForward = offset + WINDOW_SIZE < dailyRates.length;

  if (dailyRates.length === 0) {
    return <p className="p-4 text-sm text-slate-600">No hay fechas para mostrar.</p>;
  }

  return (
    <div className="space-y-3 p-4" data-testid="rate-editor-mobile-cards">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => setOffset((o) => Math.max(0, o - WINDOW_SIZE))}
          disabled={!canGoBack}
          className="min-h-11 min-w-11 rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 disabled:opacity-40"
        >
          ← Anterior
        </button>
        <p className="text-xs font-semibold text-slate-500">
          {visible[0]?.date} → {visible[visible.length - 1]?.date}
        </p>
        <button
          type="button"
          onClick={() => setOffset((o) => (o + WINDOW_SIZE < dailyRates.length ? o + WINDOW_SIZE : o))}
          disabled={!canGoForward}
          className="min-h-11 min-w-11 rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 disabled:opacity-40"
        >
          Siguiente →
        </button>
      </div>

      {visible.map((row) => (
        <RateDayCard key={row.date} row={row} currencyCode={currencyCode} onSaveCell={onSaveCell} disabled={disabled} />
      ))}
    </div>
  );
}
