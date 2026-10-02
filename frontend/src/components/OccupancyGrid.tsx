import { Fragment, useMemo } from "react";
import cx from "clsx";
import { useTranslation } from "react-i18next";

import type { OccupancyGridBlock, OccupancyGridReservation, OccupancyGridResponse, OccupancyGridRoom } from "../api/reservations";
import { reservationStatusConfig } from "../utils/reservationStatus";

// ponytail: a fixed N-day window (30 by default, see OccupancyPlanningPage)
// with prev/next prefetch, not virtualized infinite scroll. Rows are rooms
// (dozens for this hotel), not thousands, so a plain table is plenty. If the
// hotel ever crosses ~200 rooms or asks for continuous zoom, virtualize then.

export type RoomDropTarget = { reservationId: number; toRoomId: number };
export type OccupancyRoomSortMode = "floor" | "category";

type OccupancyGridProps = {
  data: OccupancyGridResponse;
  days: string[];
  todayIso: string;
  sortMode: OccupancyRoomSortMode;
  onSelectReservation: (id: number) => void;
  onSelectEmptyCell?: (room: OccupancyGridRoom, day: string) => void;
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

type RoomGroup = {
  key: string;
  label: string;
  kind: OccupancyRoomSortMode;
  rooms: OccupancyGridRoom[];
};

function compareRoomNumber(a: OccupancyGridRoom, b: OccupancyGridRoom) {
  return a.room_number.localeCompare(b.room_number, undefined, { numeric: true, sensitivity: "base" });
}

function groupRooms(rooms: OccupancyGridRoom[], sortMode: OccupancyRoomSortMode): RoomGroup[] {
  const byGroup = new Map<string, OccupancyGridRoom[]>();
  for (const room of rooms) {
    const key = sortMode === "floor" ? String(room.floor) : String(room.category_id);
    const bucket = byGroup.get(key) ?? [];
    bucket.push(room);
    byGroup.set(key, bucket);
  }

  return [...byGroup.entries()].map(([key, groupedRooms]) => {
    const roomsInGroup = [...groupedRooms].sort((a, b) =>
      sortMode === "floor"
        ? a.category_name.localeCompare(b.category_name, undefined, { sensitivity: "base" }) || compareRoomNumber(a, b)
        : a.floor - b.floor || compareRoomNumber(a, b)
    );
    return {
      key,
      label: sortMode === "floor" ? key : roomsInGroup[0].category_name,
      kind: sortMode,
      rooms: roomsInGroup
    };
  }).sort((a, b) => sortMode === "floor"
    ? Number(a.key) - Number(b.key)
    : a.label.localeCompare(b.label, undefined, { sensitivity: "base" })
  );
}

function groupByCategory(rooms: OccupancyGridRoom[]): RoomGroup[] {
  const grouped = new Map<number, OccupancyGridRoom[]>();
  rooms.forEach((room) => {
    const bucket = grouped.get(room.category_id) ?? [];
    bucket.push(room);
    grouped.set(room.category_id, bucket);
  });
  return [...grouped.entries()].map(([categoryId, categoryRooms]) => ({
    key: String(categoryId),
    label: categoryRooms[0].category_name,
    kind: "category" as const,
    rooms: categoryRooms
  })).sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: "base" }));
}

