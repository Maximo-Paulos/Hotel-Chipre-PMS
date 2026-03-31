import { Link } from "react-router-dom";

import { mockReservations } from "../../data/mock";

const currency = new Intl.NumberFormat("es-AR", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

const statusConfig: Record<
  string,
  {
    label: string;
    className: string;
  }
> = {
  "check-in": { label: "Check-in", className: "bg-emerald-100 text-emerald-800" },
  checkout: { label: "Checkout", className: "bg-sky-100 text-sky-800" },
  confirmada: { label: "Confirmada", className: "bg-slate-100 text-slate-800" },
  "no-show": { label: "No show", className: "bg-amber-100 text-amber-800" },
  cancelada: { label: "Cancelada", className: "bg-rose-100 text-rose-800" }
};

export function ReservationsPage() {
  const today = new Date().toISOString().slice(0, 10);

  const totals = mockReservations.reduce(
    (acc, item) => {
      if (item.status === "confirmada" || item.status === "check-in") acc.active += 1;
      if (item.checkIn === today) acc.checkInsToday += 1;
      if (item.checkOut === today || item.status === "checkout") acc.checkOutsToday += 1;
      if (item.status === "cancelada") acc.cancelled += 1;
      return acc;
    },
    { active: 0, checkInsToday: 0, checkOutsToday: 0, cancelled: 0 }
  );

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
          <h1 className="text-2xl font-semibold text-slate-900">Reservas</h1>
          <p className="text-sm text-slate-600">Listado mockeado para prototipar layout y estados.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="rounded-lg border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100">
            Crear reserva
          </button>
          <button className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300">
            Exportar (mock)
          </button>
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="Activas" value={totals.active} helper="Confirmadas + check-in" />
        <StatCard label="Check-ins hoy" value={totals.checkInsToday} helper={today} />
        <StatCard label="Checkouts hoy" value={totals.checkOutsToday} helper={today} />
        <StatCard label="Canceladas" value={totals.cancelled} helper="Últimos 7 días" />
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Listado</p>
            <h2 className="text-lg font-semibold text-slate-900">Reservas recientes</h2>
          </div>
          <Link to="/dashboard" className="text-sm text-brand-700 hover:underline">
            Volver al dashboard
          </Link>
        </div>
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2">Huésped</th>
              <th className="px-4 py-2">Hab.</th>
              <th className="px-4 py-2">Ingreso</th>
              <th className="px-4 py-2">Salida</th>
              <th className="px-4 py-2">Estado</th>
              <th className="px-4 py-2">Canal</th>
              <th className="px-4 py-2 text-right">Monto</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 bg-white">
            {mockReservations.map((reservation) => {
              const cfg = statusConfig[reservation.status];
              return (
                <tr key={reservation.id} className="hover:bg-slate-50/60">
                  <td className="px-4 py-2 font-medium text-slate-900">{reservation.guest}</td>
                  <td className="px-4 py-2 text-slate-600">{reservation.room}</td>
                  <td className="px-4 py-2 text-slate-600">{reservation.checkIn}</td>
                  <td className="px-4 py-2 text-slate-600">{reservation.checkOut}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${cfg?.className ?? "bg-slate-100 text-slate-800"}`}>
                      {cfg?.label ?? reservation.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-slate-600">{reservation.channel}</td>
                  <td className="px-4 py-2 text-right font-semibold text-slate-900">{currency.format(reservation.amount)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatCard({ label, value, helper }: { label: string; value: number; helper: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <div className="mt-2 text-2xl font-semibold text-slate-900">{value}</div>
      <p className="text-xs text-slate-500">{helper}</p>
    </div>
  );
}
