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
  notes?: string | null;
  closed_at: string;
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

export const openCashSession = (payload: CashSessionOpenPayload, session?: SessionLike) =>
  apiFetch<CashSession>("/api/cash-register/sessions", { method: "POST", data: payload, session });

export const listCashMovements = (sessionId: number, session?: SessionLike) =>
  apiFetch<CashMovement[]>(`/api/cash-register/sessions/${sessionId}/movements`, { session });

export const getCashSessionSummary = (sessionId: number, session?: SessionLike) =>
  apiFetch<CashSessionSummary>(`/api/cash-register/sessions/${sessionId}/summary`, { session });

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
