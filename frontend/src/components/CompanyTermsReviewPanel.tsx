import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../api/client";
import {
  getCompanyReservationTermsReview,
  reviewCompanyReservationTerms,
  type CompanyReservationTermsReviewAction
} from "../api/reservations";
import { queryKeys } from "../api/queryKeys";
import { useSession } from "../state/session";

type Props = {
  reservationId: number;
};

const termFieldKeys = [
  "payment_deferred",
  "deferred_days",
  "requires_voucher",
  "requires_signature",
  "base_price",
  "extra_person_nightly_surcharge"
] as const;

function termValue(value: unknown, t: (key: string) => string): string {
  if (typeof value === "boolean") return value ? t("drawer.companyTermsReview.yes") : t("drawer.companyTermsReview.no");
  if (value === null || value === undefined || value === "") return t("drawer.companyTermsReview.notSet");
  return String(value);
}

export function CompanyTermsReviewPanel({ reservationId }: Props) {
  const { t } = useTranslation("reservations");
  const { session } = useSession();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [action, setAction] = useState<CompanyReservationTermsReviewAction>("keep_snapshot");
  const [feedback, setFeedback] = useState<{ kind: "success" | "error"; message: string } | null>(null);
  const queryKey = queryKeys.companyReservationTerms(session.hotelId, reservationId);
  const reviewQuery = useQuery({
    queryKey,
    queryFn: ({ signal }) => getCompanyReservationTermsReview(reservationId, session, signal),
    enabled: Boolean(reservationId && session.hotelId),
    staleTime: 0,
    retry: false
  });
  const reviewMutation = useMutation({
    mutationFn: ({ decision, expectedFingerprint, decisionReason }: {
      decision: CompanyReservationTermsReviewAction;
      expectedFingerprint: string;
      decisionReason: string;
    }) => reviewCompanyReservationTerms(reservationId, {
      action: decision,
      reason: decisionReason,
      expected_config_fingerprint: expectedFingerprint,
      idempotency_key: crypto.randomUUID()
    }, session),
    onSuccess: async () => {
      setReason("");
      setFeedback({ kind: "success", message: t("drawer.companyTermsReview.saved") });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey }),
        queryClient.invalidateQueries({ queryKey: queryKeys.reservation(session.hotelId, reservationId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.reservations(session.hotelId) })
      ]);
    },
    onError: (error) => {
      setFeedback({
        kind: "error",
        message: error instanceof ApiError && error.status === 409
          ? t("drawer.companyTermsReview.stale")
          : t("drawer.companyTermsReview.saveFailed")
      });
    }
  });

  if (reviewQuery.isLoading) {
    return <section className="rounded-lg border border-indigo-200 bg-indigo-50/50 p-3" aria-busy="true">
      <p className="text-xs text-slate-600">{t("drawer.companyTermsReview.loading")}</p>
    </section>;
  }
  if (reviewQuery.isError || !reviewQuery.data) {
    return <section className="rounded-lg border border-rose-200 bg-rose-50 p-3" data-testid="company-terms-review-error">
      <p className="text-xs text-rose-800" role="alert">{t("drawer.companyTermsReview.loadFailed")}</p>
      <button
        type="button"
        onClick={() => void reviewQuery.refetch()}
        disabled={reviewQuery.isFetching}
        className="mt-2 min-h-10 rounded-md border border-rose-300 bg-white px-3 py-1 text-xs font-semibold text-rose-800 disabled:opacity-60"
      >{t("drawer.companyTermsReview.retry")}</button>
    </section>;
  }

  const review = reviewQuery.data;
  const snapshot = review.snapshot;
  const snapshotTerms = snapshot && typeof snapshot.terms === "object" && snapshot.terms !== null
    ? snapshot.terms as Record<string, unknown>
    : null;
  const currentTerms = review.current_terms ?? {};
  const changedFields = review.changed_fields.filter((field) => termFieldKeys.includes(field as typeof termFieldKeys[number]));
  const canKeepSnapshot = Boolean(snapshotTerms);
  const selectedAction: CompanyReservationTermsReviewAction = canKeepSnapshot ? action : "accept_current";

  return (
    <section
      className={`rounded-lg border p-3 ${review.needs_review ? "border-amber-300 bg-amber-50/70" : "border-indigo-200 bg-indigo-50/50"}`}
      data-testid="company-terms-review"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-indigo-900">{t("drawer.companyTermsReview.title")}</p>
          <p className={`mt-1 text-sm font-semibold ${review.needs_review ? "text-amber-950" : "text-slate-800"}`} role={review.needs_review ? "status" : undefined}>
            {review.needs_review
              ? t(snapshotTerms ? "drawer.companyTermsReview.changed" : "drawer.companyTermsReview.missingSnapshot")
              : t(`drawer.companyTermsReview.status.${review.status}`)}
          </p>
          {review.blocks_checkin ? <p className="mt-1 text-xs text-amber-900">{t("drawer.companyTermsReview.checkinBlocked")}</p> : null}
          {review.needs_review && !review.blocks_checkin ? <p className="mt-1 text-xs text-amber-900">{t("drawer.companyTermsReview.reviewNotBlocking")}</p> : null}
        </div>
        {review.needs_review ? <span className="rounded-full bg-amber-200 px-2 py-1 text-[11px] font-semibold text-amber-950">{t("drawer.companyTermsReview.pending")}</span> : null}
      </div>

      {review.needs_review ? (
        <>
          <p className="mt-2 text-xs text-slate-700">
            {snapshotTerms
              ? t("drawer.companyTermsReview.changeHint")
              : t("drawer.companyTermsReview.missingSnapshotHint")}
          </p>
          <dl className="mt-2 grid gap-2 sm:grid-cols-2">
            {(changedFields.length ? changedFields : [...termFieldKeys]).map((field) => (
              <div key={field} className="rounded-md border border-amber-100 bg-white px-2 py-1.5">
                <dt className="text-[11px] font-semibold text-slate-600">{t(`drawer.companyTermsReview.fields.${field}`)}</dt>
                <dd className="mt-0.5 text-xs text-slate-800">
                  {t("drawer.companyTermsReview.previous")}: {termValue(snapshotTerms?.[field], t)}
                  <span className="mx-1.5 text-slate-400">→</span>
                  {t("drawer.companyTermsReview.current")}: {termValue(currentTerms[field], t)}
                </dd>
              </div>
            ))}
          </dl>

          <fieldset className="mt-3 space-y-2" disabled={reviewMutation.isPending}>
            <legend className="text-xs font-semibold text-slate-700">{t("drawer.companyTermsReview.decisionTitle")}</legend>
            {canKeepSnapshot ? (
              <label className="flex cursor-pointer gap-2 rounded-md border border-slate-200 bg-white p-2 text-xs">
                <input type="radio" name={`company-terms-${reservationId}`} checked={selectedAction === "keep_snapshot"} onChange={() => setAction("keep_snapshot")} />
                <span><strong>{t("drawer.companyTermsReview.keepSnapshot")}</strong><span className="mt-0.5 block text-slate-600">{t("drawer.companyTermsReview.keepSnapshotHint")}</span></span>
              </label>
            ) : null}
            <label className="flex cursor-pointer gap-2 rounded-md border border-slate-200 bg-white p-2 text-xs">
              <input type="radio" name={`company-terms-${reservationId}`} checked={selectedAction === "accept_current"} onChange={() => setAction("accept_current")} />
              <span><strong>{t("drawer.companyTermsReview.acceptCurrent")}</strong><span className="mt-0.5 block text-slate-600">{t("drawer.companyTermsReview.acceptCurrentHint")}</span></span>
            </label>
          </fieldset>
          <label className="mt-3 block space-y-1 text-xs font-semibold text-slate-700">
            <span>{t("drawer.companyTermsReview.reasonLabel")}</span>
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              maxLength={1000}
              rows={2}
              required
              placeholder={t("drawer.companyTermsReview.reasonPlaceholder")}
              className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm font-normal"
            />
          </label>
          {feedback ? <p className={`mt-2 text-xs ${feedback.kind === "error" ? "text-rose-700" : "text-emerald-700"}`} role={feedback.kind === "error" ? "alert" : "status"}>{feedback.message}</p> : null}
          <div className="mt-2 flex justify-end">
            <button
              type="button"
              onClick={() => {
                if (!review.current_fingerprint) return;
                setFeedback(null);
                reviewMutation.mutate({
                  decision: selectedAction,
                  expectedFingerprint: review.current_fingerprint,
                  decisionReason: reason.trim()
                });
              }}
              disabled={!reason.trim() || !review.current_fingerprint || reviewMutation.isPending}
              className="min-h-10 rounded-md bg-indigo-700 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-800 disabled:cursor-not-allowed disabled:opacity-50"
            >{reviewMutation.isPending ? t("drawer.companyTermsReview.saving") : t("drawer.companyTermsReview.saveDecision")}</button>
          </div>
        </>
      ) : (
        <p className="mt-2 text-xs text-slate-600">{t("drawer.companyTermsReview.noPendingReview")}</p>
      )}
    </section>
  );
}
