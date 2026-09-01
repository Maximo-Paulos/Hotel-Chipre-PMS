import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

import { usePendingReservationActions, useReservations } from "../../hooks/useReservations";
import { useReservationDrawer } from "../../hooks/useReservationDrawer";
import { useRooms } from "../../hooks/useRooms";
import { formatMoney, resolveSingleCurrencyCode } from "../../utils/currency";
import { todayIso } from "../../utils/date";
// Single source of truth for reservation status colors/labels (also used by
// ReservationsPage, the detail drawer, the global search and the occupancy
// grid). The dashboard used to keep its own copy with different colors and
// no Spanish label, so the same "fully_paid" reservation showed as a plain
// grey "fully_paid" pill here but a green "Pago completo" pill everywhere
// else -- fixed by reusing the shared config instead of re-deriving it.
import { reservationStatusConfig } from "../../utils/reservationStatus";

const monthRangeIso = (base: Date) => {
  const pad = (part: number) => String(part).padStart(2, "0");
  const format = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const start = new Date(base.getFullYear(), base.getMonth(), 1);
  const end = new Date(base.getFullYear(), base.getMonth() + 1, 0);
  return { fromDate: format(start), toDate: format(end) };
};
const reservationGuestLabel = (
  reservation: {
    guest?: { first_name: string; last_name: string } | null;
    guest_id: number;
  },
  t: TFunction
) => (reservation.guest ? `${reservation.guest.first_name} ${reservation.guest.last_name}`.trim() : t("guestFallback", { id: reservation.guest_id }));

