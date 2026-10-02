import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { hasValidSession } from "../../api/client";
import { queryKeys } from "../../api/queryKeys";
import { getHousekeepingBoard, updateRoomCleaningStatus, type HousekeepingStatus } from "../../api/rooms";
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
    staleTime: 15_000
  });
  const statusMutation = useGuardedMutation({
    mutationFn: ({ roomId, status }: { roomId: number; status: HousekeepingStatus }) =>
      updateRoomCleaningStatus(roomId, status, undefined, session),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["housekeeping-board", session.hotelId] });
      await queryClient.invalidateQueries({ queryKey: ["rooms", session.hotelId] });
    }
  });

  const rooms = useMemo(() => boardQuery.data?.rooms ?? [], [boardQuery.data?.rooms]);
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
            onClick={() => void boardQuery.refetch()}
            disabled={boardQuery.isFetching}
            className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60"
          >
            {boardQuery.isFetching ? t("housekeepingToday.refreshing") : t("housekeepingToday.refresh")}
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

      {boardQuery.isLoading ? <p role="status" className="rounded-lg bg-white p-4 text-sm text-slate-600">{t("housekeepingToday.loading")}</p> : null}
      {boardQuery.isError ? (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          {t("housekeepingToday.loadError")}
          <button type="button" onClick={() => void boardQuery.refetch()} className="ml-2 font-semibold underline">{t("housekeepingToday.retry")}</button>
        </div>
      ) : null}
      {statusMutation.isError ? (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          {t("inventory.statusUpdateError", { message: statusMutation.error instanceof Error ? statusMutation.error.message : t("inventory.statusUpdateDefaultError") })}
        </div>
      ) : null}
      {!boardQuery.isLoading && !boardQuery.isError && rooms.length === 0 ? (
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
              {floorRooms.map((room) => (
                <article key={room.room_id} className="flex min-w-0 flex-col gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-sm sm:flex-row sm:items-center sm:justify-between">
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
                      {room.maintenance_blocked && <span className="rounded-full bg-rose-100 px-2 py-0.5 font-semibold text-rose-800">{t("housekeepingToday.maintenanceBlocked")}</span>}
                      {!room.has_arrival_today && !room.has_departure_today && !room.has_stayover_today && !room.maintenance_blocked && (
                        <span className="text-slate-500">{t("housekeepingToday.noSpecialEvents")}</span>
                      )}
                    </div>
                  </div>
                  {canUpdate ? (
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
              ))}
            </div>
          </section>
        ))}
      </section>
    </main>
  );
}
