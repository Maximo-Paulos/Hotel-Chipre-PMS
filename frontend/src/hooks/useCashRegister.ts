import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

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
import { useSession } from "../state/session";

const cashSessionsKey = (hotelId: number | null) => ["cash-sessions", hotelId];
const cashMovementsKey = (hotelId: number | null, sessionId: number) => ["cash-movements", hotelId, sessionId];

const latestCloseReportKey = (hotelId: number | null) => ["cash-latest-close-report", hotelId];

/**
 * Payments created outside the cash screen still change the current cash
 * session. Keep the register views coherent when a reservation mutation is
 * the source of that movement.
 */
export function invalidateCashRegisterQueries(queryClient: QueryClient, hotelId: number | null) {
  queryClient.invalidateQueries({ queryKey: cashSessionsKey(hotelId) });
  queryClient.invalidateQueries({ queryKey: ["cash-movements", hotelId] });
  queryClient.invalidateQueries({ queryKey: ["cash-summary", hotelId] });
  queryClient.invalidateQueries({ queryKey: latestCloseReportKey(hotelId) });
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

  const invalidateSessions = () => {
    queryClient.invalidateQueries({ queryKey: cashSessionsKey(session.hotelId) });
    queryClient.invalidateQueries({ queryKey: latestCloseReportKey(session.hotelId) });
  };
  const invalidateMovements = () => {
    if (sessionId) {
      queryClient.invalidateQueries({ queryKey: cashMovementsKey(session.hotelId, sessionId) });
      queryClient.invalidateQueries({ queryKey: ["cash-summary", session.hotelId, sessionId] });
    }
  };

  const openSessionMutation = useMutation({
    mutationFn: (payload: CashSessionOpenPayload) => openCashSession(payload, session),
    onSuccess: invalidateSessions
  });

  const addMovementMutation = useMutation({
    mutationFn: (payload: CashMovementPayload) => addCashMovement(sessionId!, payload, session),
    onSuccess: () => {
      invalidateSessions();
      invalidateMovements();
    }
  });

  const closeSessionMutation = useMutation<CashCloseReport, unknown, CashSessionClosePayload>({
    mutationFn: (payload) => closeCashSession(sessionId!, payload, session),
    onSuccess: invalidateSessions
  });

  const approveDifferenceMutation = useMutation({
    mutationFn: (reportId: number) => approveCashCloseDifference(reportId, session),
    onSuccess: invalidateSessions
  });

  const confirmCustodyMutation = useMutation({
    mutationFn: (reportId: number) => confirmCashCustody(reportId, session),
    onSuccess: invalidateSessions
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
