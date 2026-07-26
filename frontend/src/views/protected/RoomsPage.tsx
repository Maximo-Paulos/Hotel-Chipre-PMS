import { type FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { type RoomBlockCreatePayload, type RoomBlockReasonCode } from "../../api/roomBlocks";
import { type RoomStatus } from "../../api/rooms";
import { roomBlockReasonLabel, roomBlockReasonOptions, useRoomBlocks } from "../../hooks/useRoomBlocks";
import { useSubscriptionStatus } from "../../hooks/useSubscription";
import { roomStatusLabel, useRooms } from "../../hooks/useRooms";
import { useSession } from "../../state/session";
import { todayIso } from "../../utils/date";

const statusColors: Record<RoomStatus, string> = {
  available: "bg-emerald-100 text-emerald-800",
  occupied: "bg-rose-100 text-rose-800",
  cleaning: "bg-amber-100 text-amber-800",
  maintenance: "bg-orange-100 text-orange-800",
  blocked: "bg-slate-200 text-slate-700"
};

const statusOptions: RoomStatus[] = ["available", "occupied", "cleaning"];

type BlockFormValues = {
  room_id: string;
  starts_at: string;
  ends_at: string;
  is_indefinite: boolean;
  reason_code: RoomBlockReasonCode;
  reason_note: string;
};

const emptyBlockForm = (): BlockFormValues => ({
  room_id: "",
  starts_at: todayIso(),
  ends_at: "",
  is_indefinite: false,
  reason_code: "maintenance",
  reason_note: ""
});

export function RoomsPage() {
  const { session } = useSession();
  // Only owner/co_owner/manager can PATCH room status or manage room blocks
  // (see require_roles in app/api/rooms.py and PERMISSION_ROOM_BLOCK). Reception
  // and housekeeping must see room state as read-only instead of controls that
  // always fail with a permission error.
  // C4: intentionally reads session.role (not baseRole) -- these controls
  // only ever hide a button the backend would reject anyway (no data fetch
  // it gates), so letting an owner preview "what a receptionist sees here"
  // via "Cambiar vista" is exactly the switcher's job, not a security gap.
  const canManageRooms = ["owner", "co_owner", "manager"].includes(session.role ?? "");
  const { roomsQuery, categoriesQuery, updateStatusMutation } = useRooms();
  const { blocksQuery, createBlockMutation, resolveBlockMutation } = useRoomBlocks();
  const rooms = useMemo(() => roomsQuery.data || [], [roomsQuery.data]);
  const categories = useMemo(() => categoriesQuery.data || [], [categoriesQuery.data]);
  const activeBlocks = useMemo(() => blocksQuery.data || [], [blocksQuery.data]);
  const [pendingRoom, setPendingRoom] = useState<number | null>(null);
  const [roomStatusError, setRoomStatusError] = useState<{ roomId: number; message: string } | null>(null);
  const [pendingBlockId, setPendingBlockId] = useState<number | null>(null);
  const [blockForm, setBlockForm] = useState<BlockFormValues>(() => emptyBlockForm());
  const [blockMessage, setBlockMessage] = useState<string | null>(null);
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
    const map = new Map<number, { name: string; code: string; base_price_per_night: number; current_rate?: number | null }>();
    categories.forEach((cat) =>
      map.set(cat.id, {
        name: cat.name,
        code: cat.code,
        base_price_per_night: cat.base_price_per_night,
        current_rate: cat.current_rate
      })
    );
    return map;
  }, [categories]);

  const roomById = useMemo(() => {
    const map = new Map<number, { room_number: string; floor: number }>();
    rooms.forEach((room) => map.set(room.id, { room_number: room.room_number, floor: room.floor }));
    return map;
  }, [rooms]);

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
    setRoomStatusError(null);
    setPendingRoom(roomId);
    updateStatusMutation.mutate(
      { roomId, status },
      {
        onError: (error: unknown) => {
          const detail = error instanceof Error ? error.message : "No se pudo actualizar el estado de la habitación.";
          setRoomStatusError({ roomId, message: detail });
        },
        onSettled: () => setPendingRoom(null)
      }
    );
  };

  const handleBlockFormChange = <Field extends keyof BlockFormValues>(field: Field, value: BlockFormValues[Field]) => {
    setBlockForm((current) => ({ ...current, [field]: value }));
  };

  const handleCreateBlock = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (actionsBlocked) return;
    setBlockMessage(null);

    const roomId = Number(blockForm.room_id);
    if (!Number.isInteger(roomId) || roomId <= 0) {
      setBlockMessage("Seleccioná una habitación para bloquear.");
      return;
    }
    if (!blockForm.is_indefinite && !blockForm.ends_at) {
      setBlockMessage("Indicá una fecha de fin o marcá el bloqueo como indefinido.");
      return;
    }

    const payload: RoomBlockCreatePayload = {
      room_id: roomId,
      starts_at: blockForm.starts_at,
      ends_at: blockForm.is_indefinite ? null : blockForm.ends_at,
      is_indefinite: blockForm.is_indefinite,
      reason_code: blockForm.reason_code,
      reason_note: blockForm.reason_note.trim() || null
    };

    try {
      await createBlockMutation.mutateAsync(payload);
      setBlockForm(emptyBlockForm());
      setBlockMessage("Bloqueo creado.");
    } catch (error) {
      setBlockMessage(error instanceof Error ? error.message : "No se pudo crear el bloqueo.");
    }
  };

  const handleResolveBlock = async (blockId: number) => {
    if (actionsBlocked) return;
    setPendingBlockId(blockId);
    setBlockMessage(null);
    try {
      await resolveBlockMutation.mutateAsync(blockId);
      setBlockMessage("Bloqueo resuelto.");
    } catch (error) {
      setBlockMessage(error instanceof Error ? error.message : "No se pudo resolver el bloqueo.");
    } finally {
      setPendingBlockId(null);
    }
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
                      Piso {room.floor} · {category?.code || room.category?.code || "sin código"}
                    </p>
                    <p className="text-xs text-slate-600">
                      Tarifa hoy:{" "}
                      <span className="font-semibold text-slate-800">
                        ${formatRate(category?.current_rate ?? category?.base_price_per_night ?? room.category?.base_price_per_night)}
                      </span>
                      /noche
                    </p>
                  </div>
                  <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusColors[room.status]}`}>
                    {roomStatusLabel[room.status]}
                  </span>
                </div>
                <p className="mt-3 text-sm text-slate-700">{room.notes || "Sin notas"}</p>
                {canManageRooms ? (
                  <div className="mt-4 text-xs text-slate-600">
                    <select
                      value={room.status}
                      onChange={(e) => handleStatusUpdate(room.id, e.target.value as RoomStatus)}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-brand-400 focus:outline-none disabled:bg-slate-50"
                      disabled={actionsBlocked || (pendingRoom === room.id && updateStatusMutation.isPending)}
                    >
                      {statusOptions.map((status) => (
                        <option key={status} value={status}>
                          {roomStatusLabel[status]}
                        </option>
                      ))}
                      <option value="maintenance">Mantenimiento</option>
                      <option value="blocked">Bloqueada</option>
                    </select>
                    {pendingRoom === room.id && updateStatusMutation.isPending && (
                      <p className="mt-2 text-xs text-slate-500">Guardando...</p>
                    )}
                    {roomStatusError?.roomId === room.id && (
                      <p role="alert" className="mt-2 text-xs text-rose-700">
                        No se pudo actualizar el estado: {roomStatusError.message}
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="mt-4 text-xs text-slate-400">Solo lectura para tu rol.</p>
                )}
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

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Bloqueos</p>
            <h2 className="text-lg font-semibold text-slate-900">Bloqueos activos ({activeBlocks.length})</h2>
            <p className="text-sm text-slate-600">Reservá habitaciones fuera de venta por mantenimiento, limpieza o uso interno.</p>
            {blocksQuery.error && <p className="mt-1 text-xs text-rose-700">No se pudo cargar: {(blocksQuery.error as Error).message}</p>}
          </div>
          {blocksQuery.isFetching && <p className="text-xs text-slate-500">Actualizando bloqueos...</p>}
        </div>

        {canManageRooms && (
        <form className="mt-4 grid gap-4 rounded-lg border border-slate-200 bg-slate-50 p-4 lg:grid-cols-6" onSubmit={handleCreateBlock}>
          <label className="space-y-1 text-sm lg:col-span-1">
            <span className="text-slate-600">Habitación</span>
            <select
              required
              value={blockForm.room_id}
              onChange={(event) => handleBlockFormChange("room_id", event.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
              disabled={actionsBlocked || createBlockMutation.isPending}
            >
              <option value="">Seleccionar</option>
              {rooms.map((room) => (
                <option key={room.id} value={room.id}>
                  Hab. {room.room_number}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-1 text-sm lg:col-span-1">
            <span className="text-slate-600">Desde</span>
            <input
              required
              type="date"
              value={blockForm.starts_at}
              onChange={(event) => handleBlockFormChange("starts_at", event.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
              disabled={actionsBlocked || createBlockMutation.isPending}
            />
          </label>

          <label className="space-y-1 text-sm lg:col-span-1">
            <span className="text-slate-600">Hasta</span>
            <input
              type="date"
              value={blockForm.ends_at}
              min={blockForm.starts_at}
              onChange={(event) => handleBlockFormChange("ends_at", event.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 disabled:bg-slate-100"
              disabled={actionsBlocked || blockForm.is_indefinite || createBlockMutation.isPending}
              required={!blockForm.is_indefinite}
            />
          </label>

          <label className="space-y-1 text-sm lg:col-span-1">
            <span className="text-slate-600">Motivo</span>
            <select
              value={blockForm.reason_code}
              onChange={(event) => handleBlockFormChange("reason_code", event.target.value as RoomBlockReasonCode)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
              disabled={actionsBlocked || createBlockMutation.isPending}
            >
              {roomBlockReasonOptions.map((reason) => (
                <option key={reason} value={reason}>
                  {roomBlockReasonLabel[reason]}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-1 text-sm lg:col-span-2">
            <span className="text-slate-600">Detalle</span>
            <input
              value={blockForm.reason_note}
              onChange={(event) => handleBlockFormChange("reason_note", event.target.value)}
              maxLength={500}
              placeholder="Ej. reparación de aire acondicionado"
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
              disabled={actionsBlocked || createBlockMutation.isPending}
            />
          </label>

          <div className="flex flex-col gap-3 lg:col-span-6 sm:flex-row sm:items-center sm:justify-between">
            <label className="inline-flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={blockForm.is_indefinite}
                onChange={(event) => {
                  handleBlockFormChange("is_indefinite", event.target.checked);
                  if (event.target.checked) handleBlockFormChange("ends_at", "");
                }}
                className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                disabled={actionsBlocked || createBlockMutation.isPending}
              />
              Bloqueo indefinido
            </label>
            <button
              type="submit"
              disabled={actionsBlocked || createBlockMutation.isPending}
              className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              {createBlockMutation.isPending ? "Creando..." : "Crear bloqueo"}
            </button>
          </div>
        </form>
        )}

        {blockMessage && (
          <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">{blockMessage}</div>
        )}

        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {activeBlocks.map((block) => {
            const room = roomById.get(block.room_id);
            return (
              <div key={block.id} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">
                      {room ? `Hab. ${room.room_number} · Piso ${room.floor}` : `Habitación ${block.room_id}`}
                    </p>
                    <h3 className="text-base font-semibold text-slate-900">{roomBlockReasonLabel[block.reason_code]}</h3>
                    <p className="text-xs text-slate-500">{formatBlockDates(block.starts_at, block.ends_at, block.is_indefinite)}</p>
                  </div>
                  {canManageRooms && (
                    <button
                      type="button"
                      onClick={() => handleResolveBlock(block.id)}
                      disabled={actionsBlocked || (pendingBlockId === block.id && resolveBlockMutation.isPending)}
                      className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                    >
                      {pendingBlockId === block.id && resolveBlockMutation.isPending ? "Resolviendo..." : "Resolver"}
                    </button>
                  )}
                </div>
                <p className="mt-3 text-sm text-slate-700">{block.reason_note || "Sin detalle adicional."}</p>
              </div>
            );
          })}
          {!blocksQuery.isLoading && activeBlocks.length === 0 && (
            <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
              No hay bloqueos activos.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function formatBlockDates(startsAt: string, endsAt?: string | null, isIndefinite?: boolean) {
  const start = formatDate(startsAt);
  if (isIndefinite) return `Desde ${start} · indefinido`;
  return `Desde ${start} hasta ${endsAt ? formatDate(endsAt) : "sin fecha de fin"}`;
}

function formatDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString("es-AR");
}

function formatRate(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "?";
  return value.toLocaleString("es-AR", { maximumFractionDigits: 0 });
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
