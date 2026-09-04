import { apiFetch, type SessionLike } from "./client";

export type CashSessionStatus = "open" | "closed" | "pending_approval";
export type CashMovementType = "income" | "expense" | "adjustment";

export type CashSession = {
  id: number;
  hotel_id: number;
  opened_by_user_id?: number | null;
  closed_by_user_id?: number | null;
  status: CashSessionStatus;
  opening_balance: number;
  currency_code: string;
  opened_at: string;
  closed_at?: string | null;
  notes?: string | null;
};

export type CashMovement = {
  id: number;
  hotel_id: number;
  session_id: number;
  reservation_id?: number | null;
  transaction_id?: number | null;
  recorded_by_user_id?: number | null;
  movement_type: CashMovementType;
  amount: number;
  description?: string | null;
  recorded_at: string;
};

export type CashCloseReport = {
  id: number;
  hotel_id: number;
  session_id: number;
  closed_by_user_id?: number | null;
  expected_balance: number;
  declared_balance: number;
  difference: number;
  difference_approved: boolean;
  approved_by_user_id?: number | null;
  successor_session_id?: number | null;
  custody_handoff?: CashCustodyHandoff | null;
  notes?: string | null;
  closed_at: string;
};

export type CashCustodyHandoff = {
  id: number;
  hotel_id: number;
  close_report_id: number;
  delivered_by_user_id?: number | null;
  received_by_user_id?: number | null;
  delivered_amount: number | string;
  status: "pending" | "confirmed";
  delivered_at: string;
  received_at?: string | null;
  notes?: string | null;
};

export type CashSessionSummary = {
  session_id: number;
  status: CashSessionStatus;
  currency_code: string;
  opening_balance: number;
  income_total: number;
  expense_total: number;
  adjustment_total: number;
  confirmed_cash_total: number;
  expected_balance: number;
  movements_count: number;
};

export type CashDailyPaymentMethod = {
  payment_method: string;
  gross_collected: number;
  refunds: number;
  net_collected: number;
  transaction_count: number;
};

export type CashDailyCollector = {
  collector_user_id?: number | null;
  collector_name: string;
  gross_collected: number;
  refunds: number;
  net_collected: number;
  transaction_count: number;
};

export type CashDailyEntry = {
  entry_type: "payment" | "manual_movement";
  actor_user_id?: number | null;
  actor_name: string;
  transaction_id?: number | null;
  cash_movement_id?: number | null;
  reservation_id?: number | null;
  amount: number;
  signed_amount: number;
  currency_code: string;
  payment_method?: string | null;
  transaction_type?: string | null;
  transaction_status?: string | null;
  movement_type?: string | null;
  occurred_at: string;
  description?: string | null;
  provider_code?: string | null;
};

export type CashDailySession = {
  session_id: number;
  status: CashSessionStatus;
  currency_code: string;
  opened_at: string;
  closed_at?: string | null;
  opened_by_user_id?: number | null;
  closed_by_user_id?: number | null;
  opening_balance: number;
  expected_balance: number;
  declared_balance?: number | null;
  difference?: number | null;
};

export type CashDailySummary = {
  hotel_id: number;
  report_date: string;
  timezone: string;
  currency_code: string;
  gross_collected: number;
  refunds: number;
  net_collected: number;
  physical_cash_net_collected: number;
  digital_net_collected: number;
  by_payment_method: CashDailyPaymentMethod[];
  by_collector: CashDailyCollector[];
  physical_cash: {
    opening_balance: number;
    income_total: number;
    expense_total: number;
    adjustment_total: number;
    expected_balance: number;
    declared_balance?: number | null;
    difference?: number | null;
    manual_income_total: number;
    manual_expense_total: number;
  };
  sessions: CashDailySession[];
  entries: CashDailyEntry[];
  entries_truncated: boolean;
  generated_at: string;
};

export type CashSessionOpenPayload = {
  opening_balance: number;
  currency_code?: string;
  notes?: string | null;
};

export type CashMovementPayload = {
  movement_type: CashMovementType;
  amount: number;
  description?: string | null;
  reservation_id?: number | null;
  transaction_id?: number | null;
};

export type CashSessionClosePayload = {
  counted_balance: number;
  notes?: string | null;
  approve_difference?: boolean;
};

export const listCashSessions = (session?: SessionLike) =>
  apiFetch<CashSession[]>("/api/cash-register/sessions", { session });

export const getLatestCashCloseReport = (session?: SessionLike) =>
  apiFetch<CashCloseReport | null>("/api/cash-register/close-reports/latest", { session });

export const openCashSession = (payload: CashSessionOpenPayload, session?: SessionLike) =>
  apiFetch<CashSession>("/api/cash-register/sessions", { method: "POST", data: payload, session });

export const listCashMovements = (sessionId: number, session?: SessionLike) =>
  apiFetch<CashMovement[]>(`/api/cash-register/sessions/${sessionId}/movements`, { session });

export const getCashSessionSummary = (sessionId: number, session?: SessionLike) =>
  apiFetch<CashSessionSummary>(`/api/cash-register/sessions/${sessionId}/summary`, { session });

export const getCashDailySummary = (date: string, session?: SessionLike) =>
  apiFetch<CashDailySummary>(`/api/cash-register/daily-summary?date=${encodeURIComponent(date)}`, { session });

export const addCashMovement = (sessionId: number, payload: CashMovementPayload, session?: SessionLike) =>
  apiFetch<CashMovement>(`/api/cash-register/sessions/${sessionId}/movements`, {
    method: "POST",
    data: payload,
    session
  });

export const closeCashSession = (sessionId: number, payload: CashSessionClosePayload, session?: SessionLike) =>
  apiFetch<CashCloseReport>(`/api/cash-register/sessions/${sessionId}/close`, {
    method: "POST",
    data: payload,
    session
  });

export const approveCashCloseDifference = (reportId: number, session?: SessionLike) =>
  apiFetch<CashCloseReport>(`/api/cash-register/close-reports/${reportId}/approve`, {
    method: "POST",
    session
  });

export const confirmCashCustody = (reportId: number, session?: SessionLike) =>
  apiFetch<CashCloseReport>(`/api/cash-register/close-reports/${reportId}/custody/confirm`, {
    method: "POST",
    session
  });
