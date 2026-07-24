import { useMemo, useState } from "react";

import { type OperationalReservationGroup, type OperationalReservationSummary } from "../../api/reports";
import { ApiError } from "../../api/client";
import { useDailyOperationalReport, useOperationalAlerts } from "../../hooks/useReports";

const today = () => new Date().toISOString().slice(0, 10);

const money = (value?: number | string | null) =>
  Number(value ?? 0).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

export function ReportsPage() {
  const [reportDate, setReportDate] = useState(today());
  const reportQuery = useDailyOperationalReport(reportDate);
  const alertsQuery = useOperationalAlerts(reportDate);
  const report = reportQuery.data;
  const alerts = alertsQuery.data?.alerts ?? report?.alerts ?? [];

  const pendingTotal = useMemo(() => {
    return (report?.pending_payments.reservations ?? []).reduce((total, reservation) => {
      return total + Number(reservation.balance_due ?? 0);
    }, 0);
  }, [report?.pending_payments.reservations]);

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operacion</p>
          <h1 className="text-2xl font-semibold text-slate-900">Reportes</h1>
          <p className="text-sm text-slate-600">Reporte diario operativo con pagos pendientes, movimientos del dia, bloqueos y caja.</p>
        </div>
        <label className="space-y-1 text-sm">
          <span className="text-slate-600">Fecha</span>
          <input
            type="date"
            value={reportDate}
            onChange={(event) => setReportDate(event.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2"
          />
        </label>
      </header>

      {(reportQuery.error || alertsQuery.error) && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-3 text-sm text-rose-800" role="alert">
          <p>{reportsErrorMessage(reportQuery.error || alertsQuery.error)}</p>
          <button
            type="button"
            onClick={() => {
              void reportQuery.refetch();
              void alertsQuery.refetch();
            }}
            disabled={reportQuery.isFetching || alertsQuery.isFetching}
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
            <Metric label="Pagos pendientes" value={money(pendingTotal)} />
            <Metric label="Alertas" value={String(alerts.length)} />
          </div>

          <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
            <div className="space-y-4">
              <ReservationGroup title="Llegadas del dia" group={report.arrivals} emptyText="No hay llegadas para esta fecha." />
              <ReservationGroup title="Salidas del dia" group={report.departures} emptyText="No hay salidas para esta fecha." />
              <ReservationGroup
                title="Pagos pendientes"
                group={report.pending_payments}
                emptyText="No hay pagos pendientes en el reporte."
                showBalance
              />
            </div>

            <aside className="space-y-4">
              <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Caja</p>
                  <h2 className="text-lg font-semibold text-slate-900">Estado operativo</h2>
                </div>
                <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
                  <p className="font-semibold text-slate-900">{cashStatusLabel(report.cash_session.status)}</p>
                  <p className="text-xs text-slate-500">
                    {report.cash_session.session_id ? `Caja #${report.cash_session.session_id}` : "Sin sesion abierta"}
                  </p>
                  {report.cash_session.opened_at ? (
                    <p className="text-xs text-slate-500">Abierta {new Date(report.cash_session.opened_at).toLocaleString("es-AR")}</p>
                  ) : null}
                </div>
              </section>

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
                        <p className="font-semibold text-slate-900">Hab. {block.room_number || block.room_id}</p>
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
  return (
    <div className="grid gap-2 px-4 py-3 text-sm md:grid-cols-[1fr_auto]">
      <div>
        <p className="font-semibold text-slate-900">
          {reservation.guest_name || `Huesped #${reservation.guest_id}`} - {reservation.confirmation_code}
        </p>
        <p className="text-xs text-slate-500">
          Hab. {reservation.room_number || reservation.room_id || "sin asignar"} - {reservation.status} - {reservation.check_in_date} a {reservation.check_out_date}
        </p>
      </div>
      {showBalance ? <p className="font-semibold text-slate-900">{money(reservation.balance_due)}</p> : null}
    </div>
  );
}

function cashStatusLabel(status: string) {
  if (status === "open") return "Caja abierta";
  if (status === "closed") return "Caja cerrada";
  if (status === "missing") return "Sin caja abierta";
  return status;
}
