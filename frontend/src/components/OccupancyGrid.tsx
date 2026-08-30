import { Fragment, useMemo } from "react";
import cx from "clsx";

import type { OccupancyGridBlock, OccupancyGridReservation, OccupancyGridResponse, OccupancyGridRoom } from "../api/reservations";
import { reservationStatusConfig } from "../utils/reservationStatus";

// ponytail: a fixed N-day window (30 by default, see OccupancyPlanningPage)
// with prev/next prefetch, not virtualized infinite scroll. Rows are rooms
// (dozens for this hotel), not thousands, so a plain table is plenty. If the
// hotel ever crosses ~200 rooms or asks for continuous zoom, virtualize then.

const DATE_LABEL = new Intl.DateTimeFormat("es-AR", { weekday: "short", day: "2-digit", month: "2-digit" });

export type RoomDropTarget = { reservationId: number; toRoomId: number };

type OccupancyGridProps = {
  data: OccupancyGridResponse;
  days: string[];
  todayIso: string;
  onSelectReservation: (id: number) => void;
  /** Drop handler. Absent = drag disabled (no permission, or read-only view). */
  onDropReservation?: (target: RoomDropTarget) => void;
  /**
   * Fires when a drag begins (null when it ends). The parent needs the source
   * reservation to decide which rooms may receive it -- that cannot wait for
   * the drop, or every room would look droppable mid-drag.
   */
  onDragReservationChange?: (reservationId: number | null) => void;
  /** Why this room cannot receive the dragged reservation, or null if it can. */
  roomDropBlockedReason?: (roomId: number) => string | null;
};

type CategoryGroup = {
  categoryId: number;
  categoryName: string;
  rooms: OccupancyGridRoom[];
};

function groupByCategory(rooms: OccupancyGridRoom[]): CategoryGroup[] {
  const groups: CategoryGroup[] = [];
  for (const room of rooms) {
    const current = groups[groups.length - 1];
    if (current && current.categoryId === room.category_id) {
      current.rooms.push(room);
    } else {
      groups.push({ categoryId: room.category_id, categoryName: room.category_name, rooms: [room] });
    }
  }
  return groups;
}

function occupiesDay(item: { check_in_date: string; check_out_date: string }, day: string) {
  return day >= item.check_in_date && day < item.check_out_date;
}

function blocksDay(block: OccupancyGridBlock, day: string) {
  return day >= block.starts_at && (block.ends_at === null || day < block.ends_at);
}

function buildReservationsByRoomAndDay(
  reservations: OccupancyGridReservation[],
  unassigned: OccupancyGridReservation[],
  days: string[]
) {
  const map = new Map<string, OccupancyGridReservation[]>();
  const index = (roomKey: string | number, item: OccupancyGridReservation) => {
    for (const day of days) {
      if (!occupiesDay(item, day)) continue;
      const key = `${roomKey}_${day}`;
      const bucket = map.get(key);
      if (bucket) bucket.push(item);
      else map.set(key, [item]);
    }
  };
  reservations.forEach((r) => index(r.room_id as number, r));
  unassigned.forEach((r) => index("unassigned", r));
  return map;
}

function buildBlocksByRoomAndDay(blocks: OccupancyGridBlock[], days: string[]) {
  const map = new Map<string, OccupancyGridBlock[]>();
  blocks.forEach((block) => {
    for (const day of days) {
      if (!blocksDay(block, day)) continue;
      const key = `${block.room_id}_${day}`;
      const bucket = map.get(key);
      if (bucket) bucket.push(block);
      else map.set(key, [block]);
    }
  });
  return map;
}

function StickyLabelCell({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <th
      scope="row"
      className={cx(
        "sticky left-0 z-20 w-[220px] min-w-[220px] border-b border-r border-slate-200 px-3 py-2 text-left align-top",
        className
      )}
    >
      {children}
    </th>
  );
}

