import { Fragment, type ReactNode } from "react";
import cx from "clsx";

import type {
  RateCalendarChannelDay,
  RateCalendarChannelPrice,
  RateCalendarDay,
  RateCalendarResponse
} from "../api/rate-calendar";

import { InfoTip } from "./InfoTip";

type RateCalendarGridProps = {
  calendar: RateCalendarResponse;
};

type ChannelSummary = {
  providerCode: string;
  providerLabel: string;
  currencyCode: string;
  missingMapping: boolean;
  priceRows: Array<{
    id: string;
    label: string;
    ratePlanId: number | null;
  }>;
};

const DATE_LABEL = new Intl.DateTimeFormat("es-AR", {
  weekday: "short",
  day: "2-digit",
  month: "2-digit"
});

const INTEGER_LABEL = new Intl.NumberFormat("es-AR");

const ARRIVAL_LABELS: Record<string, string> = {
  booking: "No arrivals",
  expedia: "Cerrado llegada",
  direct: "No check-in"
};

const DEPARTURE_LABELS: Record<string, string> = {
  booking: "No departures",
  expedia: "Cerrado salida",
  direct: "No check-out"
};

function formatCurrency(amount: number, currencyCode: string) {
  const prefix = currencyCode === "USD" ? "US$" : currencyCode === "ARS" ? "AR$" : currencyCode;
  return `${prefix} ${INTEGER_LABEL.format(Math.round(amount))}`;
}

function getDemandBadge(day: RateCalendarDay) {
  if (day.total_rooms <= 0) {
    return null;
  }

  if (day.occupancy_pct >= 100) {
    return { label: "Completo", className: "bg-rose-100 text-rose-700" };
  }
  if (day.occupancy_pct >= 90) {
    return { label: "Muy alta", className: "bg-rose-50 text-rose-700" };
  }
  if (day.occupancy_pct >= 80) {
    return { label: "Alta", className: "bg-orange-100 text-orange-700" };
  }
  if (day.occupancy_pct >= 75) {
    return { label: "Demanda alta", className: "bg-amber-100 text-amber-700" };
  }
  return null;
}

function getChannelForDay(day: RateCalendarDay, providerCode: string) {
  return day.channels.find((channel) => channel.provider_code === providerCode) ?? null;
}

function getPriceForDay(channel: RateCalendarChannelDay | null, ratePlanId: number | null) {
  if (!channel || ratePlanId === null) {
    return null;
  }
  return channel.prices.find((price) => price.rate_plan_id === ratePlanId) ?? null;
}

function buildChannelSummaries(days: RateCalendarDay[]): ChannelSummary[] {
  const summaries = new Map<string, ChannelSummary>();

  days.forEach((day) => {
    day.channels.forEach((channel) => {
      let summary = summaries.get(channel.provider_code);
      if (!summary) {
        summary = {
          providerCode: channel.provider_code,
          providerLabel: channel.provider_label,
          currencyCode: channel.currency_code,
          missingMapping: channel.missing_mapping,
          priceRows: []
        };
        summaries.set(channel.provider_code, summary);
      }

      summary.currencyCode = summary.currencyCode || channel.currency_code;
      summary.missingMapping = summary.missingMapping || channel.missing_mapping;

      channel.prices.forEach((price) => {
        if (summary?.priceRows.some((row) => row.ratePlanId === price.rate_plan_id)) {
          return;
        }
        summary?.priceRows.push({
          id: `${channel.provider_code}-${price.rate_plan_id}`,
          label: price.rate_plan_name || price.rate_plan_code,
          ratePlanId: price.rate_plan_id
        });
      });
    });
  });

  return Array.from(summaries.values()).map((summary) => {
    if (summary.priceRows.length > 0) {
      return summary;
    }

    return {
      ...summary,
      priceRows: [
        {
          id: `${summary.providerCode}-placeholder`,
          label: "Tarifas",
          ratePlanId: null
        }
      ]
    };
  });
}

