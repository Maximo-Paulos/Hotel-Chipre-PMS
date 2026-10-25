import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { hasValidSession } from "../../api/client";
import { invalidateQueriesInBackground } from "../../api/queryInvalidation";
import { queryKeys } from "../../api/queryKeys";
import { EVENT_REFRESHED_QUERY_STALE_TIME_MS } from "../../api/queryPolicy";
import {
  completeHousekeepingChecklistItem,
  HOUSEKEEPING_CHECKLIST_ITEM_CODES,
  getHousekeepingBoard,
  getOpenHousekeepingChecklists,
  updateRoomCleaningStatus,
  type HousekeepingBoard,
  type HousekeepingChecklistItemCode,
  type HousekeepingStatus,
  type OpenHousekeepingChecklistsResponse
} from "../../api/rooms";
import { useGuardedMutation } from "../../hooks/useGuardedMutation";
import { useEffectivePermissions } from "../../hooks/usePermissions";
import { useSession } from "../../state/session";

const statusOrder: HousekeepingStatus[] = ["dirty", "in_progress", "clean", "inspected"];
const statusClasses: Record<HousekeepingStatus, string> = {
  dirty: "border-rose-200 bg-rose-50",
  in_progress: "border-amber-200 bg-amber-50",
  clean: "border-emerald-200 bg-emerald-50",
  inspected: "border-sky-200 bg-sky-50"
};

