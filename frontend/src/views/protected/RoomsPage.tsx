import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { type RoomStatus } from "../../api/rooms";
import { useSubscriptionStatus } from "../../hooks/useSubscription";
import { roomStatusLabel, useRooms } from "../../hooks/useRooms";

const statusColors: Record<RoomStatus, string> = {
  available: "bg-emerald-100 text-emerald-800",
  occupied: "bg-rose-100 text-rose-800",
  cleaning: "bg-amber-100 text-amber-800",
  maintenance: "bg-orange-100 text-orange-800",
  blocked: "bg-slate-200 text-slate-700"
};

const statusOptions: RoomStatus[] = ["available", "occupied", "cleaning"];

export function RoomsPage() {
  const { roomsQuery, categoriesQuery, updateStatusMutation } = useRooms();
  const rooms = roomsQuery.data || [];
  const categories = categoriesQuery.data || [];
  const [pendingRoom, setPendingRoom] = useState<number | null>(null);
  const { data: subscription } = useSubscriptionStatus();

  const writeBlocked = subscription?.can_write === false;
  const inactiveSubscription = subscription && subscription.status !== "active";
  const actionsBlocked = Boolean(subscription) && (writeBlocked || inactiveSubscription);
  const blockReason = actionsBlocked
    ? writeBlocked
      ? "Suscripción en modo solo lectura: reactivá tu plan para habilitar cambios."
      : "Suscripción inactiva. Reactivá el plan para operar."
    : null;

  const categoryById = useMemo(() => {
    const map = new Map<number, { name: string; code: string; base_price_per_night: number }>();
    categories.forEach((cat) => map.set(cat.id, { name: cat.name, code: cat.code, base_price_per_night: cat.base_price_per_night }));
    return map;
  }, [categories]);

  const stats = useMemo(() => {
    return rooms.reduce(
      (acc, room) => {
        acc[room.status] = (acc[room.status] || 0) + 1;
        return acc;
      },
      {} as Record<RoomStatus, number>
    );
  }, [rooms]);

  const handleStatusUpdate = (roomId: number, status: RoomStatus) => {
    if (actionsBlocked) return;
    setPendingRoom(roomId);
    updateStatusMutation.mutate(
      { roomId, status },
      {
        onSettled: () => setPendingRoom(null)
      }
    );
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
          <h1 className="text-2xl font-semibold text-slate-900">Habitaciones</h1>
          <p className="text-sm text-slate-600">Inventario en vivo con actualización de estado (libre, ocupada, limpieza).</p>
        </div>
        {roomsQuery.isFetching && <p className="text-xs text-slate-500">Actualizando estado...</p>}
      </header>

      {actionsBlocked && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {blockReason}{" "}
          <Link to="/settings/subscription" className="font-semibold underline">
            Ir a Suscripción
          </Link>
          .
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <StatusBadge label="Libres" value={stats.available ?? 0} className={statusColors.available} />
        <StatusBadge label="Ocupadas" value={stats.occupied ?? 0} className={statusColors.occupied} />
        <StatusBadge label="En limpieza" value={stats.cleaning ?? 0} className={statusColors.cleaning} />
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Inventario</p>
            <h2 className="text-lg font-semibold text-slate-900">Habitaciones ({rooms.length})</h2>
            {roomsQuery.error && <p className="text-xs text-rose-700">No se pudo cargar: {(roomsQuery.error as Error).message}</p>}
          </div>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {rooms.map((room) => {
            const category = categoryById.get(room.category_id);
            return (
              <div key={room.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">Hab. {room.room_number}</p>
                    <h2 className="text-lg font-semibold text-slate-900">{category?.name || room.category?.name || `Categoría ${room.category_id}`}</h2>
                    <p className="text-xs text-slate-500">
                      Piso {room.floor} · {category?.code || room.category?.code || "sin código"} · $
                      {category?.base_price_per_night || room.category?.base_price_per_night || "?"}/noche
                    </p>
                  </div>
                  <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusColors[room.status]}`}>
                    {roomStatusLabel[room.status]}
                  </span>
                </div>
                <p className="mt-3 text-sm text-slate-700">{room.notes || "Sin notas"}</p>
                <div className="mt-4 text-xs text-slate-600">
                  <select
                    value={room.status}
                    onChange={(e) => handleStatusUpdate(room.id, e.target.value as RoomStatus)}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-brand-400 focus:outline-none disabled:bg-slate-50"
                    disabled={actionsBlocked || (pendingRoom === room.id && updateStatusMutation.isLoading)}
                  >
                    {statusOptions.map((status) => (
                      <option key={status} value={status}>
                        {roomStatusLabel[status]}
                      </option>
                    ))}
                    <option value="maintenance">Mantenimiento</option>
                    <option value="blocked">Bloqueada</option>
                  </select>
                  {pendingRoom === room.id && updateStatusMutation.isLoading && (
                    <p className="mt-2 text-xs text-slate-500">Guardando...</p>
                  )}
                </div>
              </div>
            );
          })}
          {!roomsQuery.isLoading && rooms.length === 0 && (
            <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
              No hay habitaciones cargadas en el sistema.
            </div>
          )}
        </div>
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
