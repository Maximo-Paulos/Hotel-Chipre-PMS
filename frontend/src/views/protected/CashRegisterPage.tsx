import React, { useMemo, useState } from "react";

import { type CashCloseReport, type CashMovementPayload } from "../../api/cashRegister";
import {
  cashMovementTypeLabel,
  cashSessionStatusLabel,
  useCashMovements,
  useCashRegisterMutations,
  useCashSessions
} from "../../hooks/useCashRegister";

const emptyMovementForm: CashMovementPayload = {
  movement_type: "income",
  amount: 0,
  description: "",
  reservation_id: null,
  transaction_id: null
};

const money = (value?: number | string | null, currency = "ARS") =>
  Number(value ?? 0).toLocaleString("es-AR", { style: "currency", currency });

export function CashRegisterPage() {
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [openingBalance, setOpeningBalance] = useState(0);
  const [openingNotes, setOpeningNotes] = useState("");
  const [movementForm, setMovementForm] = useState<CashMovementPayload>(emptyMovementForm);
  const [countedBalance, setCountedBalance] = useState(0);
  const [closeNotes, setCloseNotes] = useState("");
  const [approveOnClose, setApproveOnClose] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [closeReport, setCloseReport] = useState<CashCloseReport | null>(null);

  const sessionsQuery = useCashSessions();
  const sessions = useMemo(() => sessionsQuery.data ?? [], [sessionsQuery.data]);
  const openSession = useMemo(() => sessions.find((session) => session.status === "open") ?? null, [sessions]);
  const selectedSession = useMemo(
    () => sessions.find((session) => session.id === selectedSessionId) ?? openSession ?? sessions[0] ?? null,
    [openSession, selectedSessionId, sessions]
  );
  const movementsQuery = useCashMovements(selectedSession?.id);
  const mutations = useCashRegisterMutations(selectedSession?.id);
  const movements = useMemo(() => movementsQuery.data ?? [], [movementsQuery.data]);

  const totals = useMemo(() => {
    return movements.reduce(
      (acc, movement) => {
        const amount = Number(movement.amount);
        if (movement.movement_type === "income") acc.income += amount;
        if (movement.movement_type === "expense") acc.expense += amount;
        if (movement.movement_type === "adjustment") acc.adjustment += amount;
        return acc;
      },
      { income: 0, expense: 0, adjustment: 0 }
    );
  }, [movements]);

  const expectedBalance = Number(selectedSession?.opening_balance ?? 0) + totals.income - totals.expense + totals.adjustment;
  const currency = selectedSession?.currency_code ?? "ARS";
  const busy =
    mutations.openSessionMutation.isPending ||
    mutations.addMovementMutation.isPending ||
    mutations.closeSessionMutation.isPending ||
    mutations.approveDifferenceMutation.isPending;

  const handleOpenSession = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    setCloseReport(null);
    try {
      const session = await mutations.openSessionMutation.mutateAsync({
        opening_balance: Number(openingBalance),
        currency_code: "ARS",
        notes: openingNotes.trim() || null
      });
      setSelectedSessionId(session.id);
      setOpeningBalance(0);
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
        description: movementForm.description?.trim() || null,
        reservation_id: movementForm.reservation_id ? Number(movementForm.reservation_id) : null,
        transaction_id: movementForm.transaction_id ? Number(movementForm.transaction_id) : null
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
    if (!closeReport) return;
    setMessage(null);
    try {
      const approved = await mutations.approveDifferenceMutation.mutateAsync(closeReport.id);
      setCloseReport(approved);
      setMessage("Diferencia aprobada.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo aprobar la diferencia.");
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
            </div>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Saldo inicial</span>
              <input
                type="number"
                min={0}
                step="0.01"
                value={openingBalance}
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
              disabled={busy || Boolean(openSession)}
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
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Reserva ID</span>
                <input
                  type="number"
                  min={1}
                  value={movementForm.reservation_id ?? ""}
                  onChange={(event) => setMovementForm((current) => ({ ...current, reservation_id: event.target.value ? Number(event.target.value) : null }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Transaccion ID</span>
                <input
                  type="number"
                  min={1}
                  value={movementForm.transaction_id ?? ""}
                  onChange={(event) => setMovementForm((current) => ({ ...current, transaction_id: event.target.value ? Number(event.target.value) : null }))}
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
                  Estado: {closeReport.difference_approved ? "diferencia aprobada" : "pendiente de aprobacion"}
                </p>
                {!closeReport.difference_approved && Number(closeReport.difference) !== 0 ? (
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
