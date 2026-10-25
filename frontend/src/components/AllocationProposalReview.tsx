import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { AllocationAssignment, AllocationRunDetail } from "../api/allocation";
import type { Reservation } from "../api/reservations";
import type { Room } from "../api/rooms";

type AllocationProposalReviewProps = {
  run: AllocationRunDetail | undefined;
  isLoading: boolean;
  loadError: string | null;
  isNotFound: boolean;
  reservationById: Map<number, Reservation>;
  roomById: Map<number, Room>;
  canReadReservations: boolean;
  isRecalculating: boolean;
  isAccepting: boolean;
  isRejecting: boolean;
  canRecalculate: boolean;
  recalculationDisabledReason: string | null;
  onRecalculate: () => Promise<unknown>;
  onAccept: (runId: number) => Promise<unknown>;
  onReject: (runId: number) => Promise<unknown>;
};

function allocationErrorKey(error: string) {
  if (/mixed|currency|moneda|cotizaci[oó]n|\bfx\b/iu.test(error)) return "proposal.solverErrors.mixedCurrency";
  if (/combined|comparable scale|escala comparable/iu.test(error)) return "proposal.solverErrors.combinedUnavailable";
  return null;
}

function assignmentReason(assignment: AllocationAssignment, run: AllocationRunDetail, translate: (key: string) => string) {
  const explanation = run.explanations.find((item) => item.reservation_id === assignment.reservation_id && item.explanation_type === "assignment");
  const details = explanation?.details ?? {};
  const reasons: string[] = [];
  if (details.is_exact_match === true) reasons.push(translate("proposal.reasons.exactCategory"));
  if (details.is_exact_match === false) reasons.push(translate("proposal.reasons.compatibleCategory"));
  if (details.was_moved === true) reasons.push(translate("proposal.reasons.optimizesRoomUse"));
  if (typeof details.prior_stay_room_id === "number" && details.prior_stay_room_id === assignment.room_id) {
    reasons.push(translate("proposal.reasons.returningGuest"));
  }
  if (Array.isArray(details.avoided_room_ids) && details.avoided_room_ids.length > 0) {
    reasons.push(translate("proposal.reasons.guestPreference"));
  }
  return reasons.length > 0 ? reasons.join(" · ") : assignment.explanation_summary || explanation?.summary || translate("proposal.reasons.noDetails");
}