function Cell({
  reservationItems,
  blockItems,
  onSelectReservation,
  roomId,
  onDropReservation,
  onDragReservationChange,
  dropBlockedReason
}: {
  reservationItems: OccupancyGridReservation[];
  blockItems: OccupancyGridBlock[];
  onSelectReservation: (id: number) => void;
  roomId?: number;
  onDropReservation?: (target: RoomDropTarget) => void;
  onDragReservationChange?: (reservationId: number | null) => void;
  dropBlockedReason?: string | null;
}) {
  // ponytail: native HTML5 drag, no dependency. Drag is a shortcut only --
  // it does not work on touch or with a keyboard, so the picker in the
  // reservation drawer stays the primary path.
  const canDrop = Boolean(onDropReservation) && roomId !== undefined && !dropBlockedReason;
  const dropProps = canDrop
    ? {
        onDragOver: (event: React.DragEvent) => {
          event.preventDefault();
          event.dataTransfer.dropEffect = "move" as const;
        },
        onDrop: (event: React.DragEvent) => {
          event.preventDefault();
          const raw = event.dataTransfer.getData("text/reservation-id");
          const reservationId = Number(raw);
          if (raw && Number.isFinite(reservationId) && roomId !== undefined) {
            onDropReservation?.({ reservationId, toRoomId: roomId });
          }
        }
      }
    : {};
  const blockedTitle = dropBlockedReason ?? undefined;
  if (reservationItems.length > 0) {
    const item = reservationItems[0];
    const status = reservationStatusConfig[item.status];
    const extra = reservationItems.length - 1;
    return (
      <td className="min-w-[110px] border-b border-r border-slate-200 p-1 align-top" title={blockedTitle} {...dropProps}>
        <button
          type="button"
          data-testid={`occupancy-reservation-${item.id}`}
          onClick={() => onSelectReservation(item.id)}
          draggable={Boolean(onDropReservation)}
          onDragStart={(event) => {
            event.dataTransfer.setData("text/reservation-id", String(item.id));
            event.dataTransfer.effectAllowed = "move";
            onDragReservationChange?.(item.id);
          }}
          onDragEnd={() => onDragReservationChange?.(null)}
          title={`${item.guest_name} · ${item.confirmation_code}`}
          className={cx(
            "w-full truncate rounded-lg px-2 py-1.5 text-left text-xs font-semibold shadow-sm hover:opacity-80",
            status.className
          )}
        >
          {item.guest_name}
          {extra > 0 ? ` +${extra}` : ""}
        </button>
      </td>
    );
  }

  if (blockItems.length > 0) {
    return (
      <td className="min-w-[110px] border-b border-r border-slate-200 bg-[repeating-linear-gradient(45deg,#e2e8f0,#e2e8f0_6px,#f8fafc_6px,#f8fafc_12px)] p-1 align-top">
        <span className="block truncate px-2 py-1.5 text-xs font-medium text-slate-500" title={blockItems[0].reason_code}>
          Bloqueada
        </span>
      </td>
    );
  }

  return (
    <td
      className={cx(
        "min-w-[110px] border-b border-r border-slate-200 p-1 align-top",
        dropBlockedReason && "bg-slate-50"
      )}
      title={blockedTitle}
      {...dropProps}
    />
  );
}

export function OccupancyGrid({ data, days, todayIso, onSelectReservation, onDropReservation, onDragReservationChange, roomDropBlockedReason }: OccupancyGridProps) {
  const groups = useMemo(() => groupByCategory(data.rooms), [data.rooms]);
  const reservationsByCell = useMemo(
    () => buildReservationsByRoomAndDay(data.reservations, data.unassigned, days),
    [data.reservations, data.unassigned, days]
  );
  const blocksByCell = useMemo(() => buildBlocksByRoomAndDay(data.blocks, days), [data.blocks, days]);

  return (
    <div data-testid="occupancy-grid" className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
      <table className="w-max min-w-full border-separate border-spacing-0">
        <thead>
          <tr>
            <th className="sticky left-0 top-0 z-30 w-[220px] min-w-[220px] border-b border-r border-slate-200 bg-white px-3 py-2 text-left">
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Habitación</span>
            </th>
            {days.map((day) => (
              <th
                key={day}
                className={cx(
                  "sticky top-0 z-10 min-w-[110px] border-b border-r border-slate-200 bg-white px-2 py-2 text-center",
                  day === todayIso && "bg-brand-50"
                )}
              >
                <span className="text-xs font-semibold text-slate-700">{DATE_LABEL.format(new Date(`${day}T00:00:00`))}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.unassigned.length > 0 ? (
            <tr>
              <StickyLabelCell className="bg-amber-50">
                <p className="text-sm font-semibold text-amber-900">Sin asignar</p>
                <p className="text-xs text-amber-700">{data.unassigned.length} reserva(s) sin habitación</p>
              </StickyLabelCell>
              {days.map((day) => (
                <Cell
                  key={`unassigned-${day}`}
                  reservationItems={reservationsByCell.get(`unassigned_${day}`) ?? []}
                  blockItems={[]}
                  onSelectReservation={onSelectReservation}
                />
              ))}
            </tr>
          ) : null}

          {groups.map((group) => (
            <Fragment key={group.categoryId}>
              <tr>
                <StickyLabelCell className="bg-slate-900 text-white">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-200">{group.categoryName}</p>
                </StickyLabelCell>
                {days.map((day) => (
                  <td key={`${group.categoryId}-header-${day}`} className="border-b border-r border-slate-200 bg-slate-900" />
                ))}
              </tr>
              {group.rooms.map((room) => (
                <tr key={room.id}>
                  <StickyLabelCell>
                    <p className="text-sm font-medium text-slate-900">Hab. {room.room_number}</p>
                    <p className="text-xs text-slate-500">Piso {room.floor}</p>
                  </StickyLabelCell>
                  {days.map((day) => (
                    <Cell
                      key={`${room.id}-${day}`}
                      reservationItems={reservationsByCell.get(`${room.id}_${day}`) ?? []}
                      blockItems={blocksByCell.get(`${room.id}_${day}`) ?? []}
                      onSelectReservation={onSelectReservation}
                      roomId={room.id}
                      onDropReservation={onDropReservation}
                      onDragReservationChange={onDragReservationChange}
                      dropBlockedReason={roomDropBlockedReason?.(room.id) ?? null}
                    />
                  ))}
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
