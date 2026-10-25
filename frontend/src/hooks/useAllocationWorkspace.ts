import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  acceptAllocationRun,
  createAndPublishAllocationPolicy,
  getActiveAllocationPolicy,
  getAllocationRun,
  getLatestAllocationRun,
  rejectAllocationRun,
  setReservationReassignmentLock,
  type AllocationObjective,
  type AllocationPolicyVersionCreate
} from "../api/allocation";
import { triggerAllocationRecalculation } from "../api/allocationRuns";
import { hasValidSession } from "../api/client";
import { listReservations } from "../api/reservations";
import { listRooms } from "../api/rooms";
import { useSession } from "../state/session";

import { useEffectivePermissions } from "./usePermissions";
import { useGuardedMutation } from "./useGuardedMutation";

const allocationLatestKey = (hotelId: number | null) => ["allocation-run-latest", hotelId];
const allocationPolicyKey = (hotelId: number | null) => ["allocation-policy-active", hotelId];
const allocationReservationsKey = (hotelId: number | null, skip: number) => ["allocation-reservations-upcoming", hotelId, skip];
const allocationRoomsKey = (hotelId: number | null) => ["allocation-rooms", hotelId];

export function useAllocationWorkspace(reservationSkip: number) {
  const { session } = useSession();
  const permissions = useEffectivePermissions();
  const queryClient = useQueryClient();
  const sessionReady = hasValidSession(session);
  const canMoveReservations = permissions.hasPermission("reservation:move");
  const canReadReservations = permissions.hasPermission("reservation:read");
  const canReadRooms = permissions.hasPermission("room:read");
  const canManageConfig = permissions.hasPermission("config:manage");

  const latestRunQuery = useQuery({
    queryKey: allocationLatestKey(session.hotelId ?? null),
    queryFn: () => getLatestAllocationRun(session),
    enabled: sessionReady && canMoveReservations,
    staleTime: 15_000,
    retry: false
  });

  const policyQuery = useQuery({
    queryKey: allocationPolicyKey(session.hotelId ?? null),
    queryFn: () => getActiveAllocationPolicy(session),
    enabled: sessionReady && canManageConfig,
    staleTime: 60_000,
    retry: false
  });

  const reservationsQuery = useQuery({
    queryKey: allocationReservationsKey(session.hotelId ?? null, reservationSkip),
    queryFn: () => listReservations({ upcomingOnly: true, order: "check_in", limit: 51, skip: reservationSkip }, session),
    enabled: sessionReady && canReadReservations,
    staleTime: 15_000,
    retry: false
  });

  const roomsQuery = useQuery({
    queryKey: allocationRoomsKey(session.hotelId ?? null),
    queryFn: () => listRooms(session),
    enabled: sessionReady && canReadRooms,
    staleTime: 60_000,
    retry: false
  });

  const recalculateMutation = useGuardedMutation({
    mutationFn: async () => {
      const triggered = await triggerAllocationRecalculation({ apply: false }, session);
      return getAllocationRun(triggered.run_id, session);
    },
    onSuccess: async (run) => {
      queryClient.setQueryData(allocationLatestKey(session.hotelId ?? null), run);
      await queryClient.invalidateQueries({ queryKey: allocationLatestKey(session.hotelId ?? null) });
    }
  });

  const acceptMutation = useGuardedMutation({
    mutationFn: (runId: number) => acceptAllocationRun(runId, session),
    onSuccess: async (run) => {
      queryClient.setQueryData(allocationLatestKey(session.hotelId ?? null), run);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: allocationLatestKey(session.hotelId ?? null) }),
        queryClient.invalidateQueries({ queryKey: ["reservations", session.hotelId ?? null] }),
        queryClient.invalidateQueries({ queryKey: allocationReservationsKey(session.hotelId ?? null, reservationSkip) }),
        queryClient.invalidateQueries({ queryKey: allocationRoomsKey(session.hotelId ?? null) })
      ]);
    }
  });

  const rejectMutation = useGuardedMutation({
    mutationFn: (runId: number) => rejectAllocationRun(runId, session),
    onSuccess: async (run) => {
      queryClient.setQueryData(allocationLatestKey(session.hotelId ?? null), run);
      await queryClient.invalidateQueries({ queryKey: allocationLatestKey(session.hotelId ?? null) });
    }
  });

  const reassignmentLockMutation = useGuardedMutation({
    mutationFn: ({ reservationId, locked }: { reservationId: number; locked: boolean }) =>
      setReservationReassignmentLock(reservationId, locked, session),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["allocation-reservations-upcoming", session.hotelId ?? null] }),
        queryClient.invalidateQueries({ queryKey: ["reservations", session.hotelId ?? null] })
      ]);
    }
  });

  const savePolicyMutation = useGuardedMutation({
    mutationFn: (payload: AllocationPolicyVersionCreate) => createAndPublishAllocationPolicy(payload, session),
    onSuccess: async (version) => {
      const policy = policyQuery.data;
      if (policy) {
        queryClient.setQueryData(allocationPolicyKey(session.hotelId ?? null), {
          ...policy,
          version
        });
      }
      await queryClient.invalidateQueries({ queryKey: allocationPolicyKey(session.hotelId ?? null) });
    }
  });

  const savePolicy = (objective: AllocationObjective, revenueWeight: number) => {
    const activeVersion = policyQuery.data?.version;
    if (!activeVersion) return Promise.reject(new Error("No hay una política activa para actualizar."));

    const constraints = { ...activeVersion.constraints, optimization_objective: objective };
    const weights = { ...activeVersion.weights };
    if (objective === "combined") weights.combined_revenue_weight = revenueWeight;

    return savePolicyMutation.mutateAsync({
      constraints,
      weights,
      optimization_objective: objective,
      ...(objective === "combined" ? { combined_revenue_weight: revenueWeight } : {}),
      source: "manual",
      publish: true
    });
  };

  return {
    permissions,
    canMoveReservations,
    canReadReservations,
    canReadRooms,
    canManageConfig,
    latestRunQuery,
    policyQuery,
    reservationsQuery,
    roomsQuery,
    recalculateMutation,
    acceptMutation,
    rejectMutation,
    reassignmentLockMutation,
    savePolicyMutation,
    savePolicy
  };
}
