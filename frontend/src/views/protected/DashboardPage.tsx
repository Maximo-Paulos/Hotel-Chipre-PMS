import { Link } from "react-router-dom";

import { dashboardStats, mockActivities, mockReservations } from "../../data/mock";

const currency = new Intl.NumberFormat("es-AR", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

const statusClass = (status: string) => {
  switch (status) {
    case "check-in":
      return "bg-emerald-100 text-emerald-800";
    case "checkout":
      return "bg-sky-100 text-sky-800";
    case "confirmada":
      return "bg-slate-100 text-slate-800";
    case "no-show":
      return "bg-amber-100 text-amber-800";
    default:
      return "bg-rose-100 text-rose-800";
  }
};

export function DashboardPage() {
  const arrivals = mockReservations.slice(0, 4);

  const cards = [
    { label: "Ocupación hoy", value: `${dashboardStats.occupancy}%`, helper: `${dashboardStats.arrivalsToday} llegadas` },
    { label: "ADR", value: currency.format(dashboardStats.adr), helper: "Tarifa promedio" },
    { label: "Revenue mes", value: currency.format(dashboardStats.revenue), helper: `${dashboardStats.departuresToday} salidas hoy` }
  ];

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Dashboard</p>
          <h1 className="text-2xl font-semibold text-slate-900">Visión general</h1>
          <p className="text-sm text-slate-600">KPIs rápidos y próximas llegadas/salidas para el hotel activo.</p>
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
                  <th className="px-4 py-2">Huésped</th>
                  <th className="px-4 py-2">Habitación</th>
                  <th className="px-4 py-2">Fechas</th>
                  <th className="px-4 py-2">Estado</th>
                  <th className="px-4 py-2 text-right">Monto</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {arrivals.map((reservation) => (
                  <tr key={reservation.id} className="hover:bg-slate-50/60">
                    <td className="px-4 py-2 font-medium text-slate-900">{reservation.guest}</td>
                    <td className="px-4 py-2 text-slate-600">{reservation.room}</td>
                    <td className="px-4 py-2 text-slate-600">
                      {reservation.checkIn} - {reservation.checkOut}
                    </td>
                    <td className="px-4 py-2">
                      <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(reservation.status)}`}>
                        {reservation.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right font-semibold text-slate-900">{currency.format(reservation.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-slate-500">Actividad</p>
          <h2 className="text-lg font-semibold text-slate-900">Hoy</h2>
          <div className="mt-3 space-y-3">
            {mockActivities.map((activity) => (
              <div
                key={activity.description}
                className={`rounded-lg border px-3 py-2 text-sm ${
                  activity.tone === "warning" ? "border-amber-200 bg-amber-50 text-amber-900" : "border-slate-200 bg-slate-50 text-slate-800"
                }`}
              >
                <div className="text-xs font-semibold">{activity.time}</div>
                <div>{activity.description}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
