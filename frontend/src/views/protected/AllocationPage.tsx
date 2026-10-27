import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { AllocationPolicySettings } from "../../components/AllocationPolicySettings";
import { AllocationProposalReview } from "../../components/AllocationProposalReview";
import { AllocationReservationLocks } from "../../components/AllocationReservationLocks";
import { ApiError } from "../../api/client";
import { useAllocationWorkspace } from "../../hooks/useAllocationWorkspace";

function messageFor(error: unknown, fallback: string, staleProposalMessage: string) {
  if (error instanceof Error && /reservation changed after this proposal|proposal.*stale/iu.test(error.message)) return staleProposalMessage;
  return error instanceof Error ? error.message : fallback;
}

export function AllocationPage() {
  const { t } = useTranslation("allocation");
  const [reservationPage, setReservationPage] = useState(0);
  const [actionError, setActionError] = useState<string | null>(null);
  const workspace = useAllocationWorkspace(reservationPage * 50);
  const {
    permissions,
    canMoveReservations,
    canReadReservations,
    canManageConfig,
    latestRunQuery,
    policyQuery,
    reservationsQuery,
    roomsQuery,
    recalculateMutation,
    acceptMutation,
    rejectMutation,
    reassignmentLockMutation
  } = workspace;

  const run = latestRunQuery.data;
  const hasPendingProposal = Boolean(run?.assignments.some((assignment) => assignment.status.toLowerCase() === "proposed"));
  const notFound = latestRunQuery.error instanceof ApiError && latestRunQuery.error.status === 404;

  const reservations = useMemo(() => reservationsQuery.data ?? [], [reservationsQuery.data]);
  const rooms = useMemo(() => roomsQuery.data ?? [], [roomsQuery.data]);
  const reservationById = useMemo(() => new Map(reservations.map((reservation) => [reservation.id, reservation])), [reservations]);
  const roomById = useMemo(() => new Map(rooms.map((room) => [room.id, room])), [rooms]);
  const visibleReservations = reservations.slice(0, 50);
  const staleProposalMessage = t("page.staleProposal");
  const latestRunError = latestRunQuery.error && !notFound ? messageFor(latestRunQuery.error, t("page.genericFailure"), staleProposalMessage) : null;
  const policyError = policyQuery.error ? messageFor(policyQuery.error, t("page.genericFailure"), staleProposalMessage) : null;
  const reservationError = reservationsQuery.error ? messageFor(reservationsQuery.error, t("page.genericFailure"), staleProposalMessage) : null;

  const runRecalculation = async () => {
    setActionError(null);
    try {
      await recalculateMutation.mutateAsync();
    } catch (error) {
      setActionError(messageFor(error, t("page.genericFailure"), staleProposalMessage));
    }
  };

  const acceptRun = async (runId: number, explicitlyApprovedLockedReservationIds: number[]) => {
    setActionError(null);
    try {
      await acceptMutation.mutateAsync({ runId, explicitlyApprovedLockedReservationIds });
    } catch (error) {
      setActionError(messageFor(error, t("page.genericFailure"), staleProposalMessage));
    }
  };

  const rejectRun = async (runId: number) => {
    setActionError(null);
    try {
      await rejectMutation.mutateAsync(runId);
    } catch (error) {
      setActionError(messageFor(error, t("page.genericFailure"), staleProposalMessage));
    }
  };

  const toggleLock = async (reservationId: number, locked: boolean) => {
    setActionError(null);
    try {
      await reassignmentLockMutation.mutateAsync({ reservationId, locked });
    } catch (error) {
      setActionError(messageFor(error, t("page.genericFailure"), staleProposalMessage));
    }
  };

  return (
    <div className="mx-auto w-full max-w-7xl space-y-5 pb-8">
      <header className="rounded-xl border border-brand-100 bg-gradient-to-br from-brand-50 to-white p-4 sm:p-6">
        <p className="text-xs font-semibold uppercase tracking-wide text-brand-700">{t("page.eyebrow")}</p>
        <div className="mt-1 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl">{t("page.title")}</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-700">{t("page.description")}</p>
          </div>
          <span className="self-start rounded-full border border-brand-200 bg-white px-3 py-1 text-xs font-semibold text-brand-800 sm:self-auto">{t("page.reviewBeforeApply")}</span>
        </div>
      </header>

      {actionError ? <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">{t("page.actionFailed", { message: actionError })}</div> : null}

      <AllocationProposalReview
        run={run}
        isLoading={latestRunQuery.isLoading}
        loadError={latestRunError}
        isNotFound={notFound}
        reservationById={reservationById}
        roomById={roomById}
        canReadReservations={canReadReservations}
        isRecalculating={recalculateMutation.isPending}
        isAccepting={acceptMutation.isPending}
        isRejecting={rejectMutation.isPending}
        canRecalculate={!hasPendingProposal && canMoveReservations}
        recalculationDisabledReason={
          hasPendingProposal
            ? t("proposal.resolveBeforeRecalculate")
            : null
        }
        onRecalculate={runRecalculation}
        onAccept={acceptRun}
        onReject={rejectRun}
      />

      {canReadReservations ? (
        <AllocationReservationLocks
          reservations={visibleReservations}
          roomsById={roomById}
          isLoading={reservationsQuery.isLoading}
          error={reservationError}
          canReadReservations={canReadReservations}
          canEditReservations={permissions.hasPermission("reservation:update")}
          isUpdating={reassignmentLockMutation.isPending}
          updatingReservationId={reassignmentLockMutation.variables?.reservationId ?? null}
          page={reservationPage}
          hasNextPage={reservations.length > 50}
          onPageChange={setReservationPage}
          onToggle={toggleLock}
        />
      ) : (
        <AllocationReservationLocks
          reservations={[]}
          roomsById={roomById}
          isLoading={false}
          error={null}
          canReadReservations={false}
          canEditReservations={permissions.hasPermission("reservation:update")}
          isUpdating={false}
          updatingReservationId={null}
          page={0}
          hasNextPage={false}
          onPageChange={setReservationPage}
          onToggle={toggleLock}
        />
      )}

      {canManageConfig ? (
        <AllocationPolicySettings
          policy={policyQuery.data}
          isLoading={policyQuery.isLoading}
          error={policyError}
        />
      ) : null}
    </div>
  );
}
