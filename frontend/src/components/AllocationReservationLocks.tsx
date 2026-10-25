import { useTranslation } from "react-i18next";

import type { Reservation } from "../api/reservations";
import type { Room } from "../api/rooms";

type AllocationReservationLocksProps = {
  reservations: Reservation[];
  roomsById: Map<number, Room>;
  isLoading: boolean;
  error: string | null;
  canReadReservations: boolean;
  canEditReservations: boolean;
  isUpdating: boolean;
  updatingReservationId: number | null;
  page: number;
  hasNextPage: boolean;
  onPageChange: (page: number) => void;
  onToggle: (reservationId: number, locked: boolean) => Promise<unknown>;
};

const eligibleStatuses = new Set(["pending", "deposit_paid", "fully_paid"]);

export function AllocationReservationLocks({
  reservations,
  roomsById,
  isLoading,
  error,
  canReadReservations,
  canEditReservations,
  isUpdating,
  updatingReservationId,
  page,
  hasNextPage,
  onPageChange,
  onToggle
}: AllocationReservationLocksProps) {
  const { t } = useTranslation("allocation");

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5" aria-labelledby="allocation-locks-title">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{t("locks.eyebrow")}</p>
        <h2 id="allocation-locks-title" className="mt-1 text-lg font-semibold text-slate-900">{t("locks.title")}</h2>
        <p className="mt-1 max-w-2xl text-sm text-slate-600">{t("locks.description")}</p>
      </div>

      {!canReadReservations ? <p className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">{t("locks.readPermissionRequired")}</p> : null}
      {canReadReservations && isLoading ? <p className="mt-4 text-sm text-slate-600" role="status">{t("locks.loading")}</p> : null}
      {canReadReservations && error ? <p className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">{t("locks.loadFailed", { message: error })}</p> : null}
      {canReadReservations && !isLoading && !error && reservations.length === 0 ? <p className="mt-4 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-700">{t("locks.empty")}</p> : null}

      {canReadReservations && reservations.length > 0 ? (
        <div className="mt-4 space-y-3">
          {reservations.map((reservation) => {
            const room = reservation.room_id ? roomsById.get(reservation.room_id) : undefined;
            const eligible = eligibleStatuses.has(reservation.status) && Boolean(reservation.room_id);
            const locked = Boolean(reservation.allocation_locked);
            const isThisUpdating = updatingReservationId === reservation.id && isUpdating;
            return (
              <article key={reservation.id} className="flex flex-col gap-3 rounded-xl border border-slate-200 p-3 sm:flex-row sm:items-center sm:justify-between sm:p-4">
                <div className="min-w-0">
                  <p className="truncate font-semibold text-slate-900">{reservation.confirmation_code}</p>
                  <p className="mt-1 text-sm text-slate-600">{reservation.check_in_date} — {reservation.check_out_date}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {room ? t("locks.room", { room: room.room_number }) : reservation.room_id ? t("locks.roomId", { id: reservation.room_id }) : t("locks.noRoom")}
                    <span aria-hidden="true"> · </span>
                    {t(`locks.status.${reservation.status}`, { defaultValue: reservation.status })}
                  </p>
                </div>
                <div className="flex flex-col items-start gap-2 sm:items-end">
                  <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${locked ? "bg-amber-100 text-amber-900" : "bg-slate-100 text-slate-700"}`}>
                    {locked ? t("locks.locked") : t("locks.unlocked")}
                  </span>
                  {eligible ? (
                    <button
                      type="button"
                      aria-pressed={locked}
                      onClick={() => void onToggle(reservation.id, !locked)}
                      disabled={!canEditReservations || isUpdating}
                      className="min-h-10 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-brand-400 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isThisUpdating ? t("locks.saving") : locked ? t("locks.unlockAction") : t("locks.lockAction")}
                    </button>
                  ) : (
                    <span className="text-xs text-slate-500">{t("locks.lockNotAvailable")}</span>
                  )}
                  {eligible && !canEditReservations ? <span className="text-xs text-slate-500">{t("locks.updatePermissionRequired")}</span> : null}
                </div>
              </article>
            );
          })}

          <div className="flex flex-col gap-2 border-t border-slate-200 pt-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-slate-500">{t("locks.page", { page: page + 1 })}</p>
            <div className="flex gap-2">
              <button type="button" onClick={() => onPageChange(page - 1)} disabled={page <= 0 || isLoading} className="min-h-10 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-brand-400 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50">{t("locks.previous")}</button>
              <button type="button" onClick={() => onPageChange(page + 1)} disabled={!hasNextPage || isLoading} className="min-h-10 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-brand-400 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50">{t("locks.next")}</button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