export function DashboardPage() {
  const { t } = useTranslation("dashboard");
  const today = todayIso();
  // KPI cards (ADR/revenue/arrivals-departures today) and "today" activity
  // need every reservation touching the current month, not just the most
  // recently created ones -- scope by date range instead of by count so the
  // A2 pagination fix doesn't silently corrupt these numbers. `today` always
  // falls inside this range, so today's check-ins/check-outs are covered.
  const { fromDate: monthFrom, toDate: monthTo } = useMemo(() => monthRangeIso(new Date()), []);
  const { data: reservations = [] } = useReservations({ fromDate: monthFrom, toDate: monthTo, order: "check_in", limit: 200 });
  // Upcoming reservations widget: the 10 most recently booked reservations,
  // newest first -- what the user asked this widget to show.
  const { data: recentReservations = [] } = useReservations({ limit: 10, order: "recent" });
  const pendingActionsQuery = usePendingReservationActions(8);
  const { openReservation } = useReservationDrawer();
  const { roomsQuery } = useRooms();
  const rooms = useMemo(() => roomsQuery.data || [], [roomsQuery.data]);
  const pendingActions = pendingActionsQuery.data || [];
  const criticalPendingActions = pendingActions.filter((item) => item.priority === "critical").length;

  const cards = useMemo(() => {
    const occupied = rooms.filter((r) => r.status === "occupied").length;
    const occupancy = rooms.length > 0 ? Math.round((occupied / rooms.length) * 100) : 0;

    const currentMonth = new Date(today).getMonth();
    const adrBase = reservations.filter((r) => new Date(r.check_in_date).getMonth() === currentMonth);
    const monthCurrencyCode = resolveSingleCurrencyCode(adrBase.map((r) => r.currency_code));
    const adr =
      adrBase.length > 0
        ? adrBase.reduce((acc, r) => {
            const nights = r.nights && r.nights > 0 ? r.nights : 1;
            return acc + (r.total_amount || 0) / nights;
          }, 0) / adrBase.length
        : 0;

    const revenue = adrBase.reduce((acc, r) => acc + (r.total_amount || 0), 0);
    const arrivalsToday = reservations.filter((r) => r.check_in_date === today).length;
    const departuresToday = reservations.filter((r) => r.check_out_date === today).length;

    return [
      { label: t("cards.occupancyToday.label"), value: `${occupancy}%`, helper: t("cards.occupancyToday.helper", { count: arrivalsToday }) },
      {
        label: t("cards.adr.label"),
        value: monthCurrencyCode ? formatMoney(Math.round(adr || 0), monthCurrencyCode) : t("cards.multiCurrency"),
        helper: monthCurrencyCode ? t("cards.adr.helperSingle") : t("cards.adr.helperMulti")
      },
      {
        label: t("cards.revenue.label"),
        value: monthCurrencyCode ? formatMoney(Math.round(revenue || 0), monthCurrencyCode) : t("cards.multiCurrency"),
        helper: monthCurrencyCode ? t("cards.revenue.helperSingle", { count: departuresToday }) : t("cards.revenue.helperMulti")
      },
      {
        label: t("cards.pendingActions.label"),
        value: String(pendingActions.length),
        helper: criticalPendingActions > 0 ? t("cards.pendingActions.helperCritical", { count: criticalPendingActions }) : t("cards.pendingActions.helperNone")
      }
    ];
  }, [criticalPendingActions, pendingActions.length, reservations, rooms, today, t]);

  const arrivals = useMemo(
    () =>
      [...recentReservations]
        .sort((a, b) => a.check_in_date.localeCompare(b.check_in_date))
        .slice(0, 5),
    [recentReservations]
  );

  const activities = useMemo(() => {
    const list = reservations
      .filter((r) => r.check_in_date === today || r.check_out_date === today || r.status === "cancelled")
      .slice(0, 6);
    return list.map((r) => ({
      key: r.id,
      description:
        r.check_in_date === today
          ? t("activity.checkIn", { code: r.confirmation_code })
          : r.check_out_date === today
            ? t("activity.checkOut", { code: r.confirmation_code })
            : t("activity.cancelled", { code: r.confirmation_code }),
      tone: r.status === "cancelled" ? "warning" : "info"
    }));
  }, [reservations, today, t]);

  return (
    <div className="min-w-0 space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">{t("eyebrow")}</p>
          <h1 className="text-2xl font-semibold text-slate-900">{t("title")}</h1>
          <p className="text-sm text-slate-600">{t("subtitle")}</p>
          <span className="sr-only" data-testid="dashboard-today-date">{today}</span>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/reservas?crear=1"
            className="rounded-lg border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100"
          >
            {t("actions.newReservation")}
          </Link>
          <Link
            to="/habitaciones"
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300"
          >
            {t("actions.assignRoom")}
          </Link>
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-4">
        {cards.map((card) => (
          <div key={card.label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-sm text-slate-500">{card.label}</p>
            <div className="mt-2 text-3xl font-semibold text-slate-900">{card.value}</div>
            <p className="text-xs text-slate-500">{card.helper}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="min-w-0 rounded-xl border border-slate-200 bg-white p-4 shadow-sm lg:col-span-2">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">{t("pipeline.eyebrow")}</p>
              <h2 className="text-lg font-semibold text-slate-900">{t("pipeline.title")}</h2>
            </div>
            <Link to="/reservas" className="text-sm text-brand-700 hover:underline">
              {t("pipeline.viewAll")}
            </Link>
          </div>
          <div className="mt-3 hidden overflow-x-auto rounded-lg border border-slate-200 sm:block">
            <table className="w-full min-w-[640px] divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">{t("pipeline.table.code")}</th>
                  <th className="px-4 py-2">{t("pipeline.table.guest")}</th>
                  <th className="px-4 py-2">{t("pipeline.table.dates")}</th>
                  <th className="px-4 py-2">{t("pipeline.table.status")}</th>
                  <th className="px-4 py-2 text-right">{t("pipeline.table.amount")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {arrivals.map((reservation) => (
                  <tr key={reservation.id} className="hover:bg-slate-50/60">
                    <td className="px-4 py-2 font-medium text-slate-900">
                      <button
                        type="button"
                        onClick={() => openReservation(reservation.id)}
                        className="text-brand-700 hover:underline"
                      >
                        {reservation.confirmation_code}
                      </button>
                    </td>
                    <td className="px-4 py-2 text-slate-600">{reservationGuestLabel(reservation, t)}</td>
                    <td className="px-4 py-2 text-slate-600">
                      {reservation.check_in_date} - {reservation.check_out_date}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`rounded-full px-2 py-1 text-xs font-semibold ${reservationStatusConfig[reservation.status]?.className ?? "bg-slate-100 text-slate-800"}`}
                      >
                        {reservationStatusConfig[reservation.status]?.label ?? reservation.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right font-semibold text-slate-900">
                      {formatMoney(reservation.total_amount ?? 0, reservation.currency_code)}
                    </td>
                  </tr>
                ))}
                {arrivals.length === 0 && (
                  <tr>
                    <td className="px-4 py-3 text-sm text-slate-500" colSpan={5}>
                      {t("pipeline.empty")}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="mt-3 space-y-2 sm:hidden" data-testid="dashboard-mobile-reservations">
            {arrivals.map((reservation) => (
              <article key={reservation.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <button
                      type="button"
                      onClick={() => openReservation(reservation.id)}
                      className="truncate text-sm font-semibold text-brand-700 hover:underline"
                    >
                      {reservation.confirmation_code}
                    </button>
                    <p className="mt-1 break-words text-sm text-slate-600">{reservationGuestLabel(reservation, t)}</p>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2 py-1 text-xs font-semibold ${reservationStatusConfig[reservation.status]?.className ?? "bg-slate-100 text-slate-800"}`}
                  >
                    {reservationStatusConfig[reservation.status]?.label ?? reservation.status}
                  </span>
                </div>
                <dl className="mt-3 grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <dt className="text-slate-500">{t("pipeline.table.dates")}</dt>
                    <dd className="mt-1 break-words font-medium text-slate-700">
                      {reservation.check_in_date} - {reservation.check_out_date}
                    </dd>
                  </div>
                  <div className="text-right">
                    <dt className="text-slate-500">{t("pipeline.table.amount")}</dt>
                    <dd className="mt-1 font-semibold text-slate-900">
                      {formatMoney(reservation.total_amount ?? 0, reservation.currency_code)}
                    </dd>
                  </div>
                </dl>
              </article>
            ))}
            {arrivals.length === 0 && <p className="text-sm text-slate-500">{t("pipeline.empty")}</p>}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-slate-500">{t("activity.eyebrow")}</p>
          <h2 className="text-lg font-semibold text-slate-900">{t("activity.title")}</h2>
          <div className="mt-3 space-y-3">
            {activities.map((activity) => (
              <div
                key={activity.key}
                className={`rounded-lg border px-3 py-2 text-sm ${
                  activity.tone === "warning" ? "border-amber-200 bg-amber-50 text-amber-900" : "border-slate-200 bg-slate-50 text-slate-800"
                }`}
              >
                <div className="text-xs font-semibold">{today}</div>
                <div>{activity.description}</div>
              </div>
            ))}
            {activities.length === 0 && <p className="text-sm text-slate-500">{t("activity.empty")}</p>}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">{t("operations.eyebrow")}</p>
            <h2 className="text-lg font-semibold text-slate-900">{t("operations.title")}</h2>
          </div>
          <Link to="/reservas" className="text-sm font-semibold text-brand-700 hover:underline">
            {t("operations.goToReservations")}
          </Link>
        </div>
        <div className="mt-3 space-y-3">
          {pendingActionsQuery.isLoading ? (
            <p className="text-sm text-slate-500">{t("operations.loading")}</p>
          ) : pendingActions.length === 0 ? (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              {t("operations.empty")}
            </div>
          ) : (
            pendingActions.map((action) => (
              <div key={action.action_key} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-full px-2 py-1 text-[11px] font-semibold ${
                          action.priority === "critical"
                            ? "bg-rose-100 text-rose-800"
                            : action.priority === "high"
                              ? "bg-amber-100 text-amber-800"
                              : action.priority === "medium"
                                ? "bg-sky-100 text-sky-800"
                                : "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {action.priority}
                      </span>
                      <span className="text-xs font-semibold text-slate-700">{action.confirmation_code}</span>
                      {action.guest_name && (
                        <span className="text-xs text-slate-600">{action.guest_name}</span>
                      )}
                    </div>
                    <p className="mt-1 text-sm font-semibold text-slate-900">{action.title}</p>
                    <p className="text-sm text-slate-600">{action.detail}</p>
                  </div>
                  <div className="text-right text-xs text-slate-500">
                    <p>
                      {action.check_in_date} → {action.check_out_date}
                    </p>
                    <p>{action.source_provider_code || action.source}</p>
                  </div>
                </div>
                <div className="mt-2 flex justify-end">
                  <button
                    type="button"
                    onClick={() => openReservation(action.reservation_id)}
                    className="inline-flex min-h-11 items-center rounded-lg border border-brand-200 bg-white px-3 py-1 text-xs font-semibold text-brand-700 hover:bg-brand-50"
                  >
                    {t("operations.viewReservation")}
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
