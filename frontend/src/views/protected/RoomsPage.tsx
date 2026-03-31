import { mockRooms } from "../../data/mock";

const statusColors: Record<string, string> = {
  Libre: "bg-emerald-100 text-emerald-800",
  Ocupada: "bg-rose-100 text-rose-800",
  Limpieza: "bg-amber-100 text-amber-800"
};

export function RoomsPage() {
  const stats = mockRooms.reduce(
    (acc, room) => {
      acc[room.status] = (acc[room.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
          <h1 className="text-2xl font-semibold text-slate-900">Habitaciones</h1>
          <p className="text-sm text-slate-600">Inventario rápido con estado mockeado (libre, ocupada, limpieza).</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="rounded-lg border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100">
            Agregar habitación
          </button>
          <button className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300">
            Reasignar limpieza
          </button>
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <StatusBadge label="Libres" value={stats.Libre ?? 0} className={statusColors.Libre} />
        <StatusBadge label="Ocupadas" value={stats.Ocupada ?? 0} className={statusColors.Ocupada} />
        <StatusBadge label="En limpieza" value={stats.Limpieza ?? 0} className={statusColors.Limpieza} />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {mockRooms.map((room) => (
          <div key={room.number} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Hab. {room.number}</p>
                <h2 className="text-lg font-semibold text-slate-900">{room.category}</h2>
                <p className="text-xs text-slate-500">Piso {room.floor}</p>
              </div>
              <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusColors[room.status]}`}>
                {room.status}
              </span>
            </div>
            <p className="mt-3 text-sm text-slate-700">{room.note || "Sin notas"}</p>
            <div className="mt-4 flex gap-2 text-xs text-slate-600">
              <button className="rounded-lg border border-slate-200 px-2 py-1 hover:border-slate-300">Detalle</button>
              <button className="rounded-lg border border-slate-200 px-2 py-1 hover:border-slate-300">Mover</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatusBadge({ label, value, className }: { label: string; value: number; className: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">{label}</p>
        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${className}`}>{value}</span>
      </div>
    </div>
  );
}
