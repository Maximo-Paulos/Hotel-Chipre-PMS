import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import {
  addCashMovement,
  approveCashCloseDifference,
  confirmCashCustody,
  closeCashSession,
  getLatestCashCloseReport,
  getCashSessionSummary,
  listCashMovements,
  listCashSessions,
  openCashSession,
  type CashCloseReport,
  type CashMovement,
  type CashMovementPayload,
  type CashSession,
  type CashSessionClosePayload,
  type CashSessionOpenPayload,
  type CashSessionSummary
} from "../api/cashRegister";
import { hasValidSession } from "../api/client";
import { refreshCashState } from "../api/queryInvalidation";
import { useSession } from "../state/session";

import { useGuardedMutation } from "./useGuardedMutation";

const cashSessionsKey = (hotelId: number | null) => ["cash-sessions", hotelId];
const cashMovementsKey = (hotelId: number | null, sessionId: number) => ["cash-movements", hotelId, sessionId];

const latestCloseReportKey = (hotelId: number | null) => ["cash-latest-close-report", hotelId];

/**
 * Payments created outside the cash screen still change the current cash
 * session. Keep the register views coherent when a reservation mutation is
 * the source of that movement.
 */
export function invalidateCashRegisterQueries(queryClient: QueryClient, hotelId: number | null) {
  return refreshCashState(queryClient, hotelId);
}

export function useCashSessions() {
  const { session } = useSession();
  return useQuery<CashSession[]>({
    queryKey: cashSessionsKey(session.hotelId),
    queryFn: () => listCashSessions(session),
    enabled: hasValidSession(session),
    staleTime: 15 * 1000
  });
}

export function useLatestCashCloseReport() {
  const { session } = useSession();
  return useQuery<CashCloseReport | null>({
    queryKey: latestCloseReportKey(session.hotelId),
    queryFn: () => getLatestCashCloseReport(session),
    enabled: hasValidSession(session),
    staleTime: 15 * 1000
  });
}

export function useCashMovements(sessionId?: number) {
  const { session } = useSession();
  return useQuery<CashMovement[]>({
    queryKey: sessionId ? cashMovementsKey(session.hotelId, sessionId) : ["cash-movements", "none"],
    queryFn: () => listCashMovements(sessionId!, session),
    enabled: Boolean(sessionId) && hasValidSession(session),
    staleTime: 15 * 1000
  });
}

export function useCashSessionSummary(sessionId?: number) {
  const { session } = useSession();
  return useQuery<CashSessionSummary>({
    queryKey: sessionId ? ["cash-summary", session.hotelId, sessionId] : ["cash-summary", "none"],
    queryFn: () => getCashSessionSummary(sessionId!, session),
    enabled: Boolean(sessionId) && hasValidSession(session),
    staleTime: 10 * 1000
  });
}

export function useCashRegisterMutations(sessionId?: number) {
  const queryClient = useQueryClient();
  const { session } = useSession();

  const invalidateSessions = () => refreshCashState(queryClient, session.hotelId);
  const invalidateMovements = () => refreshCashState(queryClient, session.hotelId);

  const openSessionMutation = useGuardedMutation({
    mutationFn: (payload: CashSessionOpenPayload) => openCashSession(payload, session),
    onSuccess: async () => invalidateSessions(),
    // A rejected "open" (e.g. someone else already opened the register on
    // another device) means our cached session list is stale, not just the
    // request. Without this, the UI keeps offering an "Abrir caja" button
    // that will fail again instead of switching to the real "already open"
    // state.
    onError: async () => invalidateSessions()
  });

  const addMovementMutation = useGuardedMutation({
    mutationFn: (payload: CashMovementPayload) => addCashMovement(sessionId!, payload, session),
    onSuccess: async () => invalidateMovements()
  });

  const closeSessionMutation = useGuardedMutation<CashCloseReport, unknown, CashSessionClosePayload>({
    mutationFn: (payload) => closeCashSession(sessionId!, payload, session),
    onSuccess: async () => invalidateSessions(),
    onError: async () => invalidateSessions()
  });

  const approveDifferenceMutation = useGuardedMutation({
    mutationFn: (reportId: number) => approveCashCloseDifference(reportId, session),
    onSuccess: async () => invalidateSessions(),
    onError: async () => invalidateSessions()
  });

  const confirmCustodyMutation = useGuardedMutation({
    mutationFn: (reportId: number) => confirmCashCustody(reportId, session),
    onSuccess: async () => invalidateSessions(),
    onError: async () => invalidateSessions()
  });

  return { openSessionMutation, addMovementMutation, closeSessionMutation, approveDifferenceMutation, confirmCustodyMutation };
}

export const cashSessionStatusLabel: Record<string, string> = {
  open: "Abierta",
  closed: "Cerrada",
  pending_approval: "Pendiente de aprobacion"
};

export const cashMovementTypeLabel: Record<string, string> = {
  income: "Ingreso",
  expense: "Egreso",
  adjustment: "Ajuste"
};