function buildInfoContent(summary: ChannelSummary) {
  return (
    <div className="space-y-2">
      <p className="font-semibold text-slate-900">{summary.providerLabel}</p>
      <p>Moneda del canal: {summary.currencyCode}</p>
      <p>
        Estado del mapeo: {summary.missingMapping ? "faltan vínculos de inventario/tarifa para publicar datos" : "mapeo disponible en modo lectura"}.
      </p>
      <p>Las restricciones visibles reflejan mínimo de noches y cierres de llegada/salida por canal. No hay edición en esta vista.</p>
    </div>
  );
}

function StickyLabelCell({
  children,
  className
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <th
      scope="row"
      className={cx(
        "sticky left-0 z-20 w-[260px] min-w-[260px] border-b border-r border-slate-200 px-4 py-3 text-left align-top",
        className
      )}
    >
      {children}
    </th>
  );
}

function DayHeaderCell({ day }: { day: RateCalendarDay }) {
  const demand = getDemandBadge(day);

  return (
    <th className="sticky top-0 z-10 min-w-[96px] border-b border-slate-200 bg-white px-3 py-3 text-center align-top">
      <div className="flex flex-col items-center gap-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          {DATE_LABEL.format(new Date(`${day.date}T00:00:00`))}
        </span>
        {day.is_today ? (
          <span className="rounded-full bg-brand-100 px-2 py-0.5 text-[11px] font-semibold text-brand-700">Hoy</span>
        ) : null}
        {demand ? (
          <span className={cx("rounded-full px-2 py-0.5 text-[11px] font-semibold", demand.className)}>{demand.label}</span>
        ) : null}
      </div>
    </th>
  );
}

function MetricCell({
  children,
  className
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <td className={cx("min-w-[96px] border-b border-slate-200 px-3 py-3 text-center text-sm text-slate-700", className)}>
      {children}
    </td>
  );
}

function StatusPill({ open }: { open: boolean }) {
  return (
    <span
      className={cx(
        "inline-flex rounded-full px-2 py-1 text-xs font-semibold",
        open ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-700"
      )}
    >
      {open ? "Disponible" : "Cerrado"}
    </span>
  );
}

function RestrictionPill({ blocked }: { blocked: boolean }) {
  return (
    <span
      className={cx(
        "inline-flex rounded-full px-2 py-1 text-xs font-semibold",
        blocked ? "bg-rose-100 text-rose-700" : "bg-emerald-100 text-emerald-700"
      )}
    >
      {blocked ? "No permitido" : "Permitido"}
    </span>
  );
}

function renderPriceValue(channel: RateCalendarChannelDay | null, price: RateCalendarChannelPrice | null) {
  if (channel?.missing_mapping) {
    return <span className="text-xs font-medium text-rose-700">Falta mapeo</span>;
  }
  if (!price) {
    return <span className="text-xs text-slate-500">Sin tarifas configuradas</span>;
  }

  return <span className="font-medium text-slate-900">{formatCurrency(price.base_amount, price.currency_code)}</span>;
}