export function HousekeepingTodayPage() {
  const { session } = useSession();
  const { t, i18n } = useTranslation("rooms");
  const { hasPermission } = useEffectivePermissions();
  const queryClient = useQueryClient();
  const [selectedFloor, setSelectedFloor] = useState("all");
  const enabled = hasValidSession(session);
  const canUpdate = hasPermission("room:status_update");
  const boardQuery = useQuery({
    queryKey: queryKeys.housekeepingBoard(session.hotelId),
    queryFn: () => getHousekeepingBoard(session),
    enabled,
    staleTime: EVENT_REFRESHED_QUERY_STALE_TIME_MS
  });
  const checklistsQuery = useQuery({
    queryKey: queryKeys.housekeepingChecklists(session.hotelId),
    queryFn: () => getOpenHousekeepingChecklists(session),
    enabled,
    staleTime: EVENT_REFRESHED_QUERY_STALE_TIME_MS
  });
  const statusMutation = useGuardedMutation({
    mutationFn: ({ roomId, status }: { roomId: number; status: HousekeepingStatus }) =>
      updateRoomCleaningStatus(roomId, status, undefined, session),
    onSuccess: () => {
      invalidateQueriesInBackground(queryClient, { queryKey: queryKeys.housekeepingBoard(session.hotelId) });
      invalidateQueriesInBackground(queryClient, { queryKey: queryKeys.rooms(session.hotelId) });
    }
  });
  const checklistMutation = useGuardedMutation({
    mutationFn: ({ checklistId, itemCode }: { checklistId: number; itemCode: HousekeepingChecklistItemCode }) =>
      completeHousekeepingChecklistItem(checklistId, itemCode, session),
    onSuccess: (updatedChecklist) => {
      queryClient.setQueryData<OpenHousekeepingChecklistsResponse>(
        queryKeys.housekeepingChecklists(session.hotelId),
        (current) => {
          if (!current) return current;
          return {
            checklists: updatedChecklist.status === "completed"
              ? current.checklists.filter((checklist) => checklist.checklist_id !== updatedChecklist.checklist_id)
              : current.checklists.map((checklist) => checklist.checklist_id === updatedChecklist.checklist_id
                ? updatedChecklist
                : checklist)
          };
        }
      );
      queryClient.setQueryData<HousekeepingBoard>(queryKeys.housekeepingBoard(session.hotelId), (current) => {
        if (!current) return current;
        return {
          ...current,
          rooms: current.rooms.map((room) => room.room_id === updatedChecklist.room.id
            ? {
                ...room,
                operational_status: updatedChecklist.room.operational_status,
                housekeeping_status: updatedChecklist.room.housekeeping_status
              }
            : room)
        };
      });
      invalidateQueriesInBackground(queryClient, { queryKey: queryKeys.housekeepingBoard(session.hotelId) });
      invalidateQueriesInBackground(queryClient, { queryKey: queryKeys.housekeepingChecklists(session.hotelId) });
      invalidateQueriesInBackground(queryClient, { queryKey: queryKeys.rooms(session.hotelId) });
    }
  });

  const rooms = useMemo(() => boardQuery.data?.rooms ?? [], [boardQuery.data?.rooms]);
  const checklistsByRoom = useMemo(
    () => new Map((checklistsQuery.data?.checklists ?? []).map((checklist) => [checklist.room.id, checklist])),
    [checklistsQuery.data?.checklists]
  );
  const floors = useMemo(() => [...new Set(rooms.map((room) => room.floor))].sort((a, b) => a - b), [rooms]);
  const visibleRooms = useMemo(
    () => selectedFloor === "all" ? rooms : rooms.filter((room) => String(room.floor) === selectedFloor),
    [rooms, selectedFloor]
  );
  const roomsByFloor = useMemo(() => {
    const groups = new Map<number, typeof visibleRooms>();
    for (const room of visibleRooms) {
      groups.set(room.floor, [...(groups.get(room.floor) ?? []), room]);
    }
    return [...groups.entries()];
  }, [visibleRooms]);
  const counts = useMemo(() => rooms.reduce(
    (value, room) => ({ ...value, [room.housekeeping_status]: value[room.housekeeping_status] + 1 }),
    { dirty: 0, in_progress: 0, clean: 0, inspected: 0 }
  ), [rooms]);
  const boardDate = boardQuery.data?.date
    ? new Intl.DateTimeFormat(i18n.resolvedLanguage === "en" ? "en-US" : "es-AR", { dateStyle: "full" })
      .format(new Date(`${boardQuery.data.date}T12:00:00`))
    : "";

  const updateStatus = async (roomId: number, status: HousekeepingStatus) => {
    try {
      await statusMutation.mutateAsync({ roomId, status });
    } catch {
      // useGuardedMutation surfaces the request error in the shared mutation state.
    }
  };

  return (
    <main className="mx-auto w-full max-w-6xl space-y-5 px-3 py-4 sm:px-6 sm:py-6">
      <header className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{t("housekeepingToday.eyebrow")}</p>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">{t("housekeepingToday.title")}</h1>
            <p className="text-sm text-slate-600">{boardDate || t("housekeepingToday.loadingDate")}</p>
          </div>
          <button
            type="button"
            onClick={() => void Promise.all([boardQuery.refetch(), checklistsQuery.refetch()])}
            disabled={boardQuery.isFetching || checklistsQuery.isFetching}
            className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60"
          >
            {boardQuery.isFetching || checklistsQuery.isFetching ? t("housekeepingToday.refreshing") : t("housekeepingToday.refresh")}
          </button>
        </div>
      </header>

      <section aria-label={t("housekeepingToday.summary")} className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {statusOrder.map((status) => (
          <div key={status} className={`rounded-xl border p-3 ${statusClasses[status]}`}>
            <p className="text-xs text-slate-600">{t(`housekeepingStatus.${status}`)}</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">{counts[status]}</p>
          </div>
        ))}
      </section>

      {boardQuery.isLoading || checklistsQuery.isLoading ? <p role="status" className="rounded-lg bg-white p-4 text-sm text-slate-600">{t("housekeepingToday.loading")}</p> : null}
      {boardQuery.isError ? (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          {t("housekeepingToday.loadError")}
          <button type="button" onClick={() => void boardQuery.refetch()} className="ml-2 font-semibold underline">{t("housekeepingToday.retry")}</button>
        </div>
      ) : null}
      {checklistsQuery.isError ? (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          {t("housekeepingToday.checklistsLoadError")}
          <button type="button" onClick={() => void checklistsQuery.refetch()} className="ml-2 font-semibold underline">
            {t("housekeepingToday.retry")}
          </button>
        </div>
      ) : null}
      {statusMutation.isError ? (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          {t("inventory.statusUpdateError", { message: statusMutation.error instanceof Error ? statusMutation.error.message : t("inventory.statusUpdateDefaultError") })}
        </div>
      ) : null}
      {checklistMutation.isError ? (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          {t("housekeepingToday.checklistUpdateError")}
        </div>
      ) : null}
      {boardQuery.isSuccess && checklistsQuery.isSuccess && rooms.length === 0 ? (
        <p className="rounded-lg bg-white p-4 text-sm text-slate-600">{t("housekeepingToday.empty")}</p>
      ) : null}

      <label className="block max-w-xs text-sm font-medium text-slate-700">
        {t("housekeepingToday.floorFilter")}
        <select
          aria-label={t("housekeepingToday.floorFilter")}
          value={selectedFloor}
          onChange={(event) => setSelectedFloor(event.target.value)}
          className="mt-1 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
        >
          <option value="all">{t("housekeepingToday.allFloors")}</option>
          {floors.map((floor) => <option key={floor} value={String(floor)}>{t("housekeepingToday.floorLabel", { floor })}</option>)}
        </select>
      </label>

      <section aria-label={t("housekeepingToday.roomList")} className="space-y-4">
        {roomsByFloor.map(([floor, floorRooms]) => (
          <section key={floor} aria-label={t("housekeepingToday.floorLabel", { floor })}>
            <h2 className="mb-2 text-sm font-semibold text-slate-700">{t("housekeepingToday.floorLabel", { floor })}</h2>
            <div className="space-y-2">
              {floorRooms.map((room) => {
                const checklist = checklistsByRoom.get(room.room_id);
                const completedCount = checklist?.items.filter((item) => item.completed).length ?? 0;
                return (
                <article key={room.room_id} className="flex min-w-0 flex-col gap-3 rounded-lg border border-slate-200 bg-white px-3 py-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <h3 className="font-semibold text-slate-900">{t("housekeepingToday.room", { number: room.room_number })}</h3>
                      <span className="text-xs text-slate-600">{room.category_name}</span>
                      <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${statusClasses[room.housekeeping_status]}`}>
                        {t(`housekeepingStatus.${room.housekeeping_status}`)}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1.5 text-[11px]">
                      {room.has_departure_today && <span className="rounded-full bg-orange-50 px-2 py-0.5 text-orange-800">{t("housekeepingToday.departure")}</span>}
                      {room.has_arrival_today && <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-indigo-800">{t("housekeepingToday.arrival")}</span>}
                      {room.has_stayover_today && <span className="rounded-full bg-sky-50 px-2 py-0.5 text-sky-800">{t("housekeepingToday.stayover")}</span>}
                      {room.active_block_reasons.map((reason) => (
                        <span key={reason} className="rounded-full bg-rose-100 px-2 py-0.5 font-semibold text-rose-800">
                          {t(`housekeepingToday.blockReasons.${reason}`)}
                        </span>
                      ))}
                      {!room.has_arrival_today && !room.has_departure_today && !room.has_stayover_today && room.active_block_reasons.length === 0 && (
                        <span className="text-slate-500">{t("housekeepingToday.noSpecialEvents")}</span>
                      )}
                    </div>
                  </div>
                  {checklist ? (
                    <div className="w-full min-w-0 rounded-lg border border-indigo-100 bg-indigo-50/50 p-3 sm:max-w-md">
                      <div className="flex flex-wrap items-baseline justify-between gap-1">
                        <h4 className="text-sm font-semibold text-slate-900">{t("housekeepingToday.checklist.title")}</h4>
                        <p className="text-xs text-slate-600" aria-live="polite">
                          {t("housekeepingToday.checklist.progress", { completed: completedCount, total: checklist.items.length })}
                        </p>
                      </div>
                      <fieldset className="mt-2 space-y-1.5" disabled={!canUpdate || checklistMutation.isPending}>
                        <legend className="sr-only">
                          {t("housekeepingToday.checklist.title")} · {t("housekeepingToday.room", { number: room.room_number })}
                        </legend>
                        {HOUSEKEEPING_CHECKLIST_ITEM_CODES.map((itemCode) => {
                          const item = checklist.items.find((checklistItem) => checklistItem.code === itemCode);
                          if (!item) return null;
                          return (
                            <label key={item.code} className="flex min-h-9 cursor-pointer items-center gap-2 rounded-md px-1 text-sm text-slate-800 focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-indigo-600">
                              <input
                                type="checkbox"
                                checked={item.completed}
                                disabled={!canUpdate || item.completed || checklistMutation.isPending}
                                onChange={(event) => {
                                  if (event.currentTarget.checked) {
                                    checklistMutation.mutate({ checklistId: checklist.checklist_id, itemCode: item.code });
                                  }
                                }}
                                className="h-4 w-4 shrink-0 rounded border-slate-400 text-indigo-700 focus:ring-indigo-600"
                              />
                              <span>{t(`housekeepingToday.checklist.items.${item.code}`)}</span>
                            </label>
                          );
                        })}
                      </fieldset>
                      <p className="mt-2 text-xs text-slate-600">{t("housekeepingToday.checklist.completionHint")}</p>
                      {!canUpdate ? <p className="mt-1 text-xs text-amber-800">{t("housekeepingToday.checklist.readOnly")}</p> : null}
                    </div>
                  ) : canUpdate && checklistsQuery.isSuccess ? (
                    <label className="flex shrink-0 items-center gap-2 text-xs text-slate-700 sm:min-w-44">
                      <span className="sr-only">{t("housekeepingStatus.label")}</span>
                      <select
                        aria-label={t("housekeepingToday.statusForRoom", { number: room.room_number })}
                        value={room.housekeeping_status}
                        disabled={statusMutation.isPending}
                        onChange={(event) => void updateStatus(room.room_id, event.target.value as HousekeepingStatus)}
                        className="min-h-10 w-full rounded-lg border border-slate-300 bg-white px-2 py-1"
                      >
                        {statusOrder.map((status) => <option key={status} value={status}>{t(`housekeepingStatus.${status}`)}</option>)}
                      </select>
                    </label>
                  ) : null}
                </article>
                );
              })}
            </div>
          </section>
        ))}
      </section>
    </main>
  );
}
