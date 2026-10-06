import { useState } from "react";

import { downloadRevenueReportCsv, type CurrencyAmount, type OperationalReservationGroup, type OperationalReservationSummary } from "../../api/reports";
import { ApiError } from "../../api/client";
import { useEffectivePermissions } from "../../hooks/usePermissions";
import { useHotelConfig } from "../../hooks/useHotelConfig";
import { useDailyOperationalReport, useOccupancyReport, useRevenueReport, useTodayArrivalCount } from "../../hooks/useReports";
import { formatHotelDateTime, todayIso } from "../../utils/date";
import { useSession } from "../../state/session";

const money = (value?: CurrencyAmount | null, currency = "ARS") =>
  Number(value ?? 0).toLocaleString("es-AR", { style: "currency", currency: currency.toUpperCase() });

const hotelTodayIso = (timeZone?: string | null, serverDate?: string | null) => {
  const serverLocalDate = serverDate && /^\d{4}-\d{2}-\d{2}$/.test(serverDate) ? serverDate : null;
  if (!timeZone) return serverLocalDate ?? todayIso();
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit"
    }).formatToParts(new Date());
    const dateParts = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
    return `${dateParts.year}-${dateParts.month}-${dateParts.day}`;
  } catch {
    return serverLocalDate ?? todayIso();
  }
};

const paymentMethodLabel = (method?: string | null) => ({
  cash: "Efectivo",
  bank_transfer: "Transferencia",
  credit_card: "Tarjeta de crédito",
  debit_card: "Tarjeta de débito",
  mercadopago: "Mercado Pago",
  paypal: "PayPal",
  stripe: "Stripe"
}[String(method ?? "").toLowerCase()] ?? method ?? "Sin medio");

const channelLabel = (channel?: string | null) => ({
  manual_recepcion: "Recepción",
  telefono: "Teléfono",
  whatsapp_bot: "WhatsApp",
  web_propia: "Web propia",
  booking_manual: "Booking",
  expedia_manual: "Expedia",
  empresa: "Empresa"
}[String(channel ?? "").toLowerCase()] ?? channel ?? "Sin canal");

function currencyAmounts(rows: Array<{ currency_code: string; amount?: CurrencyAmount; net_collected?: CurrencyAmount }>, field: "amount" | "net_collected" = "amount") {
  return rows.length === 0
    ? "Sin datos"
    : rows.map((row) => money(row[field] ?? 0, row.currency_code)).join(" · ");
}

