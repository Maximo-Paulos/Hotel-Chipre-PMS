import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

import { usePendingReservationActions, useReservations } from "../../hooks/useReservations";
import { useBookedValueReport, useOccupancyReport, useTodayArrivalCount } from "../../hooks/useReports";
import { isDeferredCompanyReservation } from "../../api/reservations";
import { usePendingCashCloseReports } from "../../hooks/useCashRegister";
import { useHotelConfig } from "../../hooks/useHotelConfig";
import { useEffectivePermissions } from "../../hooks/usePermissions";
import { useReservationDrawer } from "../../hooks/useReservationDrawer";
import { formatMoney } from "../../utils/currency";
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
  const year = base.getFullYear();
  const month = base.getMonth() + 1;
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return {
    fromDate: `${year}-${pad(month)}-01`,
    toDate: `${year}-${pad(month)}-${pad(lastDay)}`
  };
};

const hotelTodayIso = (timeZone?: string | null, serverDate?: string | null) => {
  if (timeZone) {
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
      // Fall through to the hotel-local date supplied by the reports API.
    }
  }
  return serverDate && /^\d{4}-\d{2}-\d{2}$/.test(serverDate) ? serverDate : todayIso();
};

type DashboardCard = {
  label: string;
  value: string;
  helper: string;
  helperRole?: "status" | "alert";
  testId?: string;
  retry?: { label: string; run: () => void; disabled: boolean };
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
  const hotelConfigQuery = useHotelConfig();
  const arrivalCountQuery = useTodayArrivalCount();
  const today = hotelTodayIso(hotelConfigQuery.data?.hotel_timezone, arrivalCountQuery.data?.report_date);
  // The reservation list supports dashboard activity and remains paginated.
  // Financial KPIs use the separate permission-protected server aggregate.
  const { fromDate: monthFrom, toDate: monthTo } = useMemo(() => monthRangeIso(new Date(`${today}T00:00:00`)), [today]);
  const reservationsQuery = useReservations({ fromDate: monthFrom, toDate: monthTo, order: "check_in", limit: 200 });
  const reservations = useMemo(() => reservationsQuery.data ?? [], [reservationsQuery.data]);
  const { hasPermission } = useEffectivePermissions();
  const canViewFinancial = hasPermission("reports:financial:view");
  const canViewOperationalReports = hasPermission("reports:operational:view");
  const occupancyQuery = useOccupancyReport(today, today, canViewOperationalReports);
  // The monthly financial cards use the permission-protected server aggregate,
  // not this paginated reservation list (which is capped for activity views).
  const bookedValueQuery = useBookedValueReport(monthFrom, monthTo, canViewFinancial);
  // Upcoming arrivals are filtered and ordered by the server from the
  // hotel's local day. This avoids hiding an arrival merely because newer
  // reservations were created afterwards.
  const upcomingReservationsQuery = useReservations({ upcomingOnly: true, order: "check_in", limit: 5 });
  const upcomingReservations = upcomingReservationsQuery.data ?? [];
  const pendingActionsQuery = usePendingReservationActions(8);
  const canApproveCashDifferences = hasPermission("cash:approve_difference");
  const pendingCashApprovalsQuery = usePendingCashCloseReports({ enabled: canApproveCashDifferences });
  const pendingCashApprovals = pendingCashApprovalsQuery.data ?? [];
  const { openReservation } = useReservationDrawer();
  const pendingActions = pendingActionsQuery.data || [];
  const criticalPendingActions = pendingActions.filter((item) => item.priority === "critical").length;
  const occupancyReport = occupancyQuery.data;
  const occupancyLoading = occupancyQuery.isLoading;
  const occupancyError = occupancyQuery.isError;
  const occupancyFetching = occupancyQuery.isFetching;
  const refetchOccupancy = occupancyQuery.refetch;

  const cards = useMemo<DashboardCard[]>(() => {
    const occupancy = occupancyReport?.daily[0];
    const occupancyLoadingText = t("cards.occupancyToday.loading");
    const occupancyErrorText = t("cards.occupancyToday.error");
    const noActiveRoomsText = t("cards.occupancyToday.noActiveRooms");
    const noOccupancyDataText = t("cards.occupancyToday.noData");
    const occupancyUnavailableText = t("cards.occupancyToday.permissionUnavailable");

    const bookedCurrencies = bookedValueQuery.data?.by_currency ?? [];
    const hasBookedReservations = bookedCurrencies.length > 0;
    const reservationValueByCurrency = bookedCurrencies
      .map((item) => formatMoney(Number(item.amount), item.currency_code))
      .join(" · ");
    const averageBookedPerNightByCurrency = bookedCurrencies
      .filter((item) => item.booked_night_count > 0)
      .map((item) => formatMoney(Math.round(Number(item.amount) / item.booked_night_count), item.currency_code))
      .join(" · ");
    const arrivalsToday = arrivalCountQuery.data?.count;

    const occupancyHelper = !canViewOperationalReports
      ? occupancyUnavailableText
      : occupancyLoading
        ? occupancyLoadingText
        : occupancyError
          ? occupancyErrorText
          : occupancyReport?.total_rooms === 0
            ? noActiveRoomsText
            : !occupancy
              ? noOccupancyDataText
              : arrivalCountQuery.isLoading
                ? t("cards.occupancyToday.helperLoading")
                : arrivalCountQuery.isError
                  ? t("cards.occupancyToday.helperError")
                  : t("cards.occupancyToday.helper", { count: arrivalsToday ?? 0 });

    return [
      {
        label: t("cards.occupancyToday.label"),
        value: !canViewOperationalReports || occupancyLoading || occupancyError || !occupancy
          ? "—"
          : `${occupancy.rate}%`,
        helper: occupancyHelper,
        helperRole: occupancyError || (!arrivalCountQuery.isLoading && arrivalCountQuery.isError)
          ? "alert"
          : occupancyLoading || arrivalCountQuery.isLoading
            ? "status"
            : undefined,
        testId: "dashboard-occupancy-card",
        ...(canViewOperationalReports && occupancyError ? {
          retry: {
            label: t("cards.occupancyToday.retry"),
            run: () => void refetchOccupancy(),
            disabled: occupancyFetching
          }
        } : {})
      },
      ...(canViewFinancial ? [{
        label: t("cards.adr.label"),
        value: bookedValueQuery.isLoading
          ? t("cards.revenue.helperLoading")
          : bookedValueQuery.isError
            ? "—"
            : !hasBookedReservations
              ? t("cards.noReservations")
              : averageBookedPerNightByCurrency,
        helper: bookedValueQuery.isLoading
          ? t("cards.revenue.helperLoading")
          : bookedValueQuery.isError
            ? t("cards.revenue.helperError")
          : !hasBookedReservations
            ? t("cards.adr.helperEmpty")
            : bookedCurrencies.length > 1
              ? t("cards.adr.helperMulti")
              : t("cards.adr.helperSingle")
      }, {
        label: t("cards.revenue.label"),
        value: bookedValueQuery.isLoading
          ? t("cards.revenue.helperLoading")
          : bookedValueQuery.isError
            ? "—"
            : hasBookedReservations
              ? reservationValueByCurrency
              : t("cards.noReservations"),
        helper: bookedValueQuery.isLoading
          ? t("cards.revenue.helperLoading")
          : bookedValueQuery.isError
            ? t("cards.revenue.helperError")
            : hasBookedReservations
              ? t("cards.revenue.helperSingle")
              : t("cards.revenue.helperEmpty")
      }] : []),
      {
        label: t("cards.pendingActions.label"),
        value: pendingActionsQuery.isError ? "—" : String(pendingActions.length),
        helper: pendingActionsQuery.isError
          ? t("cards.pendingActions.helperError")
          : criticalPendingActions > 0
            ? t("cards.pendingActions.helperCritical", { count: criticalPendingActions })
            : t("cards.pendingActions.helperNone"),
        helperRole: pendingActionsQuery.isError ? "alert" : undefined
      }
    ];
  }, [arrivalCountQuery.data?.count, arrivalCountQuery.isError, arrivalCountQuery.isLoading, bookedValueQuery.data, bookedValueQuery.isError, bookedValueQuery.isLoading, canViewFinancial, canViewOperationalReports, criticalPendingActions, occupancyError, occupancyFetching, occupancyLoading, occupancyReport, pendingActions.length, pendingActionsQuery.isError, refetchOccupancy, t]);

  const arrivals = upcomingReservations;

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
          <h1 className="text-balance text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">{t("title")}</h1>
          <p className="text-sm text-slate-600">{t("subtitle")}</p>
          <span className="sr-only" data-testid="dashboard-today-date">{today}</span>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/reservas?crear=1"
            className="rounded-control bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-raise hover:bg-brand-700 active:scale-[0.98]"
          >
            {t("actions.newReservation")}
          </Link>
          <Link
            to="/habitaciones"
            className="rounded-control bg-white px-4 py-2 text-sm font-semibold text-slate-700 ring-1 ring-slate-900/10 hover:bg-slate-50 active:scale-[0.98]"
          >
            {t("actions.assignRoom")}
          </Link>
        </div>
      </header>

      <div className={`grid gap-4 ${canViewFinancial ? "md:grid-cols-4" : "md:grid-cols-2"}`}>
        {cards.map((card) => (
          <div key={card.label} className="rounded-panel bg-white p-5 shadow-raise ring-1 ring-slate-900/5" data-testid={card.testId}>
            <p className="text-sm text-slate-500">{card.label}</p>
            <div className="numeric mt-2 break-words text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">{card.value}</div>
            <p className="text-xs text-slate-500" role={card.helperRole}>{card.helper}</p>
            {card.retry ? (
              <button
                type="button"
                onClick={card.retry.run}
                disabled={card.retry.disabled}
                className="mt-2 min-h-11 rounded-lg border border-rose-300 bg-white px-3 py-1 text-xs font-semibold text-rose-800 hover:bg-rose-100 disabled:opacity-60"
              >
                {card.retry.label}
              </button>
            ) : null}
          </div>
        ))}
      </div>

      {canApproveCashDifferences && (pendingCashApprovalsQuery.isError || pendingCashApprovals.length > 0) ? (
        <section className="flex flex-col gap-3 rounded-panel border border-amber-200 bg-amber-50 p-5 shadow-raise sm:flex-row sm:items-center sm:justify-between" data-testid="dashboard-cash-approvals">
          <div>
            <h2 className="font-semibold text-amber-950">{t("cashApprovals.title")}</h2>
            <p className="text-sm text-amber-900">
              {pendingCashApprovalsQuery.isError
                ? t("cashApprovals.error")
                : t("cashApprovals.count", { count: pendingCashApprovals.length })}
            </p>
          </div>
          <Link to="/caja" className="inline-flex min-h-11 items-center justify-center rounded-lg border border-amber-300 bg-white px-4 py-2 text-sm font-semibold text-amber-950 hover:bg-amber-100">
            {t("cashApprovals.view")}
          </Link>
        </section>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="min-w-0 rounded-panel bg-white p-5 shadow-raise ring-1 ring-slate-900/5 lg:col-span-2">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">{t("pipeline.eyebrow")}</p>
              <h2 className="text-lg font-semibold text-slate-900">{t("pipeline.title")}</h2>
            </div>
            <Link to="/reservas" className="text-sm text-brand-700 hover:underline">
              {t("pipeline.viewAll")}
            </Link>
          </div>
          {upcomingReservationsQuery.isLoading ? (
            <p className="mt-3 text-sm text-slate-500" role="status" data-testid="dashboard-upcoming-loading">
              {t("pipeline.loading")}
            </p>
          ) : upcomingReservationsQuery.isError ? (
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800" role="alert" data-testid="dashboard-upcoming-error">
              <span>{t("pipeline.error")}</span>
              <button
                type="button"
                onClick={() => void upcomingReservationsQuery.refetch()}
                className="min-h-11 rounded-lg border border-rose-300 bg-white px-3 py-1 text-xs font-semibold text-rose-800 hover:bg-rose-100"
              >
                {t("pipeline.retry")}
              </button>
            </div>
          ) : upcomingReservations.length === 0 ? (
            <p className="mt-3 text-sm text-slate-500" data-testid="dashboard-upcoming-empty">
              {t("pipeline.empty")}
            </p>
          ) : null}
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
                    <td className="whitespace-nowrap px-4 py-2 font-medium text-slate-900">
                      <button
                        type="button"
                        onClick={() => openReservation(reservation.id)}
                        className="text-brand-700 hover:underline"
                      >
                        {reservation.confirmation_code}
                      </button>
                    </td>
                    <td className="px-4 py-2 text-slate-600">{reservationGuestLabel(reservation, t)}</td>
                    <td className="whitespace-nowrap px-4 py-2 text-slate-600">
                      {reservation.check_in_date} - {reservation.check_out_date}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2">
                      <span
                        className={`rounded-full px-2 py-1 text-xs font-semibold ${reservationStatusConfig[reservation.status]?.className ?? "bg-slate-100 text-slate-800"}`}
                      >
                        {reservationStatusConfig[reservation.status]?.label ?? reservation.status}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 text-right font-semibold text-slate-900">
                      {isDeferredCompanyReservation(reservation)
                        ? t("pipeline.deferredCompanyBilling")
                        : formatMoney(reservation.total_amount ?? 0, reservation.currency_code)}
                    </td>
                  </tr>
                ))}
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
                      {isDeferredCompanyReservation(reservation)
                        ? t("pipeline.deferredCompanyBilling")
                        : formatMoney(reservation.total_amount ?? 0, reservation.currency_code)}
                    </dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        </div>

        <div className="rounded-panel bg-white p-5 shadow-raise ring-1 ring-slate-900/5">
          <p className="text-xs uppercase tracking-wide text-slate-500">{t("activity.eyebrow")}</p>
          <h2 className="text-lg font-semibold text-slate-900">{t("activity.title")}</h2>
          <div className="mt-3 space-y-3">
            {reservationsQuery.isLoading ? (
              <p className="text-sm text-slate-500" role="status" data-testid="dashboard-activity-loading">
                {t("activity.loading")}
              </p>
            ) : reservationsQuery.isError ? (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800" role="alert" data-testid="dashboard-activity-error">
                <span>{t("activity.error")}</span>
                <button
                  type="button"
                  onClick={() => void reservationsQuery.refetch()}
                  className="min-h-11 rounded-lg border border-rose-300 bg-white px-3 py-1 text-xs font-semibold text-rose-800 hover:bg-rose-100"
                >
                  {t("activity.retry")}
                </button>
              </div>
            ) : activities.length === 0 ? (
              <p className="text-sm text-slate-500" data-testid="dashboard-activity-empty">{t("activity.empty")}</p>
            ) : activities.map((activity) => (
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
          </div>
        </div>
      </div>

      <div className="rounded-panel bg-white p-5 shadow-raise ring-1 ring-slate-900/5">
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
            <p className="text-sm text-slate-500" role="status" data-testid="dashboard-pending-actions-loading">{t("operations.loading")}</p>
          ) : pendingActionsQuery.isError ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800" role="alert" data-testid="dashboard-pending-actions-error">
              <span>{t("operations.error")}</span>
              <button
                type="button"
                onClick={() => void pendingActionsQuery.refetch()}
                className="min-h-11 rounded-lg border border-rose-300 bg-white px-3 py-1 text-xs font-semibold text-rose-800 hover:bg-rose-100"
              >
                {t("operations.retry")}
              </button>
            </div>
          ) : pendingActions.length === 0 ? (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800" data-testid="dashboard-pending-actions-empty">
              {t("operations.empty")}
            </div>
          ) : (
            pendingActions.map((action) => (
              <div key={`${action.reservation_id}:${action.action_key}`} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
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
                        {t(`page.priority.${action.priority}`, { ns: "reservations" })}
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
                    <p>
                      {t(`page.form.sourceOptions.${action.source_provider_code || action.source}`, {
                        ns: "reservations",
                        defaultValue: action.source_provider_code || action.source
                      })}
                    </p>
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
