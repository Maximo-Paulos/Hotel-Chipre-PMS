import React, { useEffect, useMemo, useState } from "react";

import {
  downloadCashExpenseReceipt,
  downloadCashLedgerCsv,
  type CashCloseReport,
  type CashDailyEntry,
  type CashMovement,
  type CashMovementPayload
} from "../../api/cashRegister";
import {
  cashMovementTypeLabel,
  cashSessionStatusLabel,
  useCashSessionCloseReport,
  useLatestCashCloseReport,
  usePendingCashCloseReports,
  usePendingCashCustodyReports,
  useCashMovements,
  useCashDailySummary,
  useCashRegisterMutations,
  useCashExpenses,
  useCashSessions,
  useCashSessionSummary
} from "../../hooks/useCashRegister";
import { useSession } from "../../state/session";
import { useEffectivePermissions } from "../../hooks/usePermissions";
import { useHotelConfig } from "../../hooks/useHotelConfig";
import { useCollaborativeResource } from "../../hooks/useCollaborativeResource";
import { formatHotelDateTime, formatHotelTime, todayIso } from "../../utils/date";

const emptyMovementForm: CashMovementPayload = {
  movement_type: "income",
  amount: 0,
  description: ""
};
const emptyDailyEntries: CashDailyEntry[] = [];

const money = (value?: number | string | null, currency = "ARS") =>
  Number(value ?? 0).toLocaleString("es-AR", { style: "currency", currency });

