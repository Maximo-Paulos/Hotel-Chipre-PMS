import { apiFetch, buildAuthHeaders, buildUrl, type SessionLike } from "./client";

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
  group_payment_batch_id?: number | null;
  group_payment_total?: number | null;
  group_payment_reservation_count?: number | null;
  movement_type: CashMovementType;
  amount: number;
  description?: string | null;
  recorded_at: string;
};

export type CashCloseReport = {
  id: number;
  hotel_id: number;
  session_id: number;
  currency_code: string;
  closed_by_user_id?: number | null;
  closed_by_name?: string | null;
  expected_balance: number;
  declared_balance: number;
  difference: number;
  difference_approved: boolean;
  approved_by_user_id?: number | null;
  approved_by_name?: string | null;
  successor_session_id?: number | null;
  successor_opening_balance?: number | string | null;
  successor_float_declared_amount?: number | string | null;
  successor_float_declared_by_user_id?: number | null;
  successor_float_declared_by_name?: string | null;
  successor_float_declared_at?: string | null;
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
  by_collector: Array<{
    collector_user_id: number | null;
    collector_name: string;
    income_total: number;
    expense_total: number;
    adjustment_total: number;
    net_total: number;
    movement_count: number;
  }>;
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

export type CashDailyPriorReceipt = {
  transaction_id: number;
  reservation_id: number;
  confirmation_code: string;
  amount: number;
  currency_code: string;
  collected_on: string;
  prior_receipt_note: string;
  recorded_at: string;
  recorded_by_user_id?: number | null;
  recorded_by_name: string;
};

export type CashDailyPriorReceiptTotal = {
  currency_code: string;
  amount: number;
  transaction_count: number;
};

export type CashDailyEntry = {
  entry_type: "payment" | "manual_movement";
  actor_user_id?: number | null;
  actor_name: string;
  transaction_id?: number | null;
  group_payment_batch_id?: number | null;
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
  opened_by_name?: string | null;
  closed_by_name?: string | null;
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
    custody_delivered_total: number;
    custody_difference_total: number;
    expected_balance: number;
    declared_balance?: number | null;
    difference?: number | null;
    manual_income_total: number;
    manual_expense_total: number;
  };
  prior_receipts: CashDailyPriorReceipt[];
  prior_receipt_totals: CashDailyPriorReceiptTotal[];
  prior_receipts_truncated: boolean;
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

export type CashCustodyReceiptPayload = {
  successor_float_amount: number;
};

export type CashExpenseStatus = "pending" | "approved" | "rejected";

export type CashExpense = {
  id: number;
  hotel_id: number;
  session_id: number;
  amount: number;
  currency_code: string;
  category: string;
  vendor: string;
  description?: string | null;
  receipt_reference?: string | null;
  receipt_filename?: string | null;
  has_receipt_image: boolean;
  status: CashExpenseStatus;
  cash_movement_id?: number | null;
  recorded_by_user_id?: number | null;
  recorded_by_name?: string | null;
  approved_by_user_id?: number | null;
  approved_by_name?: string | null;
  rejected_by_user_id?: number | null;
  rejected_by_name?: string | null;
  rejection_reason?: string | null;
  created_at: string;
  approved_at?: string | null;
  rejected_at?: string | null;
};

export type CashExpensePayload = {
  amount: number;
  category: string;
  vendor: string;
  description?: string | null;
  receipt_reference?: string | null;
  receipt_image_base64?: string | null;
  receipt_filename?: string | null;
};

export const listCashSessions = (session?: SessionLike) =>
  apiFetch<CashSession[]>("/api/cash-register/sessions", { session });

export const getLatestCashCloseReport = (session?: SessionLike, currency?: string) =>
  apiFetch<CashCloseReport | null>(
    `/api/cash-register/close-reports/latest${currency ? `?currency=${encodeURIComponent(currency)}` : ""}`,
    { session }
  );

export const listPendingCashCloseReports = (session?: SessionLike) =>
  apiFetch<CashCloseReport[]>("/api/cash-register/close-reports/pending", { session });

export const listPendingCashCustodyReports = (session?: SessionLike) =>
  apiFetch<CashCloseReport[]>("/api/cash-register/close-reports/custody/pending", { session });

export const getCashSessionCloseReport = (sessionId: number, session?: SessionLike) =>
  apiFetch<CashCloseReport | null>(`/api/cash-register/sessions/${sessionId}/close-report`, { session });

export const openCashSession = (payload: CashSessionOpenPayload, session?: SessionLike) =>
  apiFetch<CashSession>("/api/cash-register/sessions", { method: "POST", data: payload, session });

export const listCashMovements = (sessionId: number, session?: SessionLike) =>
  apiFetch<CashMovement[]>(`/api/cash-register/sessions/${sessionId}/movements`, { session });

export const getCashSessionSummary = (sessionId: number, session?: SessionLike) =>
  apiFetch<CashSessionSummary>(`/api/cash-register/sessions/${sessionId}/summary`, { session });

export const getCashDailySummary = (date: string, session?: SessionLike, currency?: string | null) => {
  const query = new URLSearchParams({ date });
  if (currency) query.set("currency", currency);
  return apiFetch<CashDailySummary>(`/api/cash-register/daily-summary?${query.toString()}`, { session });
};

export const downloadCashLedgerCsv = async (
  fromDate: string,
  toDate: string,
  session?: SessionLike,
  currency?: string | null
): Promise<Blob> => {
  const query = new URLSearchParams({ from: fromDate, to: toDate });
  if (currency) query.set("currency", currency);
  const response = await fetch(buildUrl(`/api/cash-register/export.csv?${query.toString()}`), {
    headers: buildAuthHeaders(session),
    credentials: "include"
  });
  if (!response.ok) {
    let message = response.statusText || "No se pudo exportar la caja";
    try {
      const payload = await response.json() as { detail?: string };
      message = payload.detail || message;
    } catch {
      // Keep the safe HTTP status message when the response is not JSON.
    }
    throw new Error(message);
  }
  return response.blob();
};

export const downloadCashExpensesCsv = async (
  fromDate: string,
  toDate: string,
  session?: SessionLike
): Promise<Blob> => {
  const query = new URLSearchParams({ from: fromDate, to: toDate });
  const response = await fetch(buildUrl(`/api/cash-register/expenses/export.csv?${query.toString()}`), {
    headers: buildAuthHeaders(session),
    credentials: "include"
  });
  if (!response.ok) {
    let message = response.statusText || "No se pudo exportar gastos";
    try {
      const payload = await response.json() as { detail?: string };
      message = payload.detail || message;
    } catch {
      // Keep the safe HTTP status message when the response is not JSON.
    }
    throw new Error(message);
  }
  return response.blob();
};

export const listCashExpenses = (session?: SessionLike, expenseStatus?: CashExpenseStatus) => {
  const query = expenseStatus ? `?status=${encodeURIComponent(expenseStatus)}` : "";
  return apiFetch<CashExpense[]>(`/api/cash-register/expenses${query}`, { session });
};

export const createCashExpense = (sessionId: number, payload: CashExpensePayload, session?: SessionLike) =>
  apiFetch<CashExpense>(`/api/cash-register/sessions/${sessionId}/expenses`, {
    method: "POST",
    data: payload,
    session
  });

export const approveCashExpense = (expenseId: number, session?: SessionLike) =>
  apiFetch<CashExpense>(`/api/cash-register/expenses/${expenseId}/approve`, { method: "POST", session });

export const rejectCashExpense = (expenseId: number, reason: string, session?: SessionLike) =>
  apiFetch<CashExpense>(`/api/cash-register/expenses/${expenseId}/reject`, {
    method: "POST",
    data: { reason },
    session
  });

export const downloadCashExpenseReceipt = async (expenseId: number, session?: SessionLike): Promise<Blob> => {
  const response = await fetch(buildUrl(`/api/cash-register/expenses/${expenseId}/receipt`), {
    headers: buildAuthHeaders(session),
    credentials: "include"
  });
  if (!response.ok) throw new Error("No se pudo abrir el comprobante privado");
  return response.blob();
};

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

export const confirmCashCustody = (reportId: number, payload: CashCustodyReceiptPayload, session?: SessionLike) =>
  apiFetch<CashCloseReport>(`/api/cash-register/close-reports/${reportId}/custody/confirm`, {
    method: "POST",
    data: payload,
    session
  });
