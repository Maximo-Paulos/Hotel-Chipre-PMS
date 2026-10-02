import { type FormEvent, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

import { ApiError, hasValidSession } from "../../api/client";
import { queryKeys } from "../../api/queryKeys";
import {
  previewRoomBlockConflicts,
  previewRoomBlockExtension,
  type RoomBlockCreatePayload,
  type RoomBlockReasonCode
} from "../../api/roomBlocks";
import { getHousekeepingBoard, type HousekeepingStatus, type RoomStatus } from "../../api/rooms";
import { roomBlockReasonLabel, roomBlockReasonOptions, useRoomBlocks } from "../../hooks/useRoomBlocks";
import { useSubscriptionStatus } from "../../hooks/useSubscription";
import { roomStatusLabel, useRooms } from "../../hooks/useRooms";
import { useEffectivePermissions } from "../../hooks/usePermissions";
import { useSession } from "../../state/session";
import { todayIso } from "../../utils/date";
import { addDaysIso } from "../../hooks/useRateCalendar";
import { useOccupancyGrid } from "../../hooks/useReservations";

const statusColors: Record<RoomStatus, string> = {
  available: "bg-emerald-100 text-emerald-800",
  occupied: "bg-rose-100 text-rose-800",
  cleaning: "bg-amber-100 text-amber-800",
  maintenance: "bg-orange-100 text-orange-800",
  blocked: "bg-slate-200 text-slate-700"
};

const statusOptions: RoomStatus[] = ["available", "occupied", "cleaning", "maintenance", "blocked"];
const housekeepingStatusOptions: HousekeepingStatus[] = ["dirty", "in_progress", "clean", "inspected"];
const housekeepingStatusColors: Record<HousekeepingStatus, string> = {
  dirty: "bg-rose-100 text-rose-800",
  in_progress: "bg-amber-100 text-amber-800",
  clean: "bg-emerald-100 text-emerald-800",
  inspected: "bg-sky-100 text-sky-800"
};

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
  const { t } = useTranslation("rooms");
  const housekeepingStatusLabels: Record<HousekeepingStatus, string> = {
    dirty: t("housekeepingStatus.dirty"),
    in_progress: t("housekeepingStatus.in_progress"),
    clean: t("housekeepingStatus.clean"),
    inspected: t("housekeepingStatus.inspected")
  };
  const { session } = useSession();
  const { hasPermission } = useEffectivePermissions();
  const isHousekeeping = session.baseRole === "housekeeping";
  const canManageRoomStatus = ["owner", "co_owner", "manager"].includes(session.baseRole ?? "");
  const canToggleCleaningStatus = hasPermission("room:status_update");
  const canCreateBlocks = hasPermission("room:block_create");
  const canReleaseBlocks = hasPermission("room:block_release");
  const canReadBlocks = hasPermission("room:read") || canCreateBlocks || canReleaseBlocks;
  const showAssignments = !isHousekeeping && hasPermission("occupancy:view");
  const { roomsQuery, categoriesQuery, updateStatusMutation, updateCleaningStatusMutation } = useRooms({
    includeCategories: !isHousekeeping
  });
  const housekeepingBoardQuery = useQuery({
    queryKey: queryKeys.housekeepingBoard(session.hotelId),
    queryFn: () => getHousekeepingBoard(session),
    enabled: isHousekeeping && hasValidSession(session),
    staleTime: 0
  });
  const { blocksQuery, createBlockMutation, resolveBlockMutation, extendBlockMutation } = useRoomBlocks({ enabled: canReadBlocks });
  const today = todayIso();
  // Keep the persisted physical status independent from future allocations,
  // while still showing the next/current reservation after a Planilla move.
  const occupancyQuery = useOccupancyGrid(today, addDaysIso(today, 92), showAssignments);
  const rooms = useMemo(() => roomsQuery.data || [], [roomsQuery.data]);
  const maintenanceBlockedRoomIds = useMemo(
    () => new Set((housekeepingBoardQuery.data?.rooms ?? []).filter((room) => room.maintenance_blocked).map((room) => room.room_id)),
    [housekeepingBoardQuery.data?.rooms]
  );
  const categories = useMemo(() => categoriesQuery.data || [], [categoriesQuery.data]);
  const activeBlocks = useMemo(() => blocksQuery.data || [], [blocksQuery.data]);
  const [pendingRoom, setPendingRoom] = useState<number | null>(null);
  const [roomStatusError, setRoomStatusError] = useState<{ roomId: number; message: string } | null>(null);
  const [pendingBlockId, setPendingBlockId] = useState<number | null>(null);
  const [extendingBlockId, setExtendingBlockId] = useState<number | null>(null);
  const [extensionEndDate, setExtensionEndDate] = useState("");
  const [blockForm, setBlockForm] = useState<BlockFormValues>(() => emptyBlockForm());
  const [blockMessage, setBlockMessage] = useState<string | null>(null);
  const [blockErrors, setBlockErrors] = useState<Record<string, string>>({});
  const { data: subscription } = useSubscriptionStatus({ enabled: !isHousekeeping });

  const writeBlocked = subscription?.can_write === false;
  const actionsBlocked = Boolean(subscription) && writeBlocked;
  const blockReason = actionsBlocked
    ? t("subscription.readOnly")
    : null;

  const selectedBlockRoomId = Number(blockForm.room_id);
  const blockRangeReady = Boolean(
    Number.isInteger(selectedBlockRoomId)
    && selectedBlockRoomId > 0
    && blockForm.starts_at
    && (blockForm.is_indefinite || (blockForm.ends_at && blockForm.ends_at > blockForm.starts_at))
  );
  const blockConflictPreviewQuery = useQuery({
    queryKey: [
      "room-block-conflict-preview",
      session.hotelId,
      selectedBlockRoomId,
      blockForm.starts_at,
      blockForm.is_indefinite ? null : blockForm.ends_at,
      blockForm.is_indefinite
    ],
    queryFn: () => previewRoomBlockConflicts({
      room_id: selectedBlockRoomId,
      starts_at: blockForm.starts_at,
      ends_at: blockForm.is_indefinite ? null : blockForm.ends_at,
      is_indefinite: blockForm.is_indefinite
    }, session),
    enabled: canCreateBlocks && !actionsBlocked && blockRangeReady && hasValidSession(session),
    staleTime: 0,
    retry: false
  });
  const extendingBlock = activeBlocks.find((block) => block.id === extendingBlockId) ?? null;
  const extensionRangeReady = Boolean(
    extendingBlock?.ends_at && extensionEndDate && extensionEndDate > extendingBlock.ends_at
  );
  const blockExtensionPreviewQuery = useQuery({
    queryKey: ["room-block-extension-preview", session.hotelId, extendingBlockId, extensionEndDate],
    queryFn: () => previewRoomBlockExtension(extendingBlockId as number, extensionEndDate, session),
    enabled: canCreateBlocks && !actionsBlocked && extendingBlockId !== null && extensionRangeReady && hasValidSession(session),
    staleTime: 0,
    retry: false
  });

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

  const assignmentByRoomId = useMemo(() => {
    const map = new Map<number, { confirmation_code: string; guest_name: string; status: string; check_in_date: string }>();
    for (const reservation of occupancyQuery.data?.reservations ?? []) {
      if (reservation.room_id !== null) {
        const current = map.get(reservation.room_id);
        const replacesCurrent = !current
          || reservation.status === "checked_in"
          || (current.status !== "checked_in" && reservation.check_in_date < current.check_in_date);
        if (replacesCurrent) {
          map.set(reservation.room_id, reservation);
        }
      }
    }
    return map;
  }, [occupancyQuery.data]);

  const stats = useMemo(() => {
    return rooms.reduce(
      (acc, room) => {
        acc[room.status] = (acc[room.status] || 0) + 1;
        return acc;
      },
      {} as Record<RoomStatus, number>
    );
  }, [rooms]);

  const housekeepingStats = useMemo(() => {
    return rooms.reduce(
      (acc, room) => {
        acc[room.housekeeping_status] = (acc[room.housekeeping_status] || 0) + 1;
        return acc;
      },
      {} as Record<HousekeepingStatus, number>
    );
  }, [rooms]);

  const handleStatusUpdate = async (roomId: number, status: RoomStatus) => {
    if (actionsBlocked || !canManageRoomStatus) return;
    setRoomStatusError(null);
    setPendingRoom(roomId);
    try {
      await updateStatusMutation.mutateAsync({ roomId, status });
    } catch (error) {
      const detail = error instanceof Error ? error.message : t("inventory.statusUpdateDefaultError");
      setRoomStatusError({ roomId, message: detail });
    } finally {
      setPendingRoom(null);
    }
  };

  const handleHousekeepingStatusUpdate = async (roomId: number, status: HousekeepingStatus) => {
    if (actionsBlocked || !canToggleCleaningStatus) return;
    setRoomStatusError(null);
    setPendingRoom(roomId);
    try {
      await updateCleaningStatusMutation.mutateAsync({ roomId, status });
    } catch (error) {
      const detail = error instanceof Error ? error.message : t("inventory.statusUpdateDefaultError");
      setRoomStatusError({ roomId, message: detail });
    } finally {
      setPendingRoom(null);
    }
  };

  const handleBlockFormChange = <Field extends keyof BlockFormValues>(field: Field, value: BlockFormValues[Field]) => {
    setBlockForm((current) => ({ ...current, [field]: value }));
  };

  const handleCreateBlock = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (actionsBlocked || !canCreateBlocks) return;
    setBlockMessage(null);
    setBlockErrors((current) => { const next = { ...current }; delete next.create; return next; });

    const roomId = Number(blockForm.room_id);
    if (!Number.isInteger(roomId) || roomId <= 0) {
      setBlockErrors((current) => ({ ...current, create: t("blocks.selectRoomError") }));
      return;
    }
    if (!blockForm.is_indefinite && !blockForm.ends_at) {
      setBlockErrors((current) => ({ ...current, create: t("blocks.endDateRequired") }));
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
      setBlockMessage(t("blocks.createSuccess"));
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        const detail = (error.payload as { detail?: { reservation_ids?: unknown } } | null)?.detail;
        const count = Array.isArray(detail?.reservation_ids) ? detail.reservation_ids.length : 1;
        setBlockErrors((current) => ({ ...current, create: t("blocks.protectedConflictRejected", { count }) }));
      } else {
        setBlockErrors((current) => ({ ...current, create: error instanceof Error ? error.message : t("blocks.createError") }));
      }
    }
  };

  const handleResolveBlock = async (blockId: number) => {
    if (actionsBlocked || !canReleaseBlocks) return;
    setPendingBlockId(blockId);
    setBlockMessage(null);
    setBlockErrors((current) => { const next = { ...current }; delete next[`resolve-${blockId}`]; return next; });
    try {
      await resolveBlockMutation.mutateAsync(blockId);
      setBlockMessage(t("blocks.resolveSuccess"));
    } catch (error) {
      setBlockErrors((current) => ({ ...current, [`resolve-${blockId}`]: error instanceof Error ? error.message : t("blocks.resolveError") }));
    } finally {
      setPendingBlockId(null);
    }
  };

  const handleExtendBlock = async (blockId: number) => {
    if (!extensionEndDate) return;
    setPendingBlockId(blockId);
    setBlockMessage(null);
    setBlockErrors((current) => { const next = { ...current }; delete next[`extend-${blockId}`]; return next; });
    try {
      await extendBlockMutation.mutateAsync({ blockId, endsAt: extensionEndDate });
      setBlockMessage(t("blocks.extendSuccess"));
      setExtendingBlockId(null);
      setExtensionEndDate("");
    } catch (error) {
      setBlockErrors((current) => ({ ...current, [`extend-${blockId}`]: error instanceof Error ? error.message : t("blocks.extendError") }));
    } finally {
      setPendingBlockId(null);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">{t("header.eyebrow")}</p>
          <h1 className="text-balance text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">{t("header.title")}</h1>
          <p className="text-sm text-slate-600">{t("header.description")}</p>
        </div>
        {roomsQuery.isFetching && <p className="text-xs text-slate-500">{t("header.updating")}</p>}
      </header>

      {actionsBlocked && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {blockReason}{" "}
          <Link to="/settings/subscription" className="font-semibold underline">
            {t("subscription.goToSubscription")}
          </Link>
          .
        </div>
      )}

      {isHousekeeping && housekeepingBoardQuery.isLoading && (
        <p role="status" className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-600">
          {t("inventory.maintenanceStatusLoading")}
        </p>
      )}
      {isHousekeeping && housekeepingBoardQuery.isError && (
        <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          {t("inventory.maintenanceStatusError")}
        </p>
      )}

      {isHousekeeping ? (
        housekeepingBoardQuery.isSuccess ? (
          <div className="grid gap-4 sm:grid-cols-4">
            {housekeepingStatusOptions.map((status) => (
              <StatusBadge
                key={status}
                label={housekeepingStatusLabels[status]}
                value={housekeepingStats[status] ?? 0}
                className={housekeepingStatusColors[status]}
              />
            ))}
          </div>
        ) : null
      ) : roomsQuery.isSuccess ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <StatusBadge label={t("stats.available")} value={stats.available ?? 0} className={statusColors.available} />
          <StatusBadge label={t("stats.occupied")} value={stats.occupied ?? 0} className={statusColors.occupied} />
          <StatusBadge label={t("stats.cleaning")} value={stats.cleaning ?? 0} className={statusColors.cleaning} />
        </div>
      ) : null}

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">{t("inventory.eyebrow")}</p>
            <h2 className="text-lg font-semibold text-slate-900">{t("inventory.title", { count: rooms.length })}</h2>
            {roomsQuery.isLoading && <p role="status" className="text-xs text-slate-600">{t("inventory.loading")}</p>}
            {roomsQuery.isError && <p role="alert" className="text-xs text-rose-700">{t("inventory.loadError", { message: (roomsQuery.error as Error).message })} <button type="button" onClick={() => void roomsQuery.refetch()} className="font-semibold underline">{t("inventory.retry")}</button></p>}
            {!isHousekeeping && categoriesQuery.isError && <p role="alert" className="text-xs text-rose-700">{t("inventory.categoriesLoadError")} <button type="button" onClick={() => void categoriesQuery.refetch()} className="font-semibold underline">{t("inventory.retry")}</button></p>}
          </div>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {rooms.map((room) => {
            const category = categoryById.get(room.category_id);
            const canChangeThisStatus =
              canManageRoomStatus ||
              (isHousekeeping && canToggleCleaningStatus && room.is_active) ||
              (canToggleCleaningStatus && !isHousekeeping && ["available", "cleaning"].includes(room.status));
            const availableStatuses = canManageRoomStatus || !isHousekeeping ? statusOptions : housekeepingStatusOptions;
            const selectedStatus = isHousekeeping ? room.housekeeping_status : room.status;
            const maintenanceBlocked = isHousekeeping && housekeepingBoardQuery.isSuccess && maintenanceBlockedRoomIds.has(room.id);
            const activeRoomBlock = activeBlocks.find((block) => block.room_id === room.id);
            return (
              <div key={room.id} data-testid="room-card" className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">{t("inventory.roomLabel", { number: room.room_number || t("inventory.roomFallback") })}</p>
                    <h2 className="text-lg font-semibold text-slate-900">{category?.name || room.category?.name || t("inventory.categoryFallback")}</h2>
                    <p className="text-xs text-slate-500">
                      {t("inventory.floorAndCode", { floor: room.floor, code: category?.code || room.category?.code || t("inventory.noCode") })}
                    </p>
                    {!isHousekeeping && <p className="text-xs text-slate-600">
                      {t("inventory.rateToday")}{" "}
                      <span className="font-semibold text-slate-800">
                        ${formatRate(category?.current_rate ?? category?.base_price_per_night ?? room.category?.base_price_per_night)}
                      </span>
                      {t("inventory.perNight")}
                    </p>}
                    {showAssignments ? (() => {
                      const assignment = assignmentByRoomId.get(room.id);
                      return assignment ? (
                        <p className="mt-2 text-xs text-brand-700" data-testid={`room-assignment-${room.id}`}>
                          Asignación vigente: <span className="font-semibold">#{assignment.confirmation_code || assignment.guest_name || assignment.status}</span>
                          {assignment.guest_name ? ` · ${assignment.guest_name}` : ""}
                        </p>
                      ) : (
                        <p className="mt-2 text-xs text-slate-500">Sin asignación vigente</p>
                      );
                    })() : null}
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${maintenanceBlocked ? "bg-rose-100 text-rose-800" : statusColors[room.status]}`}>
                      {maintenanceBlocked ? t("housekeepingToday.maintenanceBlocked") : roomStatusLabel[room.status]}
                    </span>
                    {isHousekeeping && (
                      <span className={`rounded-full px-2 py-1 text-xs font-semibold ${housekeepingStatusColors[room.housekeeping_status]}`}>
                        {housekeepingStatusLabels[room.housekeeping_status]}
                      </span>
                    )}
                  </div>
                </div>
                <p className="mt-3 text-sm text-slate-700">{room.notes || t("inventory.noNotes")}</p>
                {blocksQuery.isSuccess && activeRoomBlock && (
                  <p className="mt-2 rounded-lg bg-rose-50 px-3 py-2 text-xs font-medium text-rose-800" data-testid={`room-active-block-${room.id}`}>
                    {activeRoomBlock.is_indefinite || !activeRoomBlock.ends_at
                      ? t("blocks.roomCardBlockedIndefinite", { reason: roomBlockReasonLabel[activeRoomBlock.reason_code] })
                      : t("blocks.roomCardBlocked", {
                          reason: roomBlockReasonLabel[activeRoomBlock.reason_code],
                          freeFrom: formatDate(activeRoomBlock.ends_at)
                        })}
                  </p>
                )}
                {canChangeThisStatus ? (
                  <div className="mt-4 text-xs text-slate-600">
                    <label htmlFor={`room-status-${room.id}`} className="mb-1 block font-semibold text-slate-600">
                      {isHousekeeping ? t("housekeepingStatus.label") : t("inventory.statusLabel")}
                    </label>
                    <select
                      id={`room-status-${room.id}`}
                      aria-label={isHousekeeping
                        ? `${t("housekeepingStatus.label")} · ${room.room_number}`
                        : t("inventory.statusAriaLabel", { number: room.room_number || t("inventory.roomFallback") })}
                      value={selectedStatus}
                      onChange={(e) => isHousekeeping
                        ? void handleHousekeepingStatusUpdate(room.id, e.target.value as HousekeepingStatus)
                        : void handleStatusUpdate(room.id, e.target.value as RoomStatus)}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-brand-400 focus:outline-none disabled:bg-slate-50"
                      disabled={actionsBlocked || (pendingRoom === room.id && (updateStatusMutation.isPending || updateCleaningStatusMutation.isPending))}
                    >
                      {availableStatuses.map((status) => (
                        <option key={status} value={status}>
                          {isHousekeeping
                            ? housekeepingStatusLabels[status as HousekeepingStatus]
                            : roomStatusLabel[status as RoomStatus]}
                        </option>
                      ))}
                    </select>
                    {isHousekeeping && canToggleCleaningStatus && (
                      <p className="mt-1 text-[11px] text-slate-500">{t("inventory.housekeepingHint")}</p>
                    )}
                    {pendingRoom === room.id && (updateStatusMutation.isPending || updateCleaningStatusMutation.isPending) && (
                      <p className="mt-2 text-xs text-slate-500">{t("inventory.saving")}</p>
                    )}
                    {roomStatusError?.roomId === room.id && (
                      <div role="alert" className="mt-2 flex items-start justify-between gap-2 text-xs text-rose-700">
                        <p>{t("inventory.statusUpdateError", { message: roomStatusError.message })}</p>
                        <button type="button" aria-label={t("blocks.closeError")} onClick={() => setRoomStatusError(null)} className="shrink-0 font-semibold underline">{t("blocks.closeError")}</button>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="mt-4 text-xs text-slate-400">{t("inventory.readOnlyRole")}</p>
                )}
              </div>
            );
          })}
          {!roomsQuery.isLoading && !roomsQuery.isError && rooms.length === 0 && (
            <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
              {t("inventory.empty")}
            </div>
          )}
        </div>
      </div>

      {canReadBlocks && <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">{t("blocks.eyebrow")}</p>
            <h2 className="text-lg font-semibold text-slate-900">{t("blocks.title", { count: activeBlocks.length })}</h2>
            <p className="text-sm text-slate-600">{t("blocks.description")}</p>
            {blocksQuery.isLoading && <p role="status" className="mt-1 text-xs text-slate-600">{t("blocks.loading")}</p>}
            {blocksQuery.isError && <p role="alert" className="mt-1 text-xs text-rose-700">{t("blocks.loadError", { message: (blocksQuery.error as Error).message })} <button type="button" onClick={() => void blocksQuery.refetch()} className="font-semibold underline">{t("blocks.retry")}</button></p>}
          </div>
          {blocksQuery.isFetching && <p className="text-xs text-slate-500">{t("blocks.updating")}</p>}
        </div>

        {canCreateBlocks && (
        <>
        <form className="mt-4 grid gap-4 rounded-lg border border-slate-200 bg-slate-50 p-4 lg:grid-cols-6" onSubmit={handleCreateBlock}>
          <label className="space-y-1 text-sm lg:col-span-1">
            <span className="text-slate-600">{t("blocks.roomFieldLabel")}</span>
            <select
              required
              value={blockForm.room_id}
              onChange={(event) => handleBlockFormChange("room_id", event.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
              disabled={actionsBlocked || createBlockMutation.isPending}
            >
              <option value="">{t("blocks.select")}</option>
              {rooms.map((room) => (
                <option key={room.id} value={room.id}>
                  {t("blocks.roomOption", { number: room.room_number })}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-1 text-sm lg:col-span-1">
            <span className="text-slate-600">{t("blocks.fromLabel")}</span>
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
            <span className="text-slate-600">{t("blocks.toLabel")}</span>
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
            <span className="text-slate-600">{t("blocks.reasonLabel")}</span>
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
            <span className="text-slate-600">{t("blocks.detailLabel")}</span>
            <input
              value={blockForm.reason_note}
              onChange={(event) => handleBlockFormChange("reason_note", event.target.value)}
              maxLength={500}
              placeholder={t("blocks.detailPlaceholder")}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
              disabled={actionsBlocked || createBlockMutation.isPending}
            />
          </label>

          {blockConflictPreviewQuery.isFetching && (
            <p role="status" className="text-sm text-slate-600 lg:col-span-6">{t("blocks.conflictsLoading")}</p>
          )}
          {blockConflictPreviewQuery.isError && (
            <p role="alert" className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 lg:col-span-6">
              {t("blocks.conflictVerificationError")}
            </p>
          )}
          {(blockConflictPreviewQuery.data?.reservation_count ?? 0) > 0 && (
            <div role="alert" className="space-y-1 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950 lg:col-span-6">
              <p>{t("blocks.conflictWarning", { count: blockConflictPreviewQuery.data!.reservation_count })}</p>
              {blockConflictPreviewQuery.data!.protected_reservation_count > 0 && (
                <p>{t("blocks.protectedConflictWarning", { count: blockConflictPreviewQuery.data!.protected_reservation_count })}</p>
              )}
            </div>
          )}

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
              {t("blocks.indefinite")}
            </label>
            <button
              type="submit"
              disabled={actionsBlocked || createBlockMutation.isPending}
              className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              {createBlockMutation.isPending ? t("blocks.creating") : t("blocks.create")}
            </button>
          </div>
        </form>
        {blockErrors.create && (
          <div role="alert" className="mt-3 flex items-start justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
            <p>{blockErrors.create}</p>
            <button type="button" onClick={() => setBlockErrors((current) => { const next = { ...current }; delete next.create; return next; })} className="shrink-0 font-semibold underline">{t("blocks.closeError")}</button>
          </div>
        )}
        </>
        )}

        {blockMessage && (
          <div role="status" className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">{blockMessage}</div>
        )}

        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {activeBlocks.map((block) => {
            const room = roomById.get(block.room_id);
            return (
              <div key={block.id} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">
                      {room ? t("blocks.roomFloor", { number: room.room_number, floor: room.floor }) : t("blocks.roomFallback")}
                    </p>
                    <h3 className="text-base font-semibold text-slate-900">{roomBlockReasonLabel[block.reason_code]}</h3>
                    <p className="text-xs text-slate-500">{formatBlockDates(block.starts_at, block.ends_at, block.is_indefinite, t)}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                  {canCreateBlocks && !block.is_indefinite && block.ends_at && (
                    <button
                      type="button"
                    onClick={() => {
                      setExtendingBlockId((current) => current === block.id ? null : block.id);
                      setExtensionEndDate("");
                      setBlockMessage(null);
                      setBlockErrors((current) => { const next = { ...current }; delete next[`extend-${block.id}`]; return next; });
                      }}
                      disabled={actionsBlocked || extendBlockMutation.isPending}
                      className="rounded-lg border border-brand-200 px-3 py-2 text-xs font-semibold text-brand-800 hover:bg-brand-50 disabled:opacity-60"
                    >
                      {extendingBlockId === block.id ? t("blocks.cancelExtend") : t("blocks.extend")}
                    </button>
                  )}
                  {canReleaseBlocks && (
                    <button
                      type="button"
                      onClick={() => handleResolveBlock(block.id)}
                      disabled={actionsBlocked || (pendingBlockId === block.id && resolveBlockMutation.isPending)}
                      className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                    >
                      {pendingBlockId === block.id && resolveBlockMutation.isPending ? t("blocks.resolving") : t("blocks.resolve")}
                    </button>
                  )}
                  </div>
                </div>
                <p className="mt-3 text-sm text-slate-700">{block.reason_note || t("blocks.noDetail")}</p>
                {blockErrors[`resolve-${block.id}`] && (
                  <div role="alert" className="mt-3 flex items-start justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
                    <p>{blockErrors[`resolve-${block.id}`]}</p>
                    <button type="button" onClick={() => setBlockErrors((current) => { const next = { ...current }; delete next[`resolve-${block.id}`]; return next; })} className="shrink-0 font-semibold underline">{t("blocks.closeError")}</button>
                  </div>
                )}
                {extendingBlockId === block.id && (
                  <div className="mt-3 space-y-2 rounded-lg bg-slate-50 p-3">
                    <label className="block text-xs font-semibold text-slate-700">
                      {t("blocks.extendEndLabel")}
                      <input
                        type="date"
                        value={extensionEndDate}
                        min={block.ends_at ?? undefined}
                        onChange={(event) => setExtensionEndDate(event.target.value)}
                        className="mt-1 block min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                        disabled={extendBlockMutation.isPending}
                      />
                    </label>
                    {extensionRangeReady && blockExtensionPreviewQuery.isLoading && <p role="status" className="text-xs text-slate-600">{t("blocks.extendPreviewLoading")}</p>}
                    {extensionRangeReady && blockExtensionPreviewQuery.isError && <p role="alert" className="text-xs text-rose-700">{t("blocks.extendPreviewError")} <button type="button" onClick={() => void blockExtensionPreviewQuery.refetch()} className="font-semibold underline">{t("blocks.retry")}</button></p>}
                    {extensionRangeReady && blockExtensionPreviewQuery.data && (
                      <p className="text-xs text-slate-700">
                        {t("blocks.extendPreviewSummary", {
                          reservations: blockExtensionPreviewQuery.data.reservation_count,
                          protected: blockExtensionPreviewQuery.data.protected_reservation_count,
                          blocks: blockExtensionPreviewQuery.data.overlapping_block_count ?? 0
                        })}
                      </p>
                    )}
                    {extensionRangeReady && blockExtensionPreviewQuery.data && (blockExtensionPreviewQuery.data.protected_reservation_count > 0 || (blockExtensionPreviewQuery.data.overlapping_block_count ?? 0) > 0) && (
                      <p role="alert" className="text-xs text-rose-700">{t("blocks.extendConflict")}</p>
                    )}
                    {blockErrors[`extend-${block.id}`] && (
                      <div role="alert" className="flex items-start justify-between gap-3 text-xs text-rose-700">
                        <p>{blockErrors[`extend-${block.id}`]}</p>
                        <button type="button" onClick={() => setBlockErrors((current) => { const next = { ...current }; delete next[`extend-${block.id}`]; return next; })} className="shrink-0 font-semibold underline">{t("blocks.closeError")}</button>
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() => void handleExtendBlock(block.id)}
                      disabled={actionsBlocked || !extensionRangeReady || !blockExtensionPreviewQuery.isSuccess || blockExtensionPreviewQuery.data.protected_reservation_count > 0 || (blockExtensionPreviewQuery.data.overlapping_block_count ?? 0) > 0 || extendBlockMutation.isPending}
                      className="min-h-10 rounded-lg bg-brand-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
                    >
                      {extendBlockMutation.isPending ? t("blocks.extending") : t("blocks.confirmExtend")}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
          {!blocksQuery.isLoading && !blocksQuery.isError && activeBlocks.length === 0 && (
            <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
              {t("blocks.empty")}
            </div>
          )}
        </div>
      </section>}
    </div>
  );
}

function formatBlockDates(startsAt: string, endsAt: string | null | undefined, isIndefinite: boolean | undefined, t: TFunction) {
  const start = formatDate(startsAt);
  if (isIndefinite) return t("blocks.datesIndefinite", { start });
  return t("blocks.datesRange", { start, end: endsAt ? formatDate(endsAt) : t("blocks.noEndDate") });
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