export function CashRegisterPage() {
  const { session } = useSession();
  const { hasPermission } = useEffectivePermissions();
  const hotelConfigQuery = useHotelConfig();
  const defaultCurrency = (hotelConfigQuery.data?.default_currency || "ARS").toUpperCase();
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [openingBalance, setOpeningBalance] = useState<number | null>(null);
  const [openingCurrency, setOpeningCurrency] = useState("ARS");
  const [openingNotes, setOpeningNotes] = useState("");
  const [movementForm, setMovementForm] = useState<CashMovementPayload>(emptyMovementForm);
  const [countedBalances, setCountedBalances] = useState<Record<number, number>>({});
  const [successorFloatAmounts, setSuccessorFloatAmounts] = useState<Record<number, string>>({});
  const [closeNotes, setCloseNotes] = useState("");
  const [approveOnClose, setApproveOnClose] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [cashActionErrors, setCashActionErrors] = useState<Record<string, string>>({});
  const [closeReport, setCloseReport] = useState<CashCloseReport | null>(null);
  const [reportDate, setReportDate] = useState(() => todayIso());
  const [reportCurrency, setReportCurrency] = useState("");
  const [exportFromDate, setExportFromDate] = useState(() => todayIso());
  const [exportToDate, setExportToDate] = useState(() => todayIso());
  const [expenseCategory, setExpenseCategory] = useState("");
  const [expenseVendor, setExpenseVendor] = useState("");
  const [expenseReceiptReference, setExpenseReceiptReference] = useState("");
  const [expenseReceiptImage, setExpenseReceiptImage] = useState<string | null>(null);
  const [expenseReceiptFilename, setExpenseReceiptFilename] = useState<string | null>(null);
  const [expenseRejectionReasons, setExpenseRejectionReasons] = useState<Record<number, string>>({});

  const setCashActionError = (key: string, error: unknown, fallback: string) => {
    setCashActionErrors((current) => ({
      ...current,
      [key]: error instanceof Error ? error.message : fallback
    }));
  };
  const dismissCashActionError = (key: string) => {
    setCashActionErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
  };

  const sessionsQuery = useCashSessions();
  const latestCloseReportQuery = useLatestCashCloseReport({ currency: openingCurrency });
  const pendingCloseReportsQuery = usePendingCashCloseReports();
  const canReceiveCustody = hasPermission("cash:custody:receive");
  const pendingCashCustodyReportsQuery = usePendingCashCustodyReports({ enabled: canReceiveCustody });
  const sessions = useMemo(() => sessionsQuery.data ?? [], [sessionsQuery.data]);
  const pendingCloseReports = useMemo(() => pendingCloseReportsQuery.data ?? [], [pendingCloseReportsQuery.data]);
  const pendingCashCustodyReports = useMemo(
    () => pendingCashCustodyReportsQuery.data ?? [],
    [pendingCashCustodyReportsQuery.data]
  );
  const dailySummaryQuery = useCashDailySummary(reportDate, reportCurrency || defaultCurrency);
  const canViewCash = hasPermission("cash:view");
  const canApproveCashExpenses = hasPermission("cash:expense_approve");
  const cashExpensesQuery = useCashExpenses({ enabled: canViewCash });
  const hotelTimeZone = dailySummaryQuery.data?.timezone ?? hotelConfigQuery.data?.hotel_timezone;
  const availableCurrencies = useMemo(
    () => Array.from(new Set([
      defaultCurrency, "ARS", "USD", "EUR", "BRL", "CLP", "UYU",
      ...sessions.map((item) => item.currency_code.toUpperCase()),
      ...(dailySummaryQuery.data?.prior_receipt_totals ?? []).map((item) => item.currency_code.toUpperCase())
    ])).sort(),
    [dailySummaryQuery.data?.prior_receipt_totals, defaultCurrency, sessions]
  );
  const openSessions = useMemo(() => sessions.filter((session) => session.status === "open"), [sessions]);
  useEffect(() => {
    setOpeningCurrency(defaultCurrency);
  }, [defaultCurrency]);
  const openSession = useMemo(
    () => openSessions.find((session) => session.currency_code.toUpperCase() === defaultCurrency) ?? openSessions[0] ?? null,
    [defaultCurrency, openSessions]
  );
  const openSessionForOpeningCurrency = useMemo(
    () => openSessions.find((session) => session.currency_code.toUpperCase() === openingCurrency) ?? null,
    [openSessions, openingCurrency]
  );
  const selectedSession = useMemo(
    () => sessions.find((session) => session.id === selectedSessionId) ?? openSession ?? sessions[0] ?? null,
    [openSession, selectedSessionId, sessions]
  );
  const countedBalance = selectedSession ? countedBalances[selectedSession.id] ?? 0 : 0;
  const movementFormErrorKey = `movement-form:${selectedSession?.id ?? "none"}`;
  const closeSessionErrorKey = `close-session:${selectedSession?.id ?? "none"}`;
  const cashNotesErrorKey = `notes:${selectedSession?.id ?? "none"}`;
  const selectedSessionCloseReportQuery = useCashSessionCloseReport(selectedSession?.id);
  const collaborativeCashSession = useCollaborativeResource({
    resourceType: "cash_session",
    resourceId: selectedSession?.id,
    initialValues: selectedSession ? { notes: selectedSession.notes ?? null } : null,
    enabled: Boolean(selectedSession && hasPermission("cash:operate"))
  });
  const movementsQuery = useCashMovements(selectedSession?.id);
  const summaryQuery = useCashSessionSummary(selectedSession?.id);
  const mutations = useCashRegisterMutations(selectedSession?.id);
  const movements = useMemo(() => movementsQuery.data ?? [], [movementsQuery.data]);
  const displayedMovements = useMemo(() => {
    const result: CashMovement[] = [];
    const groupPositions = new Map<number, number>();
    for (const movement of movements) {
      const batchId = movement.group_payment_batch_id;
      if (!batchId) {
        result.push(movement);
        continue;
      }
      const currentIndex = groupPositions.get(batchId);
      if (currentIndex === undefined) {
        const reservationCount = movement.group_payment_reservation_count ?? 1;
        result.push({
          ...movement,
          amount: Number(movement.group_payment_total ?? movement.amount),
          description: `Cobro grupal · ${reservationCount} reserva(s)`
        });
        groupPositions.set(batchId, result.length - 1);
      }
    }
    return result;
  }, [movements]);
  const dailyEntries = dailySummaryQuery.data?.entries ?? emptyDailyEntries;
  const displayedDailyEntries = useMemo<typeof dailyEntries>(() => {
    const result: typeof dailyEntries = [];
    const groups = new Map<number, (typeof dailyEntries)[number]>();
    for (const entry of dailyEntries) {
      const batchId = entry.group_payment_batch_id;
      if (!batchId || entry.entry_type !== "payment") {
        result.push(entry);
        continue;
      }
      const existing = groups.get(batchId);
      if (existing) {
        existing.amount += Number(entry.amount);
        existing.signed_amount += Number(entry.signed_amount);
        continue;
      }
      const grouped = {
        ...entry,
        amount: Number(entry.amount),
        signed_amount: Number(entry.signed_amount),
        transaction_id: null,
        reservation_id: null,
        description: "Cobro grupal · 1 reserva(s)"
      };
      groups.set(batchId, grouped);
    }
    for (const [batchId, entry] of groups) {
      const count = dailyEntries.filter((item) => item.group_payment_batch_id === batchId).length;
      entry.description = `Cobro grupal · ${count} reserva(s)`;
      result.push(entry);
    }
    return result.sort((left, right) => left.occurred_at.localeCompare(right.occurred_at));
  }, [dailyEntries]);
  const cashExpenses = useMemo(() => cashExpensesQuery.data ?? [], [cashExpensesQuery.data]);
  const latestCloseReport = latestCloseReportQuery.data;
  const selectedSessionCloseReport =
    closeReport?.session_id === selectedSession?.id
      ? closeReport
      : selectedSessionCloseReportQuery.data ?? null;
  const latestCloseReportForOpeningCurrency = latestCloseReport?.currency_code?.toUpperCase() === openingCurrency
    ? latestCloseReport
    : null;
  const successorNeedsApproval = pendingCloseReports.some(
    (report) => report.currency_code.toUpperCase() === openingCurrency
  ) && !openSessionForOpeningCurrency;
  const successorOpeningBalance = Number(latestCloseReportForOpeningCurrency?.successor_opening_balance ?? 0);
  const canApproveDifference = hasPermission("cash:approve_difference");
  const canOperateCash = hasPermission("cash:operate");
  const canAdjustCash = hasPermission("cash:adjustment_manage");
  const canRecordCashExpense = hasPermission("cash:expense");
  const canSubmitCashExpense = canOperateCash && canRecordCashExpense;

  // Authoritative figures come from the backend summary (same logic as the
  // arqueo), so the displayed "Esperado" always matches what the close computes.
  const summary = summaryQuery.data;
  const totals = useMemo(
    () => ({
      income: Number(summary?.income_total ?? 0),
      expense: Number(summary?.expense_total ?? 0),
      adjustment: Number(summary?.adjustment_total ?? 0)
    }),
    [summary]
  );

  const expectedBalance = Number(summary?.expected_balance ?? selectedSession?.opening_balance ?? 0);
  const currency = selectedSession?.currency_code ?? "ARS";
  const closeReportCurrency = selectedSessionCloseReport?.currency_code ?? currency;
  const busy =
    mutations.openSessionMutation.isPending ||
    mutations.addMovementMutation.isPending ||
    mutations.closeSessionMutation.isPending ||
    mutations.approveDifferenceMutation.isPending ||
    mutations.confirmCustodyMutation.isPending ||
    mutations.createExpenseMutation.isPending ||
    mutations.approveExpenseMutation.isPending ||
    mutations.rejectExpenseMutation.isPending;

  const handleOpenSession = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    setCloseReport(null);
    try {
      const session = await mutations.openSessionMutation.mutateAsync({
        opening_balance: Number(openingBalance ?? successorOpeningBalance),
        currency_code: openingCurrency,
        notes: openingNotes.trim() || null
      });
      setSelectedSessionId(session.id);
      setOpeningBalance(null);
      setOpeningNotes("");
      setCountedBalances((current) => ({ ...current, [session.id]: 0 }));
      setMessage("Caja abierta.");
    } catch (error) {
      setCashActionError(`open:${openingCurrency}`, error, "No se pudo abrir la caja.");
    }
  };

  const handleMovementSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (
      !canOperateCash ||
      (movementForm.movement_type === "expense" && !canSubmitCashExpense) ||
      (movementForm.movement_type === "adjustment" && !canAdjustCash)
    ) return;
    if (!selectedSession || selectedSession.status !== "open") return;
    setMessage(null);
    try {
      if (movementForm.movement_type === "expense") {
        await mutations.createExpenseMutation.mutateAsync({
          amount: Number(movementForm.amount),
          category: expenseCategory.trim(),
          vendor: expenseVendor.trim(),
          description: movementForm.description?.trim() || null,
          receipt_reference: expenseReceiptReference.trim() || null,
          receipt_image_base64: expenseReceiptImage,
          receipt_filename: expenseReceiptFilename
        });
        setMovementForm(emptyMovementForm);
        setExpenseCategory("");
        setExpenseVendor("");
        setExpenseReceiptReference("");
        setExpenseReceiptImage(null);
        setExpenseReceiptFilename(null);
        setMessage("Gasto pendiente de aprobación. Todavía no modifica el saldo de caja.");
        return;
      }
      await mutations.addMovementMutation.mutateAsync({
        ...movementForm,
        amount: Number(movementForm.amount),
        description: movementForm.description?.trim() || null
      });
      setMovementForm(emptyMovementForm);
      setMessage("Movimiento registrado.");
    } catch (error) {
      setCashActionError(movementFormErrorKey, error, "No se pudo registrar el movimiento.");
    }
  };

  const handleExpenseReceiptFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    setMessage(null);
    const file = event.target.files?.[0];
    if (!file) {
      setExpenseReceiptImage(null);
      setExpenseReceiptFilename(null);
      return;
    }
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 5 * 1024 * 1024) {
      setCashActionErrors((current) => ({
        ...current,
        [movementFormErrorKey]: "El comprobante debe ser una imagen JPEG, PNG o WEBP de hasta 5 MB."
      }));
      event.target.value = "";
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result !== "string") {
        setCashActionErrors((current) => ({ ...current, [movementFormErrorKey]: "No se pudo leer la imagen del comprobante." }));
        return;
      }
      setExpenseReceiptImage(reader.result);
      setExpenseReceiptFilename(file.name);
      setMessage(null);
    };
    reader.onerror = () => setCashActionErrors((current) => ({ ...current, [movementFormErrorKey]: "No se pudo leer la imagen del comprobante." }));
    reader.readAsDataURL(file);
  };

  const handleApproveExpense = async (expenseId: number) => {
    setMessage(null);
    try {
      await mutations.approveExpenseMutation.mutateAsync(expenseId);
      setMessage("Gasto aprobado y registrado en caja.");
    } catch (error) {
      setCashActionError(`expense:${expenseId}`, error, "No se pudo aprobar el gasto.");
    }
  };

  const handleRejectExpense = async (expenseId: number) => {
    const reason = (expenseRejectionReasons[expenseId] ?? "").trim();
    if (!reason) {
      setCashActionErrors((current) => ({ ...current, [`expense:${expenseId}`]: "Ingresá el motivo para rechazar el gasto." }));
      return;
    }
    setMessage(null);
    try {
      await mutations.rejectExpenseMutation.mutateAsync({ expenseId, reason });
      setExpenseRejectionReasons((current) => ({ ...current, [expenseId]: "" }));
      setMessage("Gasto rechazado. No se modificó la caja.");
    } catch (error) {
      setCashActionError(`expense:${expenseId}`, error, "No se pudo rechazar el gasto.");
    }
  };

  const handleExpenseReceiptDownload = async (expenseId: number) => {
    setMessage(null);
    try {
      const blob = await downloadCashExpenseReceipt(expenseId, session);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "comprobante-caja";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setCashActionError(`expense:${expenseId}`, error, "No se pudo abrir el comprobante.");
    }
  };

  const handleCloseSession = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedSession || selectedSession.status !== "open") return;
    setMessage(null);
    try {
      const report = await mutations.closeSessionMutation.mutateAsync({
        counted_balance: Number(countedBalance),
        notes: closeNotes.trim() || null,
        approve_difference: approveOnClose
      });
      setCloseReport(report);
      setSelectedSessionId(report.session_id);
      setCountedBalances((current) => ({ ...current, [report.session_id]: 0 }));
      setCloseNotes("");
      setApproveOnClose(false);
      setMessage("Caja cerrada.");
    } catch (error) {
      setCashActionError(closeSessionErrorKey, error, "No se pudo cerrar la caja.");
    }
  };

  const handleApproveDifference = async (reportId?: number, errorScope = "selected") => {
    const reportToApprove = reportId
      ? pendingCloseReports.find((report) => report.id === reportId) ??
        (selectedSessionCloseReport?.id === reportId ? selectedSessionCloseReport : null) ??
        (closeReport?.id === reportId ? closeReport : null) ??
        (latestCloseReport?.id === reportId ? latestCloseReport : null)
      : selectedSessionCloseReport ?? closeReport ?? latestCloseReport;
    if (!reportToApprove) return;
    setMessage(null);
    try {
      const approved = await mutations.approveDifferenceMutation.mutateAsync(reportToApprove.id);
      setCloseReport(approved);
      setSelectedSessionId(approved.session_id);
      setMessage("Diferencia aprobada.");
    } catch (error) {
      setCashActionError(`difference:${errorScope}:${reportToApprove.id}`, error, "No se pudo aprobar la diferencia.");
    }
  };

  const handleConfirmCustody = async (reportToConfirm: CashCloseReport, errorScope = "selected") => {
    setMessage(null);
    const floatAmount = Number(successorFloatAmounts[reportToConfirm.id] ?? "0");
    try {
      const confirmed = await mutations.confirmCustodyMutation.mutateAsync({
        reportId: reportToConfirm.id,
        successor_float_amount: floatAmount
      });
      setCloseReport(confirmed);
      setMessage(`Recepción confirmada. Fondo de cambio para la sucesora: ${money(floatAmount, reportToConfirm.currency_code)}.`);
    } catch (error) {
      setCashActionError(`custody:${errorScope}:${reportToConfirm.id}`, error, "No se pudo confirmar la custodia.");
    }
  };

  const handleCashNotesSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    if (!selectedSession || !collaborativeCashSession.isDirty) return;
    if (Object.keys(collaborativeCashSession.conflicts).length > 0) {
      setCashActionErrors((current) => ({ ...current, [cashNotesErrorKey]: "Hay un conflicto en las notas de caja. Elegí qué valor conservar." }));
      return;
    }
    try {
      await collaborativeCashSession.save();
      setMessage("Notas de caja actualizadas.");
    } catch (error) {
      setCashActionError(cashNotesErrorKey, error, "No se pudieron guardar las notas de caja.");
    }
  };

  const handleExport = async () => {
    setMessage(null);
    if (!exportFromDate || !exportToDate || exportToDate < exportFromDate) {
      setCashActionErrors((current) => ({ ...current, export: "Elegí un rango válido para exportar." }));
      return;
    }
    try {
      const blob = await downloadCashLedgerCsv(
        exportFromDate,
        exportToDate,
        session,
        reportCurrency || dailySummaryQuery.data?.currency_code
      );
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `caja-${exportFromDate}-${exportToDate}.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setMessage("Exportación de caja descargada.");
    } catch (error) {
      setCashActionError("export", error, "No se pudo exportar la caja.");
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
          <h1 className="text-balance text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">Caja</h1>
          <p className="text-sm text-slate-600">Apertura, movimientos, cierre de arqueo y aprobación de diferencias.</p>
        </div>
        {sessionsQuery.isFetching && <p className="text-xs text-slate-500">Actualizando caja...</p>}
      </header>

      {message ? <div role="status" aria-live="polite" className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">{message}</div> : null}

      <section className="space-y-4 rounded-xl border border-brand-100 bg-brand-50/40 p-5 shadow-sm" data-testid="cash-daily-summary">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-brand-700">Control diario</p>
            <h2 className="text-xl font-semibold text-slate-900">Caja diaria</h2>
            <p className="text-sm text-slate-600">Día calendario local del hotel: cobros confirmados, devoluciones y caja física.</p>
          </div>
          <label className="space-y-1 text-sm font-semibold text-slate-700">
            <span>Fecha</span>
            <input
              type="date"
              value={reportDate}
              onChange={(event) => setReportDate(event.target.value)}
              className="block rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal"
              data-testid="cash-daily-date"
            />
          </label>
          <label className="space-y-1 text-sm font-semibold text-slate-700">
            <span>Moneda</span>
            <select
              value={reportCurrency || defaultCurrency}
              onChange={(event) => setReportCurrency(event.target.value)}
              className="block rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal"
              aria-describedby="cash-daily-currency-help"
            >
              {availableCurrencies.map((currencyCode) => (
                <option key={currencyCode} value={currencyCode}>
                  {currencyCode}{currencyCode === defaultCurrency ? " · moneda del hotel" : ""}
                </option>
              ))}
            </select>
            <span id="cash-daily-currency-help" className="block max-w-48 text-xs font-normal text-slate-500">
              Usa la moneda del hotel por defecto. No se convierten ni mezclan importes entre monedas.
            </span>
          </label>
          <label className="space-y-1 text-sm font-semibold text-slate-700">
            <span>Exportar desde</span>
            <input
              type="date"
              value={exportFromDate}
              onChange={(event) => setExportFromDate(event.target.value)}
              className="block rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal"
              data-testid="cash-export-from"
            />
          </label>
          <label className="space-y-1 text-sm font-semibold text-slate-700">
            <span>Exportar hasta</span>
            <input
              type="date"
              value={exportToDate}
              onChange={(event) => setExportToDate(event.target.value)}
              min={exportFromDate}
              className="block rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal"
              data-testid="cash-export-to"
            />
          </label>
          <button
            type="button"
            onClick={() => void handleExport()}
            disabled={dailySummaryQuery.isLoading || dailySummaryQuery.isError || !hasPermission("cash:view") || !exportFromDate || !exportToDate || exportToDate < exportFromDate}
            className="rounded-lg border border-brand-200 bg-white px-3 py-2 text-sm font-semibold text-brand-700 hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Exportar CSV
          </button>
          <div className="basis-full">
            <PersistentActionError
              message={cashActionErrors.export}
              onClose={() => dismissCashActionError("export")}
            />
          </div>
        </div>
        {dailySummaryQuery.isLoading ? <p className="text-sm text-slate-600">Cargando resumen diario...</p> : null}
        {dailySummaryQuery.isError ? <p className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">No se pudo cargar el resumen diario: {(dailySummaryQuery.error as Error).message}</p> : null}
        {dailySummaryQuery.data ? (
          <>
            <div className="grid gap-3 sm:grid-cols-4">
              <Metric label="Cobrado" value={money(dailySummaryQuery.data.gross_collected, dailySummaryQuery.data.currency_code)} />
              <Metric label="Devoluciones" value={money(dailySummaryQuery.data.refunds, dailySummaryQuery.data.currency_code)} />
              <Metric label="Neto" value={money(dailySummaryQuery.data.net_collected, dailySummaryQuery.data.currency_code)} />
              <Metric label="Efectivo neto" value={money(dailySummaryQuery.data.physical_cash_net_collected, dailySummaryQuery.data.currency_code)} />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                <div className="border-b border-slate-200 px-4 py-3">
                  <h3 className="font-semibold text-slate-900">Por medio de pago</h3>
                  <p className="text-xs text-slate-500">Pendientes y fallidos quedan fuera.</p>
                </div>
                <div className="divide-y divide-slate-100">
                  {dailySummaryQuery.data.by_payment_method.length === 0 ? <p className="px-4 py-3 text-sm text-slate-500">Sin cobros confirmados.</p> : dailySummaryQuery.data.by_payment_method.map((item) => (
                    <div key={item.payment_method} className="flex items-center justify-between px-4 py-3 text-sm">
                      <span className="font-medium text-slate-700">{paymentMethodLabel(item.payment_method)}</span>
                      <span className="font-semibold text-slate-900">{money(item.net_collected, dailySummaryQuery.data?.currency_code)}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                <div className="border-b border-slate-200 px-4 py-3">
                  <h3 className="font-semibold text-slate-900">Caja física</h3>
                  <p className="text-xs text-slate-500">Esperado = apertura/fondos + ingresos − egresos + ajustes + diferencias de arqueo − entregas de efectivo. El fondo de la caja sucesora ya está incluido en la apertura. Los pagos externos no se suman a la caja.</p>
                </div>
                <div className="grid grid-cols-2 gap-3 px-4 py-3 text-sm">
                  <SummaryLine label="Apertura" value={money(dailySummaryQuery.data.physical_cash.opening_balance, dailySummaryQuery.data.currency_code)} />
                  <SummaryLine label="Ingresos" value={money(dailySummaryQuery.data.physical_cash.income_total, dailySummaryQuery.data.currency_code)} />
                  <SummaryLine label="Egresos" value={money(dailySummaryQuery.data.physical_cash.expense_total, dailySummaryQuery.data.currency_code)} />
                  <SummaryLine label="Ajustes netos" value={money(dailySummaryQuery.data.physical_cash.adjustment_total, dailySummaryQuery.data.currency_code)} />
                  <SummaryLine label="Diferencias de arqueo" value={money(dailySummaryQuery.data.physical_cash.custody_difference_total, dailySummaryQuery.data.currency_code)} />
                  <SummaryLine label="Entregado al cerrar caja" value={money(dailySummaryQuery.data.physical_cash.custody_delivered_total, dailySummaryQuery.data.currency_code)} />
                  <SummaryLine label="Esperado" value={money(dailySummaryQuery.data.physical_cash.expected_balance, dailySummaryQuery.data.currency_code)} />
                  <SummaryLine label="Manual +" value={money(dailySummaryQuery.data.physical_cash.manual_income_total, dailySummaryQuery.data.currency_code)} />
                  <SummaryLine label="Manual -" value={money(dailySummaryQuery.data.physical_cash.manual_expense_total, dailySummaryQuery.data.currency_code)} />
                  <SummaryLine label="Diferencia" value={money(dailySummaryQuery.data.physical_cash.difference, dailySummaryQuery.data.currency_code)} />
                </div>
              </div>
            </div>
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white" data-testid="cash-shift-reconciliation">
              <div className="border-b border-slate-200 px-4 py-3">
                <h3 className="font-semibold text-slate-900">Conciliación por turno</h3>
                <p className="text-xs text-slate-500">Cada turno muestra apertura, movimientos, esperado, contado y diferencia por separado.</p>
              </div>
              <table className="min-w-full text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Turno</th>
                    <th className="px-4 py-3">Apertura</th>
                    <th className="px-4 py-3">Cierre</th>
                    <th className="px-4 py-3">Saldo inicial</th>
                    <th className="px-4 py-3">Esperado</th>
                    <th className="px-4 py-3">Contado</th>
                    <th className="px-4 py-3">Diferencia</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {dailySummaryQuery.data.sessions.length === 0 ? (
                    <tr><td colSpan={7} className="px-4 py-4 text-slate-500">No hay turnos que conciliar en la fecha seleccionada.</td></tr>
                  ) : dailySummaryQuery.data.sessions.map((shift) => (
                    <tr key={shift.session_id}>
                      <td className="whitespace-nowrap px-4 py-3 font-semibold text-slate-800">#{shift.session_id} · {cashSessionStatusLabel[shift.status] ?? shift.status}</td>
                      <td className="min-w-48 px-4 py-3 text-slate-600">
                        <span className="block">{formatHotelDateTime(shift.opened_at, hotelTimeZone)}</span>
                        <span className="text-xs text-slate-500">{shift.opened_by_name ?? "Usuario no disponible"}</span>
                      </td>
                      <td className="min-w-48 px-4 py-3 text-slate-600">
                        {shift.closed_at ? <><span className="block">{formatHotelDateTime(shift.closed_at, hotelTimeZone)}</span><span className="text-xs text-slate-500">{shift.closed_by_name ?? "Usuario no disponible"}</span></> : "En curso"}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3">{money(shift.opening_balance, shift.currency_code)}</td>
                      <td className="whitespace-nowrap px-4 py-3 font-semibold">{money(shift.expected_balance, shift.currency_code)}</td>
                      <td className="whitespace-nowrap px-4 py-3">{shift.declared_balance == null ? "—" : money(shift.declared_balance, shift.currency_code)}</td>
                      <td className={`whitespace-nowrap px-4 py-3 font-semibold ${Number(shift.difference ?? 0) === 0 ? "text-slate-700" : "text-amber-800"}`}>
                        {shift.difference == null ? "—" : money(shift.difference, shift.currency_code)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="overflow-hidden rounded-lg border border-amber-200 bg-amber-50/50" data-testid="cash-prior-receipts">
              <div className="border-b border-amber-200 px-4 py-3">
                <h3 className="font-semibold text-slate-900">Cobros previos</h3>
                <p className="text-xs text-slate-600">
                  Cobros ingresados con su fecha real. No se suman al esperado ni al cobrado del día; conciliá la custodia física por separado.
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {dailySummaryQuery.data.prior_receipt_totals.map((total) => (
                    <span key={total.currency_code} className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-800">
                      {total.transaction_count} cobro(s) · {money(total.amount, total.currency_code)}
                    </span>
                  ))}
                  {dailySummaryQuery.data.prior_receipt_totals.length === 0 ? (
                    <span className="text-xs text-slate-500">Sin cobros previos registrados.</span>
                  ) : null}
                </div>
              </div>
              {dailySummaryQuery.data.prior_receipts.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-left text-sm">
                    <thead className="bg-white/70 text-xs uppercase tracking-wide text-slate-500">
                      <tr>
                        <th className="px-4 py-3">Fecha cobrada</th>
                        <th className="px-4 py-3">Reserva</th>
                        <th className="px-4 py-3">Importe</th>
                        <th className="px-4 py-3">Motivo / referencia</th>
                        <th className="px-4 py-3">Registrado por</th>
                        <th className="px-4 py-3">Cargado el</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-amber-100">
                      {dailySummaryQuery.data.prior_receipts.map((receipt) => (
                        <tr key={receipt.transaction_id}>
                          <td className="whitespace-nowrap px-4 py-3">{new Date(`${receipt.collected_on}T12:00:00`).toLocaleDateString("es-AR")}</td>
                          <td className="px-4 py-3 font-medium text-slate-800">{receipt.confirmation_code}</td>
                          <td className="whitespace-nowrap px-4 py-3 font-semibold">{money(receipt.amount, receipt.currency_code)}</td>
                          <td className="max-w-sm px-4 py-3 text-slate-600">{receipt.prior_receipt_note}</td>
                          <td className="px-4 py-3 text-slate-600">{receipt.recorded_by_name}</td>
                          <td className="whitespace-nowrap px-4 py-3 text-slate-500">{formatHotelDateTime(receipt.recorded_at, hotelTimeZone)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
              {dailySummaryQuery.data.prior_receipts_truncated ? (
                <p className="px-4 py-3 text-xs text-amber-900">Se muestran los primeros 500 registros; los totales incluyen todos los cobros previos.</p>
              ) : null}
            </div>
            <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
              <div className="border-b border-slate-200 px-4 py-3">
                <h3 className="font-semibold text-slate-900">Resumen por cobrador</h3>
                <p className="text-xs text-slate-500">Cobros y devoluciones confirmados atribuidos a cada persona o proveedor.</p>
              </div>
              <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
                {dailySummaryQuery.data.by_collector.length === 0 ? (
                  <p className="text-sm text-slate-500">Sin cobradores en la fecha seleccionada.</p>
                ) : (
                  dailySummaryQuery.data.by_collector.map((collector) => (
                    <div key={`${collector.collector_user_id ?? "system"}-${collector.collector_name}`} className="rounded-lg bg-slate-50 p-3">
                      <p className="truncate text-sm font-semibold text-slate-800">{collector.collector_name}</p>
                      <p className="mt-1 text-xs text-slate-500">{collector.transaction_count} operación(es)</p>
                      <p className="mt-1 font-semibold text-slate-900">{money(collector.net_collected, dailySummaryQuery.data.currency_code)}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <div className="border-b border-slate-200 px-4 py-3">
                <h3 className="font-semibold text-slate-900">Detalle por cobrador</h3>
                <p className="text-xs text-slate-500">Quién cobró, por qué medio, reserva, devolución y hora.</p>
              </div>
              <table className="min-w-full text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                  <tr><th className="px-4 py-3">Cobrador</th><th className="px-4 py-3">Medio</th><th className="px-4 py-3">Reserva</th><th className="px-4 py-3">Operación</th><th className="px-4 py-3">Importe</th><th className="px-4 py-3">Hora</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {displayedDailyEntries.length === 0 ? <tr><td colSpan={6} className="px-4 py-4 text-slate-500">Sin movimientos en la fecha seleccionada.</td></tr> : displayedDailyEntries.map((entry) => (
                    <tr
                      key={`${entry.entry_type}-${entry.group_payment_batch_id ?? entry.transaction_id ?? entry.cash_movement_id}`}
                      data-testid={entry.group_payment_batch_id ? `group-payment-cash-entry-${entry.group_payment_batch_id}` : undefined}
                    >
                      <td className="px-4 py-3 font-medium text-slate-800">{entry.actor_name}</td>
                      <td className="px-4 py-3 text-slate-600">{entry.payment_method ? paymentMethodLabel(entry.payment_method) : "Caja física"}</td>
                      <td className="px-4 py-3 text-slate-600">{entry.reservation_id ? `#${entry.reservation_id}` : "-"}</td>
                      <td className="px-4 py-3 text-slate-600">{entry.entry_type === "manual_movement" ? movementLabel(entry.movement_type) : entry.transaction_type === "refund" ? "Devolución" : "Cobro"}</td>
                      <td className={`px-4 py-3 font-semibold ${entry.signed_amount < 0 ? "text-rose-700" : "text-slate-900"}`}>{money(entry.signed_amount, entry.currency_code)}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-slate-500">{formatHotelTime(entry.occurred_at, hotelTimeZone)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {dailySummaryQuery.data.entries_truncated ? <p className="px-4 py-3 text-xs text-amber-700">Se muestran los primeros 500 movimientos; el ledger conserva el detalle completo.</p> : null}
            </div>
          </>
        ) : null}
      </section>

      {pendingCloseReports.length > 0 ? (
        <section className="space-y-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950" data-testid="cash-pending-approvals">
          <div>
            <h2 className="font-semibold">Diferencias de caja pendientes</h2>
            <p className="text-amber-900">El turno sucesor puede seguir operando. Revisá cada arqueo pendiente y aprobalo con MFA.</p>
          </div>
          <ul className="divide-y divide-amber-200">
            {pendingCloseReports.map((report) => (
              <li key={report.id} className="grid gap-2 py-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                <span>
                  Caja #{report.session_id} · diferencia {money(report.difference, report.currency_code || currency)}
                </span>
                {canApproveDifference ? (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void handleApproveDifference(report.id, "pending")}
                    className="rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm font-semibold text-amber-900 hover:bg-amber-100 disabled:opacity-60"
                  >
                    Aprobar diferencia
                  </button>
                ) : null}
                <div className="sm:col-span-2">
                  <PersistentActionError
                    message={cashActionErrors[`difference:pending:${report.id}`]}
                    onClose={() => dismissCashActionError(`difference:pending:${report.id}`)}
                  />
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {canReceiveCustody && pendingCashCustodyReports.length > 0 ? (
        <section
          className="space-y-3 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-950"
          data-testid="cash-pending-custodies"
        >
          <div>
            <h2 className="font-semibold">Custodias pendientes de recepción</h2>
            <p className="text-sky-900">Confirmá la recepción después de cotejar el efectivo entregado.</p>
          </div>
          <ul className="divide-y divide-sky-200">
            {pendingCashCustodyReports.map((report) => (
              <li key={report.id} className="grid gap-2 py-3 sm:grid-cols-[minmax(0,1fr)_220px_auto] sm:items-end">
                <span className="sm:pb-2">
                  Caja #{report.session_id} · {money(report.custody_handoff?.delivered_amount, report.currency_code || currency)} entregados
                </span>
                <label className="space-y-1 text-xs">
                  <span className="text-sky-900">Efectivo que dejo como cambio en la sucesora</span>
                  <input
                    type="number"
                    min={0}
                    max={9999999999.99}
                    step="0.01"
                    value={successorFloatAmounts[report.id] ?? "0"}
                    onChange={(event) => setSuccessorFloatAmounts((current) => ({ ...current, [report.id]: event.target.value }))}
                    className="w-full rounded-lg border border-sky-300 bg-white px-3 py-2 text-sm"
                    aria-label={`Cambio para caja sucesora de caja ${report.session_id}`}
                  />
                </label>
                <div className="space-y-1">
                  <button
                    type="button"
                    disabled={busy || Number(successorFloatAmounts[report.id] ?? "0") < 0 || Number(successorFloatAmounts[report.id] ?? "0") > 9999999999.99}
                    onClick={() => void handleConfirmCustody(report, "pending")}
                    className="rounded-lg border border-sky-300 bg-white px-3 py-2 text-sm font-semibold text-sky-900 hover:bg-sky-100 disabled:opacity-60"
                  >
                    Confirmar custodia y cambio
                  </button>
                  <PersistentActionError
                    message={cashActionErrors[`custody:pending:${report.id}`]}
                    onClose={() => dismissCashActionError(`custody:pending:${report.id}`)}
                  />
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-4">
        <Metric label="Saldo inicial" value={money(selectedSession?.opening_balance, currency)} />
        <Metric label="Ingresos" value={money(totals.income, currency)} />
        <Metric label="Egresos" value={money(totals.expense, currency)} />
        <Metric label="Esperado" value={money(expectedBalance, currency)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[340px_minmax(0,1fr)]">
        <section className="space-y-4">
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 px-4 py-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Sesiones</p>
              <h2 className="text-lg font-semibold text-slate-900">Turnos de caja</h2>
            </div>
            <div className="max-h-[44vh] overflow-y-auto">
              {sessionsQuery.isLoading ? (
                <p className="px-4 py-3 text-sm text-slate-500">Cargando sesiones...</p>
              ) : sessions.length === 0 ? (
                <p className="px-4 py-3 text-sm text-slate-500">No hay sesiones registradas.</p>
              ) : (
                <div className="divide-y divide-slate-200">
                  {sessions.map((session) => {
                    const isActive = session.id === selectedSession?.id;
                    return (
                      <button
                        key={session.id}
                        type="button"
                        onClick={() => {
                          setSelectedSessionId(session.id);
                          setCloseReport(null);
                        }}
                        className={`w-full px-4 py-3 text-left hover:bg-slate-50 ${isActive ? "bg-brand-50" : "bg-white"}`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-semibold text-slate-900">Caja #{session.id} · {session.currency_code}</p>
                            <p className="text-xs text-slate-500">{formatHotelDateTime(session.opened_at, hotelTimeZone)}</p>
                          </div>
                          <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${session.status === "open" ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>
                            {cashSessionStatusLabel[session.status] || session.status}
                          </span>
                        </div>
                        {pendingCloseReports.some((report) => report.session_id === session.id) ? (
                          <span className="mt-2 inline-flex rounded-full bg-amber-100 px-2 py-1 text-[11px] font-semibold text-amber-900">
                            Diferencia pendiente
                          </span>
                        ) : null}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          <form className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" onSubmit={handleOpenSession}>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Apertura</p>
              <h2 className="text-lg font-semibold text-slate-900">Abrir caja</h2>
              {!openSessionForOpeningCurrency && latestCloseReportForOpeningCurrency && !successorNeedsApproval ? (
                <p className="mt-1 text-xs text-emerald-700">
                  Saldo sucesor sugerido por el último arqueo: {money(successorOpeningBalance, currency)}
                </p>
              ) : null}
            </div>
            <PersistentActionError
              message={cashActionErrors[`open:${openingCurrency}`]}
              onClose={() => dismissCashActionError(`open:${openingCurrency}`)}
            />
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Saldo inicial</span>
              <input
                type="number"
                min={0}
                step="0.01"
                value={openingBalance ?? successorOpeningBalance}
                onChange={(event) => setOpeningBalance(Number(event.target.value))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Moneda</span>
              <select
                value={openingCurrency}
                onChange={(event) => setOpeningCurrency(event.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
              >
                {Array.from(new Set(["ARS", ...availableCurrencies])).map((currencyCode) => (
                  <option key={currencyCode} value={currencyCode}>{currencyCode}</option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Notas</span>
              <textarea
                value={openingNotes}
                onChange={(event) => setOpeningNotes(event.target.value)}
                rows={3}
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              />
            </label>
            <button
              type="submit"
              disabled={busy || !canOperateCash || Boolean(openSessionForOpeningCurrency) || successorNeedsApproval}
              className="w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              {openSessionForOpeningCurrency ? "Ya hay una caja abierta" : "Abrir caja"}
            </button>
          </form>
        </section>

        <section className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Movimientos</p>
                <h2 className="text-lg font-semibold text-slate-900">
                  {selectedSession ? `Caja #${selectedSession.id}` : "Sin caja seleccionada"}
                </h2>
                <p className="text-xs text-slate-500">
                  {selectedSession ? cashSessionStatusLabel[selectedSession.status] || selectedSession.status : "Selecciona una sesión"}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {canSubmitCashExpense ? (
                  <button
                    type="button"
                    data-testid="cash-create-expense-button"
                    aria-pressed={movementForm.movement_type === "expense"}
                    onClick={() => setMovementForm((current) => ({ ...current, movement_type: "expense" }))}
                    className="rounded-lg border border-brand-200 bg-brand-600 px-3 py-2 text-xs font-semibold text-white hover:bg-brand-700"
                  >
                    Registrar gasto
                  </button>
                ) : null}
                <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                  {movements.length} movimientos
                </span>
              </div>
            </div>

            {selectedSession && hasPermission("cash:operate") ? (
              <form className="rounded-lg border border-sky-200 bg-sky-50 p-3" onSubmit={handleCashNotesSubmit}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <label className="text-sm font-semibold text-sky-950" htmlFor="cash-session-notes">
                    Notas de la caja
                  </label>
                  {collaborativeCashSession.status !== "idle" ? (
                    <span className="text-xs text-sky-700" role="status">
                      {collaborativeCashSession.status === "connected"
                        ? `Coedición conectada${collaborativeCashSession.peers.length ? ` · ${collaborativeCashSession.peers.length} usuario(s) más` : ""}`
                        : collaborativeCashSession.status === "saving"
                          ? "Guardando..."
                          : collaborativeCashSession.status === "conflict"
                            ? "Conflicto pendiente"
                            : collaborativeCashSession.status === "degraded"
                              ? "Coedición degradada"
                              : "Conectando..."}
                    </span>
                  ) : null}
                </div>
                <textarea
                  id="cash-session-notes"
                  value={String(collaborativeCashSession.draftValues.notes ?? "")}
                  onChange={(event) => collaborativeCashSession.setField("notes", event.target.value || null)}
                  onFocus={() => collaborativeCashSession.focusField("notes")}
                  onBlur={() => collaborativeCashSession.blurField("notes")}
                  rows={2}
                  className="mt-2 w-full rounded-lg border border-sky-200 bg-white px-3 py-2 text-sm"
                />
                <PersistentActionError
                  message={cashActionErrors[cashNotesErrorKey]}
                  onClose={() => dismissCashActionError(cashNotesErrorKey)}
                />
                {Object.values(collaborativeCashSession.conflicts).map((conflict) => (
                  <div key={conflict.field} className="mt-2 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-950" data-testid={`cash-conflict-${conflict.field}`}>
                    <p className="font-semibold">Conflicto en {conflict.field}</p>
                    <p>Propio: {String(conflict.localValue ?? "(vacío)")}</p>
                    <p>Remoto: {String(conflict.remoteValue ?? "(vacío)")}</p>
                    <div className="mt-1 flex gap-2">
                      <button type="button" className="rounded border border-amber-300 bg-white px-2 py-1 font-semibold" onClick={() => collaborativeCashSession.keepMine(conflict.field)}>
                        Conservar el mío
                      </button>
                      <button type="button" className="rounded border border-amber-300 bg-white px-2 py-1 font-semibold" onClick={() => collaborativeCashSession.useRemote(conflict.field)}>
                        Usar remoto
                      </button>
                    </div>
                  </div>
                ))}
                <button
                  type="submit"
                  disabled={!collaborativeCashSession.isDirty || collaborativeCashSession.isSaving}
                  className="mt-2 rounded-lg border border-sky-300 bg-white px-3 py-2 text-xs font-semibold text-sky-900 disabled:opacity-50"
                >
                  Guardar notas
                </button>
              </form>
            ) : null}

            <form className="mt-4 grid gap-4 md:grid-cols-2" onSubmit={handleMovementSubmit}>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Tipo</span>
                <select
                  value={movementForm.movement_type}
                  onChange={(event) => setMovementForm((current) => ({ ...current, movement_type: event.target.value as CashMovementPayload["movement_type"] }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                >
                  <option value="income">Ingreso</option>
                  <option value="expense" disabled={!canSubmitCashExpense}>Gasto pendiente de aprobación</option>
                  <option value="adjustment" disabled={!canAdjustCash}>Ajuste manual (responsable + MFA)</option>
                </select>
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Importe</span>
                <input
                  type="number"
                  min={0.01}
                  step="0.01"
                  value={movementForm.amount || ""}
                  onChange={(event) => setMovementForm((current) => ({ ...current, amount: Number(event.target.value) }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="space-y-1 text-sm md:col-span-2">
                <span className="text-slate-600">Descripción</span>
                <input
                  value={movementForm.description ?? ""}
                  onChange={(event) => setMovementForm((current) => ({ ...current, description: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              {movementForm.movement_type === "expense" ? (
                <>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Categoría</span>
                    <input
                      required
                      maxLength={64}
                      value={expenseCategory}
                      onChange={(event) => setExpenseCategory(event.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Proveedor</span>
                    <input
                      required
                      maxLength={120}
                      value={expenseVendor}
                      onChange={(event) => setExpenseVendor(event.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Referencia del comprobante</span>
                    <input
                      required={!expenseReceiptImage}
                      maxLength={120}
                      value={expenseReceiptReference}
                      onChange={(event) => setExpenseReceiptReference(event.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">O adjuntá una imagen</span>
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={handleExpenseReceiptFile}
                      className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs"
                    />
                    <span className="block text-xs text-slate-500">JPEG, PNG o WEBP · hasta 5 MB. El archivo se guarda en almacenamiento privado.</span>
                    {expenseReceiptFilename ? <span className="block text-xs text-emerald-700">Adjunto: {expenseReceiptFilename}</span> : null}
                  </label>
                  <p className="text-xs text-amber-800 md:col-span-2">El gasto queda pendiente. Solo Dueño, Codueña o Gerencia pueden aprobarlo con MFA; hasta entonces no cambia el saldo de caja.</p>
                </>
              ) : null}
              {movementForm.movement_type === "expense" && !canSubmitCashExpense ? (
                <p className="text-xs text-amber-800 md:col-span-2">
                  Para cargar un gasto necesitás autorización para operar caja y registrar gastos. Las devoluciones a huéspedes se registran desde el flujo de reembolso.
                </p>
              ) : null}
              {movementForm.movement_type === "expense" && canSubmitCashExpense && (!selectedSession || selectedSession.status !== "open") ? (
                <p className="text-xs text-amber-800 md:col-span-2">
                  Abrí una caja o seleccioná una sesión abierta para registrar el gasto.
                </p>
              ) : null}
              <div className="md:col-span-2">
                <PersistentActionError
                  message={cashActionErrors[movementFormErrorKey]}
                  onClose={() => dismissCashActionError(movementFormErrorKey)}
                />
              </div>
              <div className="md:col-span-2 flex justify-end">
                <button
                  type="submit"
                  disabled={busy || !canOperateCash || (movementForm.movement_type === "expense" && !canSubmitCashExpense) || (movementForm.movement_type === "adjustment" && !canAdjustCash) || !selectedSession || selectedSession.status !== "open" || Number(movementForm.amount) <= 0}
                  className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                >
                  {movementForm.movement_type === "expense" ? "Registrar gasto pendiente" : "Registrar movimiento"}
                </button>
              </div>
            </form>

            <div className="mt-5 overflow-hidden rounded-lg border border-slate-200">
              {movementsQuery.isLoading ? (
                <p className="px-4 py-3 text-sm text-slate-500">Cargando movimientos...</p>
              ) : displayedMovements.length === 0 ? (
                <p className="px-4 py-3 text-sm text-slate-500">No hay movimientos para esta caja.</p>
              ) : (
                <div className="divide-y divide-slate-200">
                  {displayedMovements.map((movement) => (
                    <div key={movement.id} className="grid gap-2 px-4 py-3 text-sm sm:grid-cols-[1fr_auto]">
                      <div>
                        <p className="font-semibold text-slate-900">{cashMovementTypeLabel[movement.movement_type]}</p>
                        <p className="text-xs text-slate-500">
                          {movement.description || "Sin descripción"} - {formatHotelDateTime(movement.recorded_at, hotelTimeZone)}
                        </p>
                      </div>
                      <p className="font-semibold text-slate-900">{money(movement.amount, currency)}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {canViewCash ? (
              <section className="mt-5 overflow-hidden rounded-lg border border-slate-200 bg-white" data-testid="cash-expenses">
                <div className="border-b border-slate-200 px-4 py-3">
                  <h3 className="font-semibold text-slate-900">Gastos de caja</h3>
                  <p className="text-xs text-slate-500">Los gastos pendientes no afectan el arqueo hasta que se aprueben.</p>
                </div>
                {cashExpensesQuery.isLoading ? <p className="px-4 py-3 text-sm text-slate-500">Cargando gastos…</p> : null}
                {cashExpensesQuery.isError ? <p className="px-4 py-3 text-sm text-rose-700">No se pudieron cargar los gastos. {(cashExpensesQuery.error as Error).message}</p> : null}
                {!cashExpensesQuery.isLoading && !cashExpensesQuery.isError && cashExpenses.length === 0 ? (
                  <p className="px-4 py-3 text-sm text-slate-500">No hay gastos registrados.</p>
                ) : null}
                <ul className="divide-y divide-slate-100">
                  {cashExpenses.map((expense) => (
                    <li key={expense.id} className="grid gap-3 px-4 py-3 text-sm lg:grid-cols-[minmax(0,1fr)_minmax(260px,auto)]">
                      <div>
                        <p className="font-semibold text-slate-900">{expense.category} · {expense.vendor} · {money(expense.amount, expense.currency_code)}</p>
                        <p className="text-xs text-slate-600">Caja #{expense.session_id} · {formatHotelDateTime(expense.created_at, hotelTimeZone)} · registrado por {expense.recorded_by_name ?? "Usuario"}</p>
                        <p className="text-xs text-slate-500">{expense.description || expense.receipt_reference || "Sin detalle adicional"}</p>
                        {expense.status === "approved" ? <p className="text-xs text-emerald-700">Aprobado por {expense.approved_by_name ?? "Usuario"} · {expense.approved_at ? formatHotelDateTime(expense.approved_at, hotelTimeZone) : ""}</p> : null}
                        {expense.status === "rejected" ? <p className="text-xs text-rose-700">Rechazado por {expense.rejected_by_name ?? "Usuario"}: {expense.rejection_reason}</p> : null}
                        {expense.receipt_reference ? <p className="text-xs text-slate-500">Comprobante: {expense.receipt_reference}</p> : null}
                        <PersistentActionError
                          message={cashActionErrors[`expense:${expense.id}`]}
                          onClose={() => dismissCashActionError(`expense:${expense.id}`)}
                        />
                      </div>
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
                        {expense.has_receipt_image ? (
                          <button type="button" onClick={() => void handleExpenseReceiptDownload(expense.id)} className="rounded border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-700">
                            Abrir comprobante
                          </button>
                        ) : null}
                        {expense.status === "pending" ? <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-900">Pendiente de aprobación</span> : null}
                        {expense.status === "pending" && canApproveCashExpenses ? (
                          <div className="flex flex-col gap-2 sm:min-w-64">
                            <button type="button" disabled={busy} onClick={() => void handleApproveExpense(expense.id)} className="rounded bg-brand-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">
                              Aprobar gasto · MFA
                            </button>
                            <input
                              value={expenseRejectionReasons[expense.id] ?? ""}
                              onChange={(event) => setExpenseRejectionReasons((current) => ({ ...current, [expense.id]: event.target.value }))}
                              maxLength={1000}
                              placeholder="Motivo para rechazar"
                              aria-label={`Motivo para rechazar gasto ${expense.id}`}
                              className="rounded border border-slate-300 px-2 py-1 text-xs"
                            />
                            <button type="button" disabled={busy || !(expenseRejectionReasons[expense.id] ?? "").trim()} onClick={() => void handleRejectExpense(expense.id)} className="rounded border border-rose-300 bg-white px-3 py-2 text-xs font-semibold text-rose-700 disabled:opacity-50">
                              Rechazar · MFA
                            </button>
                          </div>
                        ) : expense.status !== "pending" ? <span className={`rounded-full px-2 py-1 text-xs font-semibold ${expense.status === "approved" ? "bg-emerald-100 text-emerald-900" : "bg-rose-100 text-rose-900"}`}>
                          {expense.status === "approved" ? "Aprobado" : "Rechazado"}
                        </span> : null}
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </div>

          {selectedSession?.status === "open" ? (
          <form className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm" onSubmit={handleCloseSession}>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Arqueo</p>
              <h2 className="text-lg font-semibold text-slate-900">Cerrar caja</h2>
              <p className="text-sm text-slate-600">Saldo esperado: {money(expectedBalance, currency)}</p>
            </div>
            <PersistentActionError
              message={cashActionErrors[closeSessionErrorKey]}
              onClose={() => dismissCashActionError(closeSessionErrorKey)}
            />
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Saldo contado</span>
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={countedBalance || ""}
                  onChange={(event) => {
                    if (selectedSession) {
                      setCountedBalances((current) => ({ ...current, [selectedSession.id]: Number(event.target.value) }));
                    }
                  }}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="flex items-center gap-2 pt-6 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={approveOnClose}
                  onChange={(event) => setApproveOnClose(event.target.checked)}
                  className="h-11 w-11 shrink-0 cursor-pointer accent-brand-600"
                />
                Aprobar diferencia al cerrar
              </label>
              <label className="space-y-1 text-sm md:col-span-2">
                <span className="text-slate-600">Notas de cierre</span>
                <textarea
                  value={closeNotes}
                  onChange={(event) => setCloseNotes(event.target.value)}
                  rows={3}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <p className="text-xs text-slate-500 md:col-span-2">
                El arqueo incluye todo el efectivo contado. Después del cierre, Dueño o Codueña confirma la custodia y registra por separado el cambio que deja en la caja sucesora.
              </p>
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={busy || !canOperateCash || !selectedSession || selectedSession.status !== "open"}
                className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
              >
                Cerrar caja
              </button>
            </div>
          </form>
          ) : null}

          {selectedSessionCloseReport ? (
            <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Reporte de cierre</p>
                <h2 className="text-lg font-semibold text-slate-900">Arqueo #{selectedSessionCloseReport.id}</h2>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <Metric label="Esperado" value={money(selectedSessionCloseReport.expected_balance, closeReportCurrency)} />
                <Metric label="Declarado" value={money(selectedSessionCloseReport.declared_balance, closeReportCurrency)} />
                <Metric label="Diferencia" value={money(selectedSessionCloseReport.difference, closeReportCurrency)} />
              </div>
              <div className="border-t border-slate-200 pt-3 text-sm text-slate-600">
                <p>Cerrada el {formatHotelDateTime(selectedSessionCloseReport.closed_at, hotelTimeZone)} por {selectedSessionCloseReport.closed_by_name ?? "Usuario no disponible"}.</p>
                <p className="mt-1">Notas de cierre: {selectedSessionCloseReport.notes?.trim() || "Sin notas"}</p>
              </div>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-slate-600">
                  Estado: {Number(selectedSessionCloseReport.difference) === 0 ? "sin diferencia" : selectedSessionCloseReport.difference_approved ? "diferencia aprobada" : "pendiente de aprobación"}
                </p>
                {canApproveDifference && !selectedSessionCloseReport.difference_approved && Number(selectedSessionCloseReport.difference) !== 0 ? (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void handleApproveDifference(selectedSessionCloseReport.id, "report")}
                    className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                  >
                    Aprobar diferencia
                  </button>
                ) : null}
              </div>
              <PersistentActionError
                message={cashActionErrors[`difference:report:${selectedSessionCloseReport.id}`]}
                onClose={() => dismissCashActionError(`difference:report:${selectedSessionCloseReport.id}`)}
              />
              <div className="border-t border-slate-200 pt-3 text-sm text-slate-600">
                <p>
                  Caja sucesora: {selectedSessionCloseReport.successor_session_id
                    ? `#${selectedSessionCloseReport.successor_session_id} abierta con saldo ${money(selectedSessionCloseReport.successor_opening_balance, closeReportCurrency)}`
                    : "pendiente de creación"}.
                </p>
                <p className="mt-1">
                  Custodia: {selectedSessionCloseReport.custody_handoff?.status === "confirmed"
                    ? `recepción confirmada de ${money(selectedSessionCloseReport.custody_handoff.delivered_amount, closeReportCurrency)}`
                    : `pendiente de recepción del dueño o la codueña por ${money(selectedSessionCloseReport.custody_handoff?.delivered_amount, closeReportCurrency)}`}.
                </p>
                <p className="mt-1">
                  Fondo de cambio declarado: {selectedSessionCloseReport.successor_float_declared_amount == null
                    ? "pendiente"
                    : `${money(selectedSessionCloseReport.successor_float_declared_amount, closeReportCurrency)} para la caja sucesora`}
                  {selectedSessionCloseReport.successor_float_declared_by_user_id
                    ? ` · declarado por ${selectedSessionCloseReport.successor_float_declared_by_name ?? "Usuario no disponible"}`
                    : ""}.
                </p>
                {canReceiveCustody && selectedSessionCloseReport.custody_handoff?.status === "pending" ? (
                  <label className="mt-3 block max-w-sm space-y-1 text-xs">
                    <span className="text-slate-600">Efectivo que dejo como cambio en la sucesora</span>
                    <input
                      type="number"
                      min={0}
                      max={9999999999.99}
                      step="0.01"
                      value={successorFloatAmounts[selectedSessionCloseReport.id] ?? "0"}
                      onChange={(event) => setSuccessorFloatAmounts((current) => ({ ...current, [selectedSessionCloseReport.id]: event.target.value }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                      aria-label={`Cambio para caja sucesora de caja ${selectedSessionCloseReport.session_id}`}
                    />
                  </label>
                ) : null}
                {canReceiveCustody && selectedSessionCloseReport.custody_handoff?.status === "pending" ? (
                  <>
                    <button
                      type="button"
                      disabled={busy || Number(successorFloatAmounts[selectedSessionCloseReport.id] ?? "0") < 0 || Number(successorFloatAmounts[selectedSessionCloseReport.id] ?? "0") > 9999999999.99}
                      onClick={() => void handleConfirmCustody(selectedSessionCloseReport, "report")}
                      className="mt-3 rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                    >
                      Confirmar custodia y cambio
                    </button>
                    <PersistentActionError
                      message={cashActionErrors[`custody:report:${selectedSessionCloseReport.id}`]}
                      onClose={() => dismissCashActionError(`custody:report:${selectedSessionCloseReport.id}`)}
                    />
                  </>
                ) : null}
              </div>
            </section>
          ) : null}
        </section>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function PersistentActionError({ message, onClose }: { message?: string; onClose: () => void }) {
  if (!message) return null;

  return (
    <div role="alert" data-testid="cash-action-error" className="mt-2 flex items-start justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
      <p className="min-w-0 flex-1">{message}</p>
      <button
        type="button"
        onClick={onClose}
        aria-label="Cerrar error"
        className="shrink-0 rounded px-1 font-semibold text-rose-900 hover:bg-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-500"
      >
        Cerrar
      </button>
    </div>
  );
}

function SummaryLine({ label, value }: { label: string; value: string }) {
  return <div><p className="text-xs text-slate-500">{label}</p><p className="font-semibold text-slate-800">{value}</p></div>;
}

function paymentMethodLabel(method: string) {
  const labels: Record<string, string> = {
    cash: "Efectivo",
    credit_card: "Tarjeta de crédito",
    debit_card: "Tarjeta de débito",
    bank_transfer: "Transferencia",
    mercado_pago: "Mercado Pago",
    paypal: "PayPal"
  };
  return labels[method] ?? method;
}

function movementLabel(movementType?: string | null) {
  if (movementType === "income") return "Ingreso manual";
  if (movementType === "expense") return "Egreso manual";
  return "Ajuste manual";
}