export function ReportsPage() {
  const { session } = useSession();
  const { hasPermission } = useEffectivePermissions();
  const hotelConfigQuery = useHotelConfig();
  const arrivalCountQuery = useTodayArrivalCount();
  const canViewFinancial = hasPermission("reports:financial:view");
  const [selectedReportDate, setSelectedReportDate] = useState("");
  const reportDate = selectedReportDate || hotelTodayIso(hotelConfigQuery.data?.hotel_timezone, arrivalCountQuery.data?.report_date);
  const reportQuery = useDailyOperationalReport(reportDate);
  const occupancyQuery = useOccupancyReport(reportDate, reportDate);
  const revenueQuery = useRevenueReport(reportDate, reportDate, canViewFinancial);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const report = reportQuery.data;
  // The daily response already includes role-redacted alerts; avoid rebuilding it through a second endpoint.
  const alerts = report?.alerts ?? [];
  const occupancy = occupancyQuery.data?.daily[0];
  const revenue = revenueQuery.data;

  const exportCsv = async () => {
    setExporting(true);
    setExportError(null);
    try {
      const blob = await downloadRevenueReportCsv(reportDate, reportDate, session);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `reporte-financiero-${reportDate}.csv`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setExportError(error instanceof Error ? error.message : "No se pudo exportar el reporte.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
          <h1 className="text-balance text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">Reportes</h1>
          <p className="text-sm text-slate-600">Operación diaria y ocupación; los importes financieros sólo están disponibles para owner y co-owner.</p>
        </div>
        <label className="space-y-1 text-sm">
          <span className="text-slate-600">Fecha</span>
          <input
            type="date"
            value={reportDate}
            onChange={(event) => setSelectedReportDate(event.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2"
          />
        </label>
      </header>

      {(reportQuery.error || occupancyQuery.error || revenueQuery.error) && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-3 text-sm text-rose-800" role="alert">
          <p>{reportsErrorMessage(reportQuery.error || occupancyQuery.error || revenueQuery.error)}</p>
          <button
            type="button"
            onClick={() => {
              void reportQuery.refetch();
              void occupancyQuery.refetch();
              if (canViewFinancial) void revenueQuery.refetch();
            }}
            disabled={reportQuery.isFetching || occupancyQuery.isFetching || revenueQuery.isFetching}
            className="mt-2 rounded-lg border border-rose-300 bg-white px-3 py-2 font-semibold text-rose-800 hover:bg-rose-100 disabled:opacity-60"
          >
            Reintentar
          </button>
        </div>
      )}

      {reportQuery.isLoading ? (
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">Cargando reporte...</div>
      ) : reportQuery.isError ? null : report ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Llegadas" value={String(report.arrivals.count)} />
            <Metric label="Salidas" value={String(report.departures.count)} />
            <Metric label="Ocupación" value={occupancy ? `${occupancy.rate}%` : "—"} />
            <Metric label="Alertas" value={String(alerts.length)} />
          </div>

          {canViewFinancial && revenue && (
            <section className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4 shadow-sm" data-testid="financial-report">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-wide text-emerald-700">Finanzas · acceso owner/co-owner</p>
                  <h2 className="text-lg font-semibold text-slate-900">Resumen del día</h2>
                  <p className="text-xs text-slate-600">Cobros y saldos se muestran por moneda. Zona horaria: {revenue.timezone}.</p>
                </div>
                <button
                  type="button"
                  onClick={() => void exportCsv()}
                  disabled={exporting || revenueQuery.isFetching}
                  className="rounded-lg border border-emerald-300 bg-white px-3 py-2 text-sm font-semibold text-emerald-800 hover:bg-emerald-50 disabled:opacity-60"
                >
                  {exporting ? "Exportando…" : "Exportar CSV"}
                </button>
              </div>
              {exportError ? <p className="mt-3 text-sm text-rose-700" role="alert">{exportError}</p> : null}
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <Metric label="Cobrado en el PMS" value={currencyAmounts(revenue.collected.by_currency, "net_collected")} />
                <Metric label="Valor reservado · no es cobro" value={currencyAmounts(revenue.booked_value.by_currency, "amount")} />
                <Metric label="Cobrado por OTA · fuera de caja" value={currencyAmounts(revenue.external_ota_collected.by_currency, "amount")} />
              </div>
              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <BreakdownTable
                  title="Cobros y devoluciones por medio"
                  rows={revenue.collected.by_method_by_currency.map((item) => ({
                    key: `${item.payment_method}-${item.currency_code}`,
                    label: paymentMethodLabel(item.payment_method),
                    currency: item.currency_code,
                    gross: item.gross_collected,
                    refunds: item.refunds,
                    net: item.net_collected
                  }))}
                />
                <BreakdownTable
                  title="Cobros y devoluciones por categoría"
                  rows={revenue.collected.by_category.map((item) => ({
                    key: `${item.category_id}-${item.currency_code}`,
                    label: item.category_name ?? "Sin categoría",
                    currency: item.currency_code,
                    gross: item.gross_collected,
                    refunds: item.refunds,
                    net: item.net_collected
                  }))}
                />
                <BreakdownTable
                  title="Cobros y devoluciones por canal"
                  rows={revenue.collected.by_channel.map((item) => ({
                    key: `${item.channel_code}-${item.currency_code}`,
                    label: channelLabel(item.channel_code),
                    currency: item.currency_code,
                    gross: item.gross_collected,
                    refunds: item.refunds,
                    net: item.net_collected
                  }))}
                />
                <section className="overflow-hidden rounded-lg border border-emerald-200 bg-white">
                  <div className="border-b border-emerald-100 px-4 py-3">
                    <h3 className="font-semibold text-slate-900">Saldos por cobrar</h3>
                    <p className="text-xs text-slate-500">Situación actual al {revenue.receivables_as_of}; no es un saldo histórico del día seleccionado.</p>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-left text-sm">
                      <thead className="bg-emerald-50 text-xs text-slate-600"><tr><th className="px-3 py-2">Moneda</th><th className="px-3 py-2">Vencido</th><th className="px-3 py-2">Check-in de hoy</th><th className="px-3 py-2">Adicional empresa hoy</th><th className="px-3 py-2">Futuro</th><th className="px-3 py-2">Total</th></tr></thead>
                      <tbody className="divide-y divide-slate-100">
                        {revenue.receivables.by_currency.length === 0 ? <tr><td colSpan={6} className="px-3 py-3 text-slate-500">No hay saldos por cobrar.</td></tr> : revenue.receivables.by_currency.map((item) => (
                          <tr key={item.currency_code}><td className="px-3 py-2 font-semibold">{item.currency_code}</td><td className="px-3 py-2">{money(item.overdue, item.currency_code)}</td><td className="px-3 py-2">{money(item.due_at_check_in, item.currency_code)}</td><td className="px-3 py-2">{money(item.due_today_company_nights, item.currency_code)}</td><td className="px-3 py-2">{money(item.future, item.currency_code)}</td><td className="px-3 py-2 font-semibold">{money(item.total, item.currency_code)}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              </div>
            </section>
          )}

          <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
            <div className="space-y-4">
              <ReservationGroup title="Llegadas del día" group={report.arrivals} emptyText="No hay llegadas para esta fecha." />
              <ReservationGroup title="No-shows" group={report.no_shows} emptyText="No hay no-shows para esta fecha." />
              <ReservationGroup title="Salidas del día" group={report.departures} emptyText="No hay salidas para esta fecha." />
              {canViewFinancial && (
                <ReservationGroup
                  title="Saldos pendientes en estadías activas"
                  group={report.pending_payments}
                  emptyText="No hay pagos pendientes en el reporte."
                  showBalance
                />
              )}
            </div>

            <aside className="space-y-4">
              {canViewFinancial && <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Caja</p>
                  <h2 className="text-lg font-semibold text-slate-900">Estado operativo</h2>
                </div>
                <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
                  <p className="font-semibold text-slate-900">{cashStatusLabel(report.cash_session.status)}</p>
                  <p className="text-xs text-slate-500">
                    {report.cash_session.session_id ? `Caja #${report.cash_session.session_id}` : "Sin sesión abierta"}
                  </p>
                  {report.cash_session.opened_at ? (
                    <p className="text-xs text-slate-500">Abierta {formatHotelDateTime(report.cash_session.opened_at, hotelConfigQuery.data?.hotel_timezone)}</p>
                  ) : null}
                </div>
              </section>}

              <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Bloqueos</p>
                  <h2 className="text-lg font-semibold text-slate-900">Habitaciones bloqueadas</h2>
                </div>
                <div className="mt-4 space-y-2">
                  {report.active_room_blocks.length === 0 ? (
                    <p className="text-sm text-slate-500">No hay bloqueos activos.</p>
                  ) : (
                    report.active_room_blocks.map((block) => (
                      <div key={block.room_block_id} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                        <p className="font-semibold text-slate-900">Hab. {block.room_number || "Información no disponible"}</p>
                        <p className="text-xs text-slate-500">
                          {block.reason_code} - {block.is_indefinite ? "sin fecha de fin" : `hasta ${block.ends_at}`}
                        </p>
                        {block.reason_note ? <p className="mt-1 text-xs text-slate-600">{block.reason_note}</p> : null}
                      </div>
                    ))
                  )}
                </div>
              </section>

              <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Alertas</p>
                  <h2 className="text-lg font-semibold text-slate-900">Riesgos operativos</h2>
                </div>
                <div className="mt-4 space-y-2">
                  {alerts.length === 0 ? (
                    <p className="text-sm text-slate-500">No hay alertas para esta fecha.</p>
                  ) : (
                    alerts.map((alert) => (
                      <div key={`${alert.code}-${alert.reservation_id ?? alert.room_id ?? alert.cash_session_id ?? "general"}`} className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                        <p className="font-semibold">{alert.severity.toUpperCase()} - {alert.code}</p>
                        <p>{alert.message}</p>
                        {alert.code === "pending_payment" && alert.amount != null ? (
                          <p className="mt-1 font-semibold">
                            Pendiente: {money(alert.amount, alert.currency_code ?? "ARS")}
                          </p>
                        ) : null}
                      </div>
                    ))
                  )}
                </div>
              </section>
            </aside>
          </section>
        </>
      ) : (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-sm text-slate-500">
          No hay datos para mostrar.
        </div>
      )}
    </div>
  );
}

function reportsErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 402) return "Tu plan actual no incluye este reporte operativo.";
    if (error.status === 403) return "No tenés permisos para consultar este reporte operativo.";
  }
  return "No se pudo cargar el reporte operativo. Revisá la conexión y reintentá.";
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function ReservationGroup({
  title,
  group,
  emptyText,
  showBalance = false
}: {
  title: string;
  group: OperationalReservationGroup;
  emptyText: string;
  showBalance?: boolean;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Reservas</p>
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        </div>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">{group.count}</span>
      </div>
      <div className="mt-4 overflow-hidden rounded-lg border border-slate-200">
        {group.reservations.length === 0 ? (
          <p className="px-4 py-3 text-sm text-slate-500">{emptyText}</p>
        ) : (
          <div className="divide-y divide-slate-200">
            {group.reservations.map((reservation) => (
              <ReservationRow key={reservation.reservation_id} reservation={reservation} showBalance={showBalance} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function ReservationRow({ reservation, showBalance }: { reservation: OperationalReservationSummary; showBalance: boolean }) {
  const companyExtraDue = Number(reservation.company_night_extra_due ?? 0);
  return (
    <div className="grid gap-2 px-4 py-3 text-sm md:grid-cols-[1fr_auto]">
      <div>
        <p className="font-semibold text-slate-900">
          {reservation.guest_name || `Huésped #${reservation.guest_id}`} - {reservation.confirmation_code}
        </p>
        <p className="text-xs text-slate-500">
          Hab. {reservation.room_number || "Información no disponible"} - {reservation.status} - {reservation.check_in_date} a {reservation.check_out_date}
        </p>
      </div>
      {showBalance ? (
        reservation.company_billing_deferred ? (
          <div className="text-right">
            <p className="text-xs font-medium text-slate-600">Alojamiento facturado fuera del PMS</p>
            {companyExtraDue > 0 ? <p className="font-semibold text-amber-800">Adicional empresa pendiente: {money(companyExtraDue, reservation.currency_code ?? "ARS")}</p> : null}
          </div>
        ) : <p className="font-semibold text-slate-900">{money(reservation.balance_due, reservation.currency_code ?? "ARS")}</p>
      ) : null}
    </div>
  );
}

function BreakdownTable({
  title,
  rows
}: {
  title: string;
  rows: Array<{ key: string; label: string; currency: string; gross: CurrencyAmount; refunds: CurrencyAmount; net: CurrencyAmount }>;
}) {
  return (
    <section className="overflow-hidden rounded-lg border border-emerald-200 bg-white">
      <div className="border-b border-emerald-100 px-4 py-3"><h3 className="font-semibold text-slate-900">{title}</h3></div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-emerald-50 text-xs text-slate-600"><tr><th className="px-3 py-2">Grupo</th><th className="px-3 py-2">Moneda</th><th className="px-3 py-2">Cobrado</th><th className="px-3 py-2">Devuelto</th><th className="px-3 py-2">Neto</th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {rows.length === 0 ? <tr><td colSpan={5} className="px-3 py-3 text-slate-500">Sin cobros confirmados.</td></tr> : rows.map((row) => (
              <tr key={row.key}><td className="px-3 py-2 font-medium text-slate-800">{row.label}</td><td className="px-3 py-2">{row.currency}</td><td className="px-3 py-2">{money(row.gross, row.currency)}</td><td className="px-3 py-2">{money(row.refunds, row.currency)}</td><td className="px-3 py-2 font-semibold">{money(row.net, row.currency)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function cashStatusLabel(status: string) {
  if (status === "open") return "Caja abierta";
  if (status === "closed") return "Caja cerrada";
  if (status === "missing") return "Sin caja abierta";
  return status;
}
