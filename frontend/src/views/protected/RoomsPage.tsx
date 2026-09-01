import { type FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

import { type RoomBlockCreatePayload, type RoomBlockReasonCode } from "../../api/roomBlocks";
import { type RoomStatus } from "../../api/rooms";
import { roomBlockReasonLabel, roomBlockReasonOptions, useRoomBlocks } from "../../hooks/useRoomBlocks";
import { useSubscriptionStatus } from "../../hooks/useSubscription";
import { roomStatusLabel, useRooms } from "../../hooks/useRooms";
import { useEffectivePermissions } from "../../hooks/usePermissions";
import { useSession } from "../../state/session";
import { todayIso } from "../../utils/date";

const statusColors: Record<RoomStatus, string> = {
  available: "bg-emerald-100 text-emerald-800",
  occupied: "bg-rose-100 text-rose-800",
  cleaning: "bg-amber-100 text-amber-800",
  maintenance: "bg-orange-100 text-orange-800",
  blocked: "bg-slate-200 text-slate-700"
};

const statusOptions: RoomStatus[] = ["available", "occupied", "cleaning", "maintenance", "blocked"];
const cleaningStatusOptions: RoomStatus[] = ["available", "cleaning"];

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
  const { session } = useSession();
  const { hasPermission } = useEffectivePermissions();
  const isHousekeeping = session.baseRole === "housekeeping";
  const canManageRoomStatus = ["owner", "co_owner", "manager"].includes(session.baseRole ?? "");
  const canToggleCleaningStatus = hasPermission("room:status_update");
  const canCreateBlocks = hasPermission("room:block_create");
  const canReleaseBlocks = hasPermission("room:block_release");
  const { roomsQuery, categoriesQuery, updateStatusMutation, updateCleaningStatusMutation } = useRooms({
    includeCategories: !isHousekeeping
  });
  const { blocksQuery, createBlockMutation, resolveBlockMutation } = useRoomBlocks({ enabled: !isHousekeeping });
  const rooms = useMemo(() => roomsQuery.data || [], [roomsQuery.data]);
  const categories = useMemo(() => categoriesQuery.data || [], [categoriesQuery.data]);
  const activeBlocks = useMemo(() => blocksQuery.data || [], [blocksQuery.data]);
  const [pendingRoom, setPendingRoom] = useState<number | null>(null);
  const [roomStatusError, setRoomStatusError] = useState<{ roomId: number; message: string } | null>(null);
  const [pendingBlockId, setPendingBlockId] = useState<number | null>(null);
  const [blockForm, setBlockForm] = useState<BlockFormValues>(() => emptyBlockForm());
  const [blockMessage, setBlockMessage] = useState<string | null>(null);
  const { data: subscription } = useSubscriptionStatus({ enabled: !isHousekeeping });

  const writeBlocked = subscription?.can_write === false;
  const inactiveSubscription = subscription && subscription.status !== "active";
  const actionsBlocked = Boolean(subscription) && (writeBlocked || inactiveSubscription);
  const blockReason = actionsBlocked
    ? writeBlocked
      ? t("subscription.readOnly")
      : t("subscription.inactive")
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

  const handleStatusUpdate = async (roomId: number, status: RoomStatus) => {
    if (actionsBlocked || (!canManageRoomStatus && !canToggleCleaningStatus)) return;
    setRoomStatusError(null);
    setPendingRoom(roomId);
    try {
      if (canManageRoomStatus) {
        await updateStatusMutation.mutateAsync({ roomId, status });
      } else if (status === "available" || status === "cleaning") {
        await updateCleaningStatusMutation.mutateAsync({ roomId, status });
      }
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

    const roomId = Number(blockForm.room_id);
    if (!Number.isInteger(roomId) || roomId <= 0) {
      setBlockMessage(t("blocks.selectRoomError"));
      return;
    }
    if (!blockForm.is_indefinite && !blockForm.ends_at) {
      setBlockMessage(t("blocks.endDateRequired"));
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
      setBlockMessage(error instanceof Error ? error.message : t("blocks.createError"));
    }
  };

  const handleResolveBlock = async (blockId: number) => {
    if (actionsBlocked || !canReleaseBlocks) return;
    setPendingBlockId(blockId);
    setBlockMessage(null);
    try {
      await resolveBlockMutation.mutateAsync(blockId);
      setBlockMessage(t("blocks.resolveSuccess"));
    } catch (error) {
      setBlockMessage(error instanceof Error ? error.message : t("blocks.resolveError"));
    } finally {
      setPendingBlockId(null);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">{t("header.eyebrow")}</p>
          <h1 className="text-2xl font-semibold text-slate-900">{t("header.title")}</h1>
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

      <div className="grid gap-4 sm:grid-cols-3">
        <StatusBadge label={t("stats.available")} value={stats.available ?? 0} className={statusColors.available} />
        <StatusBadge label={t("stats.occupied")} value={stats.occupied ?? 0} className={statusColors.occupied} />
        <StatusBadge label={t("stats.cleaning")} value={stats.cleaning ?? 0} className={statusColors.cleaning} />
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">{t("inventory.eyebrow")}</p>
            <h2 className="text-lg font-semibold text-slate-900">{t("inventory.title", { count: rooms.length })}</h2>
            {roomsQuery.error && <p className="text-xs text-rose-700">{t("inventory.loadError", { message: (roomsQuery.error as Error).message })}</p>}
          </div>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {rooms.map((room) => {
            const category = categoryById.get(room.category_id);
            const canChangeThisStatus =
              canManageRoomStatus ||
              (canToggleCleaningStatus && cleaningStatusOptions.includes(room.status));
            const availableStatuses = canManageRoomStatus ? statusOptions : cleaningStatusOptions;
            return (
              <div key={room.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">{t("inventory.roomLabel", { number: room.room_number })}</p>
                    <h2 className="text-lg font-semibold text-slate-900">{category?.name || room.category?.name || t("inventory.categoryFallback", { id: room.category_id })}</h2>
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
                  </div>
                  <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusColors[room.status]}`}>
                    {roomStatusLabel[room.status]}
                  </span>
                </div>
                <p className="mt-3 text-sm text-slate-700">{room.notes || t("inventory.noNotes")}</p>
                {canChangeThisStatus ? (
                  <div className="mt-4 text-xs text-slate-600">
                    <label htmlFor={`room-status-${room.id}`} className="mb-1 block font-semibold text-slate-600">
                      {t("inventory.statusLabel")}
                    </label>
                    <select
                      id={`room-status-${room.id}`}
                      aria-label={t("inventory.statusAriaLabel", { number: room.room_number })}
                      value={room.status}
                      onChange={(e) => void handleStatusUpdate(room.id, e.target.value as RoomStatus)}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-brand-400 focus:outline-none disabled:bg-slate-50"
                      disabled={actionsBlocked || (pendingRoom === room.id && (updateStatusMutation.isPending || updateCleaningStatusMutation.isPending))}
                    >
                      {availableStatuses.map((status) => (
                        <option key={status} value={status}>
                          {roomStatusLabel[status]}
                        </option>
                      ))}
                    </select>
                    {!canManageRoomStatus && canToggleCleaningStatus && (
                      <p className="mt-1 text-[11px] text-slate-500">{t("inventory.housekeepingHint")}</p>
                    )}
                    {pendingRoom === room.id && (updateStatusMutation.isPending || updateCleaningStatusMutation.isPending) && (
                      <p className="mt-2 text-xs text-slate-500">{t("inventory.saving")}</p>
                    )}
                    {roomStatusError?.roomId === room.id && (
                      <p role="alert" className="mt-2 text-xs text-rose-700">
                        {t("inventory.statusUpdateError", { message: roomStatusError.message })}
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="mt-4 text-xs text-slate-400">{t("inventory.readOnlyRole")}</p>
                )}
              </div>
            );
          })}
          {!roomsQuery.isLoading && rooms.length === 0 && (
            <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
              {t("inventory.empty")}
            </div>
          )}
        </div>
      </div>

      {!isHousekeeping && <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">{t("blocks.eyebrow")}</p>
            <h2 className="text-lg font-semibold text-slate-900">{t("blocks.title", { count: activeBlocks.length })}</h2>
            <p className="text-sm text-slate-600">{t("blocks.description")}</p>
            {blocksQuery.error && <p className="mt-1 text-xs text-rose-700">{t("blocks.loadError", { message: (blocksQuery.error as Error).message })}</p>}
          </div>
          {blocksQuery.isFetching && <p className="text-xs text-slate-500">{t("blocks.updating")}</p>}
        </div>

        {canCreateBlocks && (
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
                      {room ? t("blocks.roomFloor", { number: room.room_number, floor: room.floor }) : t("blocks.roomFallback", { id: block.room_id })}
                    </p>
                    <h3 className="text-base font-semibold text-slate-900">{roomBlockReasonLabel[block.reason_code]}</h3>
                    <p className="text-xs text-slate-500">{formatBlockDates(block.starts_at, block.ends_at, block.is_indefinite, t)}</p>
                  </div>
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
                <p className="mt-3 text-sm text-slate-700">{block.reason_note || t("blocks.noDetail")}</p>
              </div>
            );
          })}
          {!blocksQuery.isLoading && activeBlocks.length === 0 && (
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
