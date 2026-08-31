import React, { useMemo, useState } from "react";

import { type CashCloseReport, type CashMovementPayload } from "../../api/cashRegister";
import {
  cashMovementTypeLabel,
  cashSessionStatusLabel,
  useLatestCashCloseReport,
  useCashMovements,
  useCashRegisterMutations,
  useCashSessions,
  useCashSessionSummary
} from "../../hooks/useCashRegister";
import { useSession } from "../../state/session";
import { useEffectivePermissions } from "../../hooks/usePermissions";
import { useCollaborativeResource } from "../../hooks/useCollaborativeResource";

const emptyMovementForm: CashMovementPayload = {
  movement_type: "income",
  amount: 0,
  description: ""
};

const money = (value?: number | string | null, currency = "ARS") =>
  Number(value ?? 0).toLocaleString("es-AR", { style: "currency", currency });

export function CashRegisterPage() {
  const { session } = useSession();
  const { hasPermission } = useEffectivePermissions();
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [openingBalance, setOpeningBalance] = useState<number | null>(null);
  const [openingNotes, setOpeningNotes] = useState("");
  const [movementForm, setMovementForm] = useState<CashMovementPayload>(emptyMovementForm);
  const [countedBalance, setCountedBalance] = useState(0);
  const [closeNotes, setCloseNotes] = useState("");
  const [approveOnClose, setApproveOnClose] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [closeReport, setCloseReport] = useState<CashCloseReport | null>(null);

  const sessionsQuery = useCashSessions();
  const latestCloseReportQuery = useLatestCashCloseReport();
  const sessions = useMemo(() => sessionsQuery.data ?? [], [sessionsQuery.data]);
  const openSession = useMemo(() => sessions.find((session) => session.status === "open") ?? null, [sessions]);
  const selectedSession = useMemo(
    () => sessions.find((session) => session.id === selectedSessionId) ?? openSession ?? sessions[0] ?? null,
    [openSession, selectedSessionId, sessions]
  );
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
  const latestCloseReport = latestCloseReportQuery.data;
  const successorNeedsApproval = Boolean(
    !openSession && latestCloseReport && Number(latestCloseReport.difference) !== 0 && !latestCloseReport.difference_approved
  );
  const successorOpeningBalance =
    latestCloseReport && (!Number(latestCloseReport.difference) || latestCloseReport.difference_approved)
      ? Number(latestCloseReport.declared_balance)
      : 0;
  const canApproveDifference = ["owner", "co_owner", "manager"].includes(session.baseRole ?? "");
  const canReceiveCustody = session.baseRole === "owner";

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
  const busy =
    mutations.openSessionMutation.isPending ||
    mutations.addMovementMutation.isPending ||
    mutations.closeSessionMutation.isPending ||
    mutations.approveDifferenceMutation.isPending ||
    mutations.confirmCustodyMutation.isPending;

  const handleOpenSession = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    setCloseReport(null);
    try {
      const session = await mutations.openSessionMutation.mutateAsync({
        opening_balance: Number(openingBalance ?? successorOpeningBalance),
        currency_code: "ARS",
        notes: openingNotes.trim() || null
      });
      setSelectedSessionId(session.id);
      setOpeningBalance(null);
      setOpeningNotes("");
      setMessage("Caja abierta.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo abrir la caja.");
    }
  };

  const handleMovementSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedSession || selectedSession.status !== "open") return;
    setMessage(null);
    try {
      await mutations.addMovementMutation.mutateAsync({
        ...movementForm,
        amount: Number(movementForm.amount),
        description: movementForm.description?.trim() || null
      });
      setMovementForm(emptyMovementForm);
      setMessage("Movimiento registrado.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo registrar el movimiento.");
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
      setCloseNotes("");
      setApproveOnClose(false);
      setMessage("Caja cerrada.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo cerrar la caja.");
    }
  };

  const handleApproveDifference = async () => {
    const reportToApprove = closeReport ?? latestCloseReport;
    if (!reportToApprove) return;
    setMessage(null);
    try {
      const approved = await mutations.approveDifferenceMutation.mutateAsync(reportToApprove.id);
      setCloseReport(approved);
      setMessage("Diferencia aprobada.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo aprobar la diferencia.");
    }
  };

  const handleConfirmCustody = async () => {
    if (!closeReport) return;
    setMessage(null);
    try {
      const confirmed = await mutations.confirmCustodyMutation.mutateAsync(closeReport.id);
      setCloseReport(confirmed);
      setMessage("Recepción de custodia confirmada.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo confirmar la custodia.");
    }
  };

  const handleCashNotesSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedSession || !collaborativeCashSession.isDirty) return;
    if (Object.keys(collaborativeCashSession.conflicts).length > 0) {
      setMessage("Hay un conflicto en las notas de caja. Elegí qué valor conservar.");
      return;
    }
    try {
      await collaborativeCashSession.save();
      setMessage("Notas de caja actualizadas.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudieron guardar las notas de caja.");
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operacion</p>
          <h1 className="text-2xl font-semibold text-slate-900">Caja</h1>
          <p className="text-sm text-slate-600">Apertura, movimientos, cierre de arqueo y aprobacion de diferencias.</p>
        </div>
        {sessionsQuery.isFetching && <p className="text-xs text-slate-500">Actualizando caja...</p>}
      </header>

      {message ? <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">{message}</div> : null}

      {successorNeedsApproval ? (
        <div className="flex flex-col gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 sm:flex-row sm:items-center sm:justify-between">
          <p>
            La caja anterior tiene una diferencia de {money(latestCloseReport?.difference, currency)}.
            Aprobala antes de abrir la caja sucesora.
          </p>
          {canApproveDifference ? (
            <button
              type="button"
              disabled={busy}
              onClick={handleApproveDifference}
              className="rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm font-semibold text-amber-900 hover:bg-amber-100 disabled:opacity-60"
            >
              Aprobar diferencia
            </button>
          ) : null}
        </div>
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
                        onClick={() => setSelectedSessionId(session.id)}
                        className={`w-full px-4 py-3 text-left hover:bg-slate-50 ${isActive ? "bg-brand-50" : "bg-white"}`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-semibold text-slate-900">Caja #{session.id}</p>
                            <p className="text-xs text-slate-500">{new Date(session.opened_at).toLocaleString("es-AR")}</p>
                          </div>
                          <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${session.status === "open" ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>
                            {cashSessionStatusLabel[session.status] || session.status}
                          </span>
                        </div>
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
              {!openSession && latestCloseReport && !successorNeedsApproval ? (
                <p className="mt-1 text-xs text-emerald-700">
                  Saldo sucesor sugerido por el último arqueo: {money(successorOpeningBalance, currency)}
                </p>
              ) : null}
            </div>
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
              disabled={busy || Boolean(openSession) || successorNeedsApproval}
              className="w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              {openSession ? "Ya hay una caja abierta" : "Abrir caja"}
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
                  {selectedSession ? cashSessionStatusLabel[selectedSession.status] || selectedSession.status : "Selecciona una sesion"}
                </p>
              </div>
              <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                {movements.length} movimientos
              </span>
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
                  <option value="expense">Egreso</option>
                  <option value="adjustment">Ajuste</option>
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
                <span className="text-slate-600">Descripcion</span>
                <input
                  value={movementForm.description ?? ""}
                  onChange={(event) => setMovementForm((current) => ({ ...current, description: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <div className="md:col-span-2 flex justify-end">
                <button
                  type="submit"
                  disabled={busy || !selectedSession || selectedSession.status !== "open" || Number(movementForm.amount) <= 0}
                  className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                >
                  Registrar movimiento
                </button>
              </div>
            </form>

            <div className="mt-5 overflow-hidden rounded-lg border border-slate-200">
              {movementsQuery.isLoading ? (
                <p className="px-4 py-3 text-sm text-slate-500">Cargando movimientos...</p>
              ) : movements.length === 0 ? (
                <p className="px-4 py-3 text-sm text-slate-500">No hay movimientos para esta caja.</p>
              ) : (
                <div className="divide-y divide-slate-200">
                  {movements.map((movement) => (
                    <div key={movement.id} className="grid gap-2 px-4 py-3 text-sm sm:grid-cols-[1fr_auto]">
                      <div>
                        <p className="font-semibold text-slate-900">{cashMovementTypeLabel[movement.movement_type]}</p>
                        <p className="text-xs text-slate-500">
                          {movement.description || "Sin descripcion"} - {new Date(movement.recorded_at).toLocaleString("es-AR")}
                        </p>
                      </div>
                      <p className="font-semibold text-slate-900">{money(movement.amount, currency)}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <form className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm" onSubmit={handleCloseSession}>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Arqueo</p>
              <h2 className="text-lg font-semibold text-slate-900">Cerrar caja</h2>
              <p className="text-sm text-slate-600">Saldo esperado: {money(expectedBalance, currency)}</p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Saldo contado</span>
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={countedBalance || ""}
                  onChange={(event) => setCountedBalance(Number(event.target.value))}
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
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={busy || !selectedSession || selectedSession.status !== "open"}
                className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
              >
                Cerrar caja
              </button>
            </div>
          </form>

          {closeReport ? (
            <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Reporte de cierre</p>
                <h2 className="text-lg font-semibold text-slate-900">Arqueo #{closeReport.id}</h2>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <Metric label="Esperado" value={money(closeReport.expected_balance, currency)} />
                <Metric label="Declarado" value={money(closeReport.declared_balance, currency)} />
                <Metric label="Diferencia" value={money(closeReport.difference, currency)} />
              </div>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-slate-600">
                  Estado: {Number(closeReport.difference) === 0 ? "sin diferencia" : closeReport.difference_approved ? "diferencia aprobada" : "pendiente de aprobacion"}
                </p>
                {canApproveDifference && !closeReport.difference_approved && Number(closeReport.difference) !== 0 ? (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={handleApproveDifference}
                    className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                  >
                    Aprobar diferencia
                  </button>
                ) : null}
              </div>
              <div className="border-t border-slate-200 pt-3 text-sm text-slate-600">
                <p>
                  Caja sucesora: {closeReport.successor_session_id ? `#${closeReport.successor_session_id} abierta con saldo $0` : "pendiente de creación"}.
                </p>
                <p className="mt-1">
                  Custodia: {closeReport.custody_handoff?.status === "confirmed" ? "recepción confirmada" : "pendiente de recepción del dueño"}.
                </p>
                {canReceiveCustody && closeReport.custody_handoff?.status === "pending" ? (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={handleConfirmCustody}
                    className="mt-3 rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                  >
                    Confirmar recepción de custodia
                  </button>
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