function countFreeRooms(
  rooms: OccupancyGridRoom[],
  day: string,
  reservationsByCell: Map<string, OccupancyGridReservation[]>,
  blocksByCell: Map<string, OccupancyGridBlock[]>
) {
  return rooms.filter((room) =>
    !["maintenance", "blocked"].includes(room.status)
    && !(reservationsByCell.get(`${room.id}_${day}`)?.length)
    && !(blocksByCell.get(`${room.id}_${day}`)?.length)
  ).length;
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
        "sticky left-0 z-20 w-[180px] min-w-[180px] border-b border-r border-slate-200 px-3 py-2 text-left align-top",
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
  onSelectEmptyCell,
  roomId,
  room,
  day,
  onDropReservation,
  onDragReservationChange,
  dropBlockedReason
}: {
  reservationItems: OccupancyGridReservation[];
  blockItems: OccupancyGridBlock[];
  onSelectReservation: (id: number) => void;
  onSelectEmptyCell?: (room: OccupancyGridRoom, day: string) => void;
  roomId?: number;
  room?: OccupancyGridRoom;
  day?: string;
  onDropReservation?: (target: RoomDropTarget) => void;
  onDragReservationChange?: (reservationId: number | null) => void;
  dropBlockedReason?: string | null;
}) {
  const { t } = useTranslation("reservations");
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
  const blockReasonLabels: Record<string, string> = {
    maintenance: t("occupancy.blockReasons.maintenance"),
    deep_cleaning: t("occupancy.blockReasons.deep_cleaning"),
    owner_use: t("occupancy.blockReasons.owner_use"),
    vip_hold: t("occupancy.blockReasons.vip_hold"),
    overbooking_buffer: t("occupancy.blockReasons.overbooking_buffer"),
    other: t("occupancy.blockReasons.other")
  };
  if (reservationItems.length > 0) {
    const item = reservationItems[0];
    const status = reservationStatusConfig[item.status];
    const extra = reservationItems.length - 1;
    const overlappingBlock = blockItems[0];
    const hasBlockConflict = Boolean(overlappingBlock);
    const blockReason = overlappingBlock
      ? blockReasonLabels[overlappingBlock.reason_code] ?? t("occupancy.blocked")
      : "";
    return (
      <td
        data-testid={hasBlockConflict ? `occupancy-block-conflict-${item.id}` : undefined}
        aria-label={hasBlockConflict ? t("occupancy.blockConflictTitle", { reason: blockReason }) : undefined}
        className={cx("min-w-[64px] border-b border-r border-slate-200 p-1 align-top", hasBlockConflict && "bg-rose-50")}
        title={hasBlockConflict ? t("occupancy.blockConflictTitle", { reason: blockReason }) : blockedTitle}
        {...dropProps}
      >
        {hasBlockConflict && (
          <span className="mb-1 block truncate rounded-md bg-rose-100 px-2 py-1 text-[10px] font-semibold text-rose-900">
            {t("occupancy.blockConflict", { reason: blockReason })}
          </span>
        )}
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
    const blockReason = blockReasonLabels[blockItems[0].reason_code] ?? t("occupancy.blocked");
    const blockedCellLabel = t("occupancy.blockedCell", { reason: blockReason });
    return (
      <td
        data-testid={roomId !== undefined && day ? `occupancy-block-${roomId}-${day}` : undefined}
        aria-label={blockedCellLabel}
        className="min-w-[64px] border-b border-r border-slate-200 bg-[repeating-linear-gradient(45deg,#e2e8f0,#e2e8f0_6px,#f8fafc_6px,#f8fafc_12px)] p-1 align-top"
        title={blockedCellLabel}
      >
        <span className="block truncate px-2 py-1.5 text-xs font-medium text-slate-500">
          {t("occupancy.blocked")}
        </span>
        <span className="block truncate px-2 text-[10px] font-medium text-slate-700">{blockReason}</span>
      </td>
    );
  }

  const canCreate = Boolean(
    onSelectEmptyCell && room && day && !["maintenance", "blocked"].includes(room.status)
  );
  return (
    <td
      className={cx(
        "min-w-[64px] border-b border-r border-slate-200 p-1 align-top",
        dropBlockedReason && "bg-slate-50"
      )}
      title={blockedTitle}
      {...dropProps}
    >
      {canCreate ? (
        <button
          type="button"
          data-testid={`occupancy-create-${room!.id}-${day}`}
          aria-label={t("occupancy.createForRoom", { room: room!.room_number, day })}
          onClick={() => onSelectEmptyCell?.(room!, day!)}
          className="min-h-8 w-full rounded-md px-1 text-left text-xs text-slate-400 hover:bg-brand-50 hover:text-brand-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-600"
        >
          +
        </button>
      ) : null}
    </td>
  );
}

export function OccupancyGrid({ data, days, todayIso, sortMode, onSelectReservation, onSelectEmptyCell, onDropReservation, onDragReservationChange, roomDropBlockedReason }: OccupancyGridProps) {
  const { t, i18n } = useTranslation("reservations");
  const dateLabel = useMemo(
    () => new Intl.DateTimeFormat(i18n.language === "en" ? "en-US" : "es-AR", { weekday: "short", day: "2-digit", month: "2-digit" }),
    [i18n.language]
  );
  const groups = useMemo(() => groupRooms(data.rooms, sortMode), [data.rooms, sortMode]);
  const categoryGroups = useMemo(() => groupByCategory(data.rooms), [data.rooms]);
  const reservationsByCell = useMemo(
    () => buildReservationsByRoomAndDay(data.reservations, data.unassigned, days),
    [data.reservations, data.unassigned, days]
  );
  const blocksByCell = useMemo(() => buildBlocksByRoomAndDay(data.blocks, days), [data.blocks, days]);
  const legendStatuses = ["pending", "deposit_paid", "fully_paid", "pre_check_in", "checked_in"] as const;

  return (
    <div data-testid="occupancy-grid" className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div aria-label={t("occupancy.legendLabel")} className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-3 py-2 text-xs">
        <span className="font-semibold text-slate-700">{t("occupancy.legendLabel")}</span>
      {legendStatuses.map((status) => (
        <span key={status} className={cx("rounded-full px-2 py-1 font-medium", reservationStatusConfig[status].className)}>
          {t(`occupancy.statuses.${status}`)}
        </span>
      ))}
      <span className="rounded-full bg-slate-100 px-2 py-1 font-medium text-slate-600">{t("occupancy.blocked")}</span>
      <span className="rounded-full bg-rose-100 px-2 py-1 font-medium text-rose-900">{t("occupancy.blockConflictLegend")}</span>
      </div>
      <table className="w-full min-w-[1076px] table-fixed border-separate border-spacing-0">
        <thead>
          <tr>
            <th className="sticky left-0 top-0 z-30 w-[180px] min-w-[180px] border-b border-r border-slate-200 bg-white px-3 py-2 text-left">
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{t("occupancy.room")}</span>
            </th>
            {days.map((day) => (
              <th
                key={day}
                className={cx(
                  "sticky top-0 z-10 w-16 min-w-[64px] border-b border-r border-slate-200 bg-white px-1 py-2 text-center",
                  day === todayIso && "bg-brand-50"
                )}
              >
                <span className="text-[10px] font-semibold text-slate-700">{dateLabel.format(new Date(`${day}T00:00:00`))}</span>
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

          {sortMode === "floor" ? (
            <>
              <tr data-testid="occupancy-category-availability-heading">
                <StickyLabelCell className="bg-emerald-100 text-emerald-900">
                  <p className="text-xs font-semibold uppercase tracking-wide">{t("occupancy.availableByCategory")}</p>
                </StickyLabelCell>
                {days.map((day) => <td key={`availability-heading-${day}`} className="w-16 min-w-[64px] border-b border-r border-emerald-100 bg-emerald-100" />)}
              </tr>
              {categoryGroups.map((category) => (
                <tr key={`free-category-${category.key}`} data-testid={`occupancy-free-row-${category.key}`}>
                  <StickyLabelCell className="bg-emerald-50">
                    <p className="text-xs font-semibold text-emerald-900">{t("occupancy.freeCount", { category: category.label })}</p>
                  </StickyLabelCell>
                  {days.map((day) => {
                    const free = countFreeRooms(category.rooms, day, reservationsByCell, blocksByCell);
                    return (
                      <td
                        key={`free-category-${category.key}-${day}`}
                        data-testid={`occupancy-free-count-${category.key}-${day}`}
                        aria-label={t("occupancy.freeCountCell", { count: free, category: category.label, day })}
                        className="w-16 min-w-[64px] border-b border-r border-emerald-100 bg-emerald-50 px-1 py-2 text-center text-xs font-bold text-emerald-900"
                      >{free}</td>
                    );
                  })}
                </tr>
              ))}
            </>
          ) : null}
          {groups.map((group) => (
            <Fragment key={`${group.kind}-${group.key}`}>
              <tr data-testid={`occupancy-group-${group.kind}-${group.key}`}>
                <StickyLabelCell className="bg-slate-100 text-slate-700">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                    {group.kind === "floor" ? t("occupancy.floorLabel", { floor: group.label }) : group.label}
                  </p>
                </StickyLabelCell>
                {days.map((day) => (
                  <td key={`${group.kind}-${group.key}-header-${day}`} className="w-16 min-w-[64px] border-b border-r border-slate-200 bg-slate-100" />
                ))}
              </tr>
              {group.kind === "category" ? (
                <tr data-testid={`occupancy-free-row-${group.key}`}>
                  <StickyLabelCell className="bg-emerald-50">
                    <p className="text-xs font-semibold text-emerald-900">{t("occupancy.freeCount", { category: group.label })}</p>
                  </StickyLabelCell>
                  {days.map((day) => {
                    const free = countFreeRooms(group.rooms, day, reservationsByCell, blocksByCell);
                    return (
                      <td
                        key={`${group.key}-free-${day}`}
                        data-testid={`occupancy-free-count-${group.key}-${day}`}
                        aria-label={t("occupancy.freeCountCell", { count: free, category: group.label, day })}
                        className="w-16 min-w-[64px] border-b border-r border-emerald-100 bg-emerald-50 px-1 py-2 text-center text-xs font-bold text-emerald-900"
                      >{free}</td>
                    );
                  })}
                </tr>
              ) : null}
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
                      onSelectEmptyCell={onSelectEmptyCell}
                      roomId={room.id}
                      room={room}
                      day={day}
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
