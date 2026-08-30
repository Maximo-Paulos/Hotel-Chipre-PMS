import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { OccupancyGrid, type RoomDropTarget } from "../../components/OccupancyGrid";
import { moveReservationRoom } from "../../api/reservations";
import { useEffectivePermissions } from "../../hooks/usePermissions";
import { useRooms } from "../../hooks/useRooms";
import { useSession } from "../../state/session";
import { ROOM_MOVE_REASONS, moveBlockedReason } from "../../utils/roomMove";
import { useReservationDrawer } from "../../hooks/useReservationDrawer";
import { addDaysIso, todayIso } from "../../hooks/useRateCalendar";
import { useOccupancyGrid, usePrefetchOccupancyGrid } from "../../hooks/useReservations";

const WINDOW_DAYS = 30;

function buildDayRange(from: string, count: number): string[] {
  return Array.from({ length: count }, (_, i) => addDaysIso(from, i));
}

const RANGE_LABEL = new Intl.DateTimeFormat("es-AR", { day: "2-digit", month: "short", year: "numeric" });

export function OccupancyPlanningPage() {
  const [windowStart, setWindowStart] = useState(todayIso());
  const windowEnd = useMemo(() => addDaysIso(windowStart, WINDOW_DAYS), [windowStart]);
  const days = useMemo(() => buildDayRange(windowStart, WINDOW_DAYS), [windowStart]);
  const today = todayIso();

  const gridQuery = useOccupancyGrid(windowStart, windowEnd);
  const prefetch = usePrefetchOccupancyGrid();
  const { openReservation } = useReservationDrawer();
  const { session } = useSession();
  const queryClient = useQueryClient();
  const { hasPermission } = useEffectivePermissions();
  const { roomsQuery, categoriesQuery } = useRooms();

  // Drop opens this dialog: a drag alone never moves a guest, because the
  // backend requires an explicit reason and the operator must pick one.
  const [pendingMove, setPendingMove] = useState<RoomDropTarget | null>(null);
  const [draggingId, setDraggingId] = useState<number | null>(null);
  const [moveReason, setMoveReason] = useState("");
  const [moveNotes, setMoveNotes] = useState("");
  const [moveError, setMoveError] = useState<string | null>(null);

  const categoryById = useMemo(() => {
    const map = new Map<number, { id: number; max_occupancy: number }>();
    (categoriesQuery.data ?? []).forEach((cat) => map.set(cat.id, { id: cat.id, max_occupancy: cat.max_occupancy }));
    return map;
  }, [categoriesQuery.data]);

  const roomById = useMemo(() => {
    const map = new Map<number, { id: number; room_number: string; category_id: number }>();
    (roomsQuery.data ?? []).forEach((room) => map.set(room.id, room));
    return map;
  }, [roomsQuery.data]);

  const draggedReservation = useMemo(
    () => gridQuery.data?.reservations.find((r) => r.id === pendingMove?.reservationId) ?? null,
    [gridQuery.data, pendingMove]
  );

  const canMoveAtAll = hasPermission("reservation:move")
    || hasPermission("reservation:move_category")
    || hasPermission("reservation:move_capacity");

  const moveMutation = useMutation({
    mutationFn: ({ reservationId, toRoomId }: { reservationId: number; toRoomId: number }) =>
      moveReservationRoom(
        reservationId,
        { to_room_id: toRoomId, reason_code: moveReason, notes: moveNotes || null, price_action: "keep" },
        session
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["occupancy-grid"] });
      queryClient.invalidateQueries({ queryKey: ["reservations", session.hotelId] });
      setPendingMove(null);
      setMoveReason("");
      setMoveNotes("");
      setMoveError(null);
    },
    onError: (error: unknown) => {
      // The backend names the missing permission; show that, not a generic.
      const detail = (error as { detail?: string; message?: string })?.detail
        ?? (error as { message?: string })?.message;
      setMoveError(detail ?? "No se pudo mover la reserva.");
    }
  });


  // Prefetch the previous/next windows so ±30 navigation feels instant --
  // the "infinite calendar" the plan asks for, without virtualized scroll.
  useEffect(() => {
    const prevStart = addDaysIso(windowStart, -WINDOW_DAYS);
    const nextStart = addDaysIso(windowStart, WINDOW_DAYS);
    prefetch(prevStart, addDaysIso(prevStart, WINDOW_DAYS));
    prefetch(nextStart, addDaysIso(nextStart, WINDOW_DAYS));
  }, [windowStart, prefetch]);

  return (
    <div className="space-y-4" data-testid="occupancy-planning-page">
      <header className="flex flex-col gap-3 rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-200 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Planilla de ocupación</h1>
          <p className="mt-1 text-sm text-slate-600">
            {RANGE_LABEL.format(new Date(`${windowStart}T00:00:00`))} — {RANGE_LABEL.format(new Date(`${addDaysIso(windowStart, WINDOW_DAYS - 1)}T00:00:00`))}
            {gridQuery.isFetching ? " · Actualizando..." : ""}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            data-testid="occupancy-prev-window"
            onClick={() => setWindowStart((current) => addDaysIso(current, -WINDOW_DAYS))}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
          >
            ← 30 días
          </button>
          <button
            type="button"
            onClick={() => setWindowStart(today)}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
          >
            Hoy
          </button>
          <button
            type="button"
            data-testid="occupancy-next-window"
            onClick={() => setWindowStart((current) => addDaysIso(current, WINDOW_DAYS))}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
          >
            30 días →
          </button>
        </div>
      </header>

      {gridQuery.isLoading ? (
        <div className="rounded-3xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">Cargando planilla...</div>
      ) : null}

      {gridQuery.isError ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          No se pudo cargar la planilla: {(gridQuery.error as Error).message}
        </div>
      ) : null}

      {gridQuery.data && gridQuery.data.rooms.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-600 shadow-sm">
          No hay habitaciones cargadas para mostrar la planilla.
        </div>
      ) : null}

      {gridQuery.data && gridQuery.data.rooms.length > 0 ? (
        <OccupancyGrid
          data={gridQuery.data}
          days={days}
          todayIso={today}
          onSelectReservation={openReservation}
          onDropReservation={canMoveAtAll ? (target) => { setMoveError(null); setPendingMove(target); } : undefined}
          onDragReservationChange={setDraggingId}
          roomDropBlockedReason={(roomId) => {
            // Uses the reservation being dragged, not the pending one: the
            // answer is needed while the drag is in flight.
            const source = draggingId ?? pendingMove?.reservationId ?? null;
            if (source === null) return null;
            const room = roomById.get(roomId);
            const current = gridQuery.data?.reservations.find((r) => r.id === source);
            const fromRoom = current?.room_id ? roomById.get(current.room_id) : undefined;
            if (!room || !fromRoom) return null;
            return moveBlockedReason(categoryById.get(fromRoom.category_id), categoryById.get(room.category_id), hasPermission);
          }}
        />
      ) : null}

      {pendingMove ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="mover-reserva-titulo"
            data-testid="planilla-move-dialog"
            className="w-full max-w-md space-y-3 rounded-2xl bg-white p-5 shadow-xl"
          >
            <h2 id="mover-reserva-titulo" className="text-lg font-bold text-slate-900">
              Mover reserva
            </h2>
            <p className="text-sm text-slate-600">
              {draggedReservation?.guest_name ?? "Reserva"} a la habitación{" "}
              <strong>{roomById.get(pendingMove.toRoomId)?.room_number ?? pendingMove.toRoomId}</strong>.
            </p>

            <label className="block space-y-1 text-sm">
              <span className="text-slate-600">Motivo del cambio</span>
              <select
                value={moveReason}
                onChange={(event) => setMoveReason(event.target.value)}
                required
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              >
                <option value="">Elegí un motivo</option>
                {ROOM_MOVE_REASONS.map((reason) => (
                  <option key={reason.value} value={reason.value}>
                    {reason.label}
                  </option>
                ))}
              </select>
            </label>
            {moveReason === "guest_complaint" ? (
              <p className="text-xs text-amber-700">
                Se va a registrar un rechazo: la asignación automática va a evitar esta habitación para este
                huésped en estadías futuras, hasta que alguien lo resuelva.
              </p>
            ) : null}

            <label className="block space-y-1 text-sm">
              <span className="text-slate-600">Notas del cambio</span>
              <textarea
                value={moveNotes}
                onChange={(event) => setMoveNotes(event.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              />
            </label>

            {moveError ? <p className="text-sm text-rose-700">{moveError}</p> : null}

            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => {
                  setPendingMove(null);
                  setMoveError(null);
                }}
                className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={!moveReason || moveMutation.isPending}
                onClick={() => moveMutation.mutate(pendingMove)}
                className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {moveMutation.isPending ? "Moviendo..." : "Confirmar"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
