import { useMemo } from "react";
import { Link } from "react-router-dom";

import { type ReservationStatus } from "../../api/reservations";
import { useReservations } from "../../hooks/useReservations";
import { useRooms } from "../../hooks/useRooms";

const currency = new Intl.NumberFormat("es-AR", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

const statusClass = (status: ReservationStatus) => {
  switch (status) {
    case "checked_in":
      return "bg-emerald-100 text-emerald-800";
    case "checked_out":
      return "bg-sky-100 text-sky-800";
    case "fully_paid":
      return "bg-slate-100 text-slate-800";
    case "deposit_paid":
      return "bg-amber-100 text-amber-800";
    case "pending":
      return "bg-slate-100 text-slate-700";
    default:
      return "bg-rose-100 text-rose-800";
  }
};

const todayIso = () => new Date().toISOString().slice(0, 10);

export function DashboardPage() {
  const today = todayIso();
  const { data: reservations = [] } = useReservations({});
  const { roomsQuery } = useRooms();
  const rooms = roomsQuery.data || [];

  const cards = useMemo(() => {
    const occupied = rooms.filter((r) => r.status === "occupied").length;
    const occupancy = rooms.length > 0 ? Math.round((occupied / rooms.length) * 100) : 0;

    const currentMonth = new Date(today).getMonth();
    const adrBase = reservations.filter((r) => new Date(r.check_in_date).getMonth() === currentMonth);
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
      { label: "Ocupación hoy", value: `${occupancy}%`, helper: `${arrivalsToday} llegadas` },
      { label: "ADR", value: currency.format(Math.round(adr || 0)), helper: "Tarifa promedio mes" },
      { label: "Revenue mes", value: currency.format(Math.round(revenue || 0)), helper: `${departuresToday} salidas hoy` }
    ];
  }, [reservations, rooms, today]);

  const arrivals = useMemo(
    () =>
      [...reservations]
        .sort((a, b) => a.check_in_date.localeCompare(b.check_in_date))
        .slice(0, 5),
    [reservations]
  );

  const activities = useMemo(() => {
    const list = reservations
      .filter((r) => r.check_in_date === today || r.check_out_date === today || r.status === "cancelled")
      .slice(0, 6);
    return list.map((r) => ({
      key: r.id,
      description:
        r.check_in_date === today
          ? `Check-in previsto ${r.confirmation_code}`
          : r.check_out_date === today
            ? `Checkout previsto ${r.confirmation_code}`
            : `Reserva cancelada ${r.confirmation_code}`,
      tone: r.status === "cancelled" ? "warning" : "info"
    }));
  }, [reservations, today]);

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Dashboard</p>
          <h1 className="text-2xl font-semibold text-slate-900">Visión general</h1>
          <p className="text-sm text-slate-600">KPIs en vivo y próximas llegadas/salidas para el hotel activo.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/reservas"
            className="rounded-lg border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100"
          >
            Nueva reserva
          </Link>
          <Link
            to="/habitaciones"
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300"
          >
            Asignar habitación
          </Link>
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        {cards.map((card) => (
          <div key={card.label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-sm text-slate-500">{card.label}</p>
            <div className="mt-2 text-3xl font-semibold text-slate-900">{card.value}</div>
            <p className="text-xs text-slate-500">{card.helper}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm lg:col-span-2">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Pipeline</p>
              <h2 className="text-lg font-semibold text-slate-900">Próximas reservas</h2>
            </div>
            <Link to="/reservas" className="text-sm text-brand-700 hover:underline">
              Ver todas
            </Link>
          </div>
          <div className="mt-3 overflow-hidden rounded-lg border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Código</th>
                  <th className="px-4 py-2">Huésped</th>
                  <th className="px-4 py-2">Fechas</th>
                  <th className="px-4 py-2">Estado</th>
                  <th className="px-4 py-2 text-right">Monto</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {arrivals.map((reservation) => (
                  <tr key={reservation.id} className="hover:bg-slate-50/60">
                    <td className="px-4 py-2 font-medium text-slate-900">{reservation.confirmation_code}</td>
                    <td className="px-4 py-2 text-slate-600">Huésped #{reservation.guest_id}</td>
                    <td className="px-4 py-2 text-slate-600">
                      {reservation.check_in_date} - {reservation.check_out_date}
                    </td>
                    <td className="px-4 py-2">
                      <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(reservation.status)}`}>
                        {reservation.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right font-semibold text-slate-900">{currency.format(reservation.total_amount ?? 0)}</td>
                  </tr>
                ))}
                {arrivals.length === 0 && (
                  <tr>
                    <td className="px-4 py-3 text-sm text-slate-500" colSpan={5}>
                      Sin próximas reservas.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-slate-500">Actividad</p>
          <h2 className="text-lg font-semibold text-slate-900">Hoy</h2>
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
            {activities.length === 0 && <p className="text-sm text-slate-500">Sin actividad para hoy.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