export function RateCalendarGrid({ calendar }: RateCalendarGridProps) {
  const channelSummaries = buildChannelSummaries(calendar.days);

  return (
    <div
      data-testid="rate-calendar-grid"
      className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm"
    >
      <table className="w-max min-w-full border-separate border-spacing-0">
        <thead>
          <tr>
            <th className="sticky left-0 top-0 z-30 w-[260px] min-w-[260px] border-b border-r border-slate-200 bg-white px-4 py-3 text-left">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Categoría</p>
                <p className="font-semibold text-slate-900">
                  {calendar.meta.category_name} · {calendar.meta.category_code}
                </p>
              </div>
            </th>
            {calendar.days.map((day) => (
              <DayHeaderCell key={day.date} day={day} />
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <StickyLabelCell className="bg-slate-50">
              <span className="text-sm font-semibold text-slate-900">Estado</span>
            </StickyLabelCell>
            {calendar.days.map((day) => (
              <MetricCell key={`status-${day.date}`} className="bg-slate-50">
                <StatusPill open={day.status === "open"} />
              </MetricCell>
            ))}
          </tr>
          <tr>
            <StickyLabelCell>
              <span className="text-sm font-semibold text-slate-900">Para vender</span>
            </StickyLabelCell>
            {calendar.days.map((day) => (
              <MetricCell key={`for-sale-${day.date}`}>{INTEGER_LABEL.format(day.for_sale)}</MetricCell>
            ))}
          </tr>
          <tr>
            <StickyLabelCell>
              <span className="text-sm font-semibold text-slate-900">Reservadas</span>
            </StickyLabelCell>
            {calendar.days.map((day) => (
              <MetricCell key={`reserved-${day.date}`}>{INTEGER_LABEL.format(day.reserved)}</MetricCell>
            ))}
          </tr>

          {channelSummaries.map((summary) => (
            <Fragment key={summary.providerCode}>
              <tr>
                <StickyLabelCell className="bg-slate-900 text-white">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold">{summary.providerLabel}</p>
                      <p className="text-xs text-slate-300">Lectura de tarifas y restricciones</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="rounded-full bg-white/10 px-2 py-1 text-[11px] font-semibold text-white">
                        {summary.currencyCode}
                      </span>
                      <InfoTip content={buildInfoContent(summary)} label={`Info ${summary.providerLabel}`} />
                    </div>
                  </div>
                </StickyLabelCell>
                {calendar.days.map((day) => (
                  <MetricCell key={`${summary.providerCode}-header-${day.date}`} className="bg-slate-900 text-slate-200">
                    {getChannelForDay(day, summary.providerCode)?.missing_mapping ? "Sin publicar" : "Activo"}
                  </MetricCell>
                ))}
              </tr>
              {summary.priceRows.map((priceRow) => (
                <tr key={priceRow.id}>
                  <StickyLabelCell>
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-slate-900">{priceRow.label}</p>
                      <p className="text-xs text-slate-500">Tarifa publicada</p>
                    </div>
                  </StickyLabelCell>
                  {calendar.days.map((day) => {
                    const channel = getChannelForDay(day, summary.providerCode);
                    const price = getPriceForDay(channel, priceRow.ratePlanId);
                    return (
                      <MetricCell key={`${priceRow.id}-${day.date}`}>
                        {renderPriceValue(channel, price)}
                      </MetricCell>
                    );
                  })}
                </tr>
              ))}
              <tr key={`${summary.providerCode}-min-stay`}>
                <StickyLabelCell>
                  <span className="text-sm font-medium text-slate-900">Min. noches</span>
                </StickyLabelCell>
                {calendar.days.map((day) => {
                  const channel = getChannelForDay(day, summary.providerCode);
                  return (
                    <MetricCell key={`${summary.providerCode}-min-stay-${day.date}`}>
                      {channel?.restrictions.min_stay ? INTEGER_LABEL.format(channel.restrictions.min_stay) : "—"}
                    </MetricCell>
                  );
                })}
              </tr>
              <tr key={`${summary.providerCode}-arrival`}>
                <StickyLabelCell>
                  <span className="text-sm font-medium text-slate-900">
                    {ARRIVAL_LABELS[summary.providerCode] || "Cerrado llegada"}
                  </span>
                </StickyLabelCell>
                {calendar.days.map((day) => {
                  const channel = getChannelForDay(day, summary.providerCode);
                  return (
                    <MetricCell key={`${summary.providerCode}-arrival-${day.date}`}>
                      <RestrictionPill blocked={Boolean(channel?.restrictions.closed_to_arrival)} />
                    </MetricCell>
                  );
                })}
              </tr>
              <tr key={`${summary.providerCode}-departure`}>
                <StickyLabelCell>
                  <span className="text-sm font-medium text-slate-900">
                    {DEPARTURE_LABELS[summary.providerCode] || "Cerrado salida"}
                  </span>
                </StickyLabelCell>
                {calendar.days.map((day) => {
                  const channel = getChannelForDay(day, summary.providerCode);
                  return (
                    <MetricCell key={`${summary.providerCode}-departure-${day.date}`}>
                      <RestrictionPill blocked={Boolean(channel?.restrictions.closed_to_departure)} />
                    </MetricCell>
                  );
                })}
              </tr>
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