export function AllocationProposalReview({
  run,
  isLoading,
  loadError,
  isNotFound,
  reservationById,
  roomById,
  canReadReservations,
  isRecalculating,
  isAccepting,
  isRejecting,
  canRecalculate,
  recalculationDisabledReason,
  onRecalculate,
  onAccept,
  onReject
}: AllocationProposalReviewProps) {
  const { t, i18n } = useTranslation("allocation");
  const [confirmation, setConfirmation] = useState<"accept" | "reject" | null>(null);
  const proposed = run?.assignments.filter((assignment) => assignment.status.toLowerCase() === "proposed") ?? [];
  const reviewable = proposed.length > 0;
  const canAccept = run?.status.toLowerCase() === "succeeded";
  const solverErrorKey = run?.error_message ? allocationErrorKey(run.error_message) : null;

  const roomLabel = (id: number | null | undefined) => {
    if (!id) return t("proposal.unassigned");
    const room = roomById.get(id);
    return room ? t("proposal.room", { room: room.room_number }) : t("proposal.roomId", { id });
  };

  const handleAction = async () => {
    if (!run || !confirmation) return;
    const action = confirmation;
    setConfirmation(null);
    await (action === "accept" ? onAccept(run.run_id) : onReject(run.run_id));
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5" aria-labelledby="allocation-proposal-title">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{t("proposal.eyebrow")}</p>
          <h2 id="allocation-proposal-title" className="mt-1 text-lg font-semibold text-slate-900">{t("proposal.title")}</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-600">{t("proposal.description")}</p>
        </div>
        <div className="flex flex-col items-stretch gap-1 sm:items-end">
          <button
            type="button"
            onClick={() => void onRecalculate()}
            disabled={!canRecalculate || isRecalculating || isLoading || (reviewable && Boolean(run))}
            aria-describedby="allocation-recalculate-help"
            className="min-h-11 rounded-lg border border-brand-700 bg-brand-700 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-800 focus:outline-none focus:ring-2 focus:ring-brand-400 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isRecalculating ? t("proposal.recalculating") : t("proposal.recalculate")}
          </button>
          <span id="allocation-recalculate-help" className="max-w-xs text-xs text-slate-500 sm:text-right">
            {reviewable ? t("proposal.resolveBeforeRecalculate") : recalculationDisabledReason ?? t("proposal.recalculateHelp")}
          </span>
        </div>
      </div>

      {isLoading ? <p className="mt-4 text-sm text-slate-600" role="status">{t("proposal.loading")}</p> : null}
      {loadError && !isNotFound ? <p className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">{t("proposal.loadFailed", { message: loadError })}</p> : null}

      {!isLoading && !loadError && !isNotFound && !run ? <p className="mt-4 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-700">{t("proposal.empty")}</p> : null}
      {!isLoading && isNotFound ? <p className="mt-4 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-700">{t("proposal.empty")}</p> : null}

      {run ? (
        <div className="mt-4 space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full bg-slate-100 px-3 py-1 font-semibold text-slate-700">{t("proposal.run", { id: run.run_id })}</span>
            <span className={`rounded-full px-3 py-1 font-semibold ${run.status.toLowerCase() === "succeeded" ? "bg-emerald-100 text-emerald-800" : run.status.toLowerCase() === "failed" ? "bg-rose-100 text-rose-800" : "bg-amber-100 text-amber-900"}`}>
              {t(`proposal.status.${run.status.toLowerCase()}`, { defaultValue: run.status })}
            </span>
            <time className="text-slate-500" dateTime={run.created_at}>{new Intl.DateTimeFormat(i18n.language === "en" ? "en-US" : "es-AR", { dateStyle: "medium", timeStyle: "short" }).format(new Date(run.created_at))}</time>
          </div>

          {run.error_message ? <p className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">{solverErrorKey ? t(solverErrorKey) : run.error_message}</p> : null}

          {run.assignments.length === 0 ? (
            <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">{t("proposal.noAssignments")}</p>
          ) : (
            <div className="space-y-3">
              {run.assignments.map((assignment) => {
                const reservation = reservationById.get(assignment.reservation_id);
                const proposedRoom = assignment.room_id;
                const currentRoom = assignment.source_room_id;
                return (
                  <article key={assignment.id} className="rounded-xl border border-slate-200 p-3 sm:p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <p className="font-semibold text-slate-900">
                          {reservation?.confirmation_code || t("proposal.reservationId", { id: assignment.reservation_id })}
                        </p>
                        {reservation ? <p className="mt-1 text-xs text-slate-500">{reservation.check_in_date} — {reservation.check_out_date}</p> : null}
                        {!reservation && canReadReservations ? <p className="mt-1 text-xs text-slate-500">{t("proposal.reservationId", { id: assignment.reservation_id })}</p> : null}
                      </div>
                      <span className={`self-start rounded-full px-2.5 py-1 text-xs font-medium ${assignment.status.toLowerCase() === "proposed" ? "bg-amber-100 text-amber-900" : assignment.status.toLowerCase() === "applied" ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-700"}`}>
                        {t(`proposal.assignmentStatus.${assignment.status.toLowerCase()}`, { defaultValue: assignment.status })}
                      </span>
                    </div>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <div className="rounded-lg bg-slate-50 p-3">
                        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("proposal.currentRoom")}</p>
                        <p className="mt-1 text-sm font-semibold text-slate-900">{roomLabel(currentRoom)}</p>
                      </div>
                      <div className="rounded-lg bg-brand-50 p-3">
                        <p className="text-xs font-medium uppercase tracking-wide text-brand-800">{t("proposal.proposedRoom")}</p>
                        <p className="mt-1 text-sm font-semibold text-brand-900">{roomLabel(proposedRoom)}</p>
                      </div>
                    </div>
                    <p className="mt-3 text-sm text-slate-600"><span className="font-medium text-slate-700">{t("proposal.reason")}: </span>{assignmentReason(assignment, run, (key) => t(key))}</p>
                  </article>
                );
              })}
            </div>
          )}

          {reviewable ? (
            <div className="border-t border-slate-200 pt-4">
              {confirmation ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3" role="group" aria-label={t("proposal.confirmationLabel")}>
                  <p className="text-sm font-medium text-amber-950">{t(confirmation === "accept" ? "proposal.confirmAccept" : "proposal.confirmReject", { count: proposed.length })}</p>
                  <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                    <button type="button" onClick={() => void handleAction()} disabled={isAccepting || isRejecting} className="min-h-10 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 disabled:opacity-50">{t("proposal.confirmAction")}</button>
                    <button type="button" onClick={() => setConfirmation(null)} className="min-h-10 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2">{t("proposal.keepReviewing")}</button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
                  <button type="button" onClick={() => setConfirmation("reject")} disabled={isAccepting || isRejecting} className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 disabled:opacity-50">{t("proposal.reject")}</button>
                  <button type="button" onClick={() => setConfirmation("accept")} disabled={!canAccept || isAccepting || isRejecting} title={!canAccept ? t("proposal.acceptRequiresSuccess") : undefined} className="min-h-11 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50">{t("proposal.accept")}</button>
                </div>
              )}
              {!canAccept ? <p className="mt-2 text-xs text-slate-600">{t("proposal.acceptRequiresSuccess")}</p> : null}
            </div>
          ) : run.status.toLowerCase() === "succeeded" && run.assignments.length > 0 ? (
            <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">{t("proposal.reviewed")}</p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
