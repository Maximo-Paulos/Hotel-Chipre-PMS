import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import {
  approveCashExpense,
  addCashMovement,
  approveCashCloseDifference,
  confirmCashCustody,
  closeCashSession,
  createCashExpense,
  listCashExpenses,
  getLatestCashCloseReport,
  getCashSessionSummary,
  getCashSessionCloseReport,
  getCashDailySummary,
  listCashMovements,
  listCashSessions,
  listPendingCashCloseReports,
  listPendingCashCustodyReports,
  openCashSession,
  rejectCashExpense,
  type CashExpense,
  type CashExpensePayload,
  type CashCloseReport,
  type CashCustodyReceiptPayload,
  type CashMovement,
  type CashMovementPayload,
  type CashSession,
  type CashSessionClosePayload,
  type CashSessionOpenPayload,
  type CashSessionSummary,
  type CashDailySummary
} from "../api/cashRegister";
import { hasValidSession } from "../api/client";
import { refreshCashState } from "../api/queryInvalidation";
import { useSession } from "../state/session";

import { useGuardedMutation } from "./useGuardedMutation";

const cashSessionsKey = (hotelId: number | null) => ["cash-sessions", hotelId];
const cashMovementsKey = (hotelId: number | null, sessionId: number) => ["cash-movements", hotelId, sessionId];

const latestCloseReportKey = (hotelId: number | null, currency?: string) => ["cash-latest-close-report", hotelId, currency ?? "all"];
const pendingCloseReportsKey = (hotelId: number | null) => ["cash-latest-close-report", hotelId, "pending"];
const pendingCashCustodyReportsKey = (hotelId: number | null) => ["cash-latest-close-report", hotelId, "custody-pending"];
const dailySummaryKey = (hotelId: number | null, date: string, currency?: string | null) => ["cash-daily-summary", hotelId, date, currency || "auto"];
const cashExpensesKey = (hotelId: number | null) => ["cash-expenses", hotelId];

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

export function useLatestCashCloseReport(options?: { enabled?: boolean; currency?: string }) {
  const { session } = useSession();
  return useQuery<CashCloseReport | null>({
    queryKey: latestCloseReportKey(session.hotelId, options?.currency),
    queryFn: () => getLatestCashCloseReport(session, options?.currency),
    enabled: hasValidSession(session) && (options?.enabled ?? true),
    staleTime: 15 * 1000
  });
}

export function usePendingCashCloseReports(options?: { enabled?: boolean }) {
  const { session } = useSession();
  return useQuery<CashCloseReport[]>({
    queryKey: pendingCloseReportsKey(session.hotelId),
    queryFn: () => listPendingCashCloseReports(session),
    enabled: hasValidSession(session) && (options?.enabled ?? true),
    staleTime: 10 * 1000
  });
}

export function usePendingCashCustodyReports(options?: { enabled?: boolean }) {
  const { session } = useSession();
  return useQuery<CashCloseReport[]>({
    queryKey: pendingCashCustodyReportsKey(session.hotelId),
    queryFn: () => listPendingCashCustodyReports(session),
    enabled: hasValidSession(session) && (options?.enabled ?? true),
    staleTime: 10 * 1000
  });
}

export function useCashSessionCloseReport(sessionId?: number) {
  const { session } = useSession();
  return useQuery<CashCloseReport | null>({
    queryKey: ["cash-latest-close-report", session.hotelId, "session", sessionId ?? null],
    queryFn: () => getCashSessionCloseReport(sessionId!, session),
    enabled: Boolean(sessionId) && hasValidSession(session),
    staleTime: 10 * 1000
  });
}

export function useCashDailySummary(reportDate: string, currency?: string | null) {
  const { session } = useSession();
  return useQuery<CashDailySummary>({
    queryKey: dailySummaryKey(session.hotelId, reportDate, currency),
    queryFn: () => getCashDailySummary(reportDate, session, currency),
    enabled: hasValidSession(session) && Boolean(reportDate),
    staleTime: 10 * 1000
  });
}

export function useCashExpenses(options?: { enabled?: boolean }) {
  const { session } = useSession();
  return useQuery<CashExpense[]>({
    queryKey: cashExpensesKey(session.hotelId),
    queryFn: () => listCashExpenses(session),
    enabled: hasValidSession(session) && (options?.enabled ?? true),
    staleTime: 10 * 1000
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
    onSuccess: () => {
      // The write has already committed. Reconcile active cash views in the
      // background so a slow report/list refresh does not keep the form in a
      // saving state or delay its success feedback.
      void invalidateMovements().catch(() => undefined);
    }
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

  const confirmCustodyMutation = useGuardedMutation<CashCloseReport, unknown, { reportId: number } & CashCustodyReceiptPayload>({
    mutationFn: ({ reportId, ...payload }) => confirmCashCustody(reportId, payload, session),
    onSuccess: async () => invalidateSessions(),
    onError: async () => invalidateSessions()
  });

  const createExpenseMutation = useGuardedMutation<CashExpense, Error, CashExpensePayload>({
    mutationFn: (payload) => createCashExpense(sessionId!, payload, session),
    onSuccess: async () => {
      await invalidateSessions();
      await queryClient.invalidateQueries({ queryKey: cashExpensesKey(session.hotelId) });
    },
    onError: async () => queryClient.invalidateQueries({ queryKey: cashExpensesKey(session.hotelId) })
  });

  const approveExpenseMutation = useGuardedMutation<CashExpense, Error, number>({
    mutationFn: (expenseId) => approveCashExpense(expenseId, session),
    onSuccess: async () => {
      await invalidateSessions();
      await queryClient.invalidateQueries({ queryKey: cashExpensesKey(session.hotelId) });
    },
    onError: async () => queryClient.invalidateQueries({ queryKey: cashExpensesKey(session.hotelId) })
  });

  const rejectExpenseMutation = useGuardedMutation<CashExpense, Error, { expenseId: number; reason: string }>({
    mutationFn: ({ expenseId, reason }) => rejectCashExpense(expenseId, reason, session),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: cashExpensesKey(session.hotelId) });
    },
    onError: async () => queryClient.invalidateQueries({ queryKey: cashExpensesKey(session.hotelId) })
  });

  return {
    openSessionMutation,
    addMovementMutation,
    closeSessionMutation,
    approveDifferenceMutation,
    confirmCustodyMutation,
    createExpenseMutation,
    approveExpenseMutation,
    rejectExpenseMutation
  };
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
