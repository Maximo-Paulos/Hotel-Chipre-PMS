import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  cancelPaymentLinkTest,
  createMercadoPagoPaymentLinkTest,
  listPaymentLinkTests,
  refreshPaymentLinkTest,
  type PaymentLinkTest,
} from "../../api/paymentLinkTests";
import { ApiError } from "../../api/client";
import { useSession } from "../../state/session";

const statusTone: Record<string, string> = {
  approved: "bg-emerald-50 text-emerald-700",
  pending: "bg-amber-50 text-amber-700",
  failed: "bg-rose-50 text-rose-700",
  refunded: "bg-violet-50 text-violet-700",
  partially_refunded: "bg-fuchsia-50 text-fuchsia-700",
  expired: "bg-slate-100 text-slate-700",
  cancelled: "bg-slate-200 text-slate-800",
};

const statusLabel: Record<string, string> = {
  approved: "Pagado",
  pending: "Pendiente",
  failed: "Fallido",
  refunded: "Devuelto",
  partially_refunded: "Devuelto parcial",
  expired: "Vencido",
  cancelled: "Cancelado",
};

export function SettingsTestsPage() {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    recipient_email: "",
    amount: "",
    description: "Sena de reserva",
    currency: "ARS",
    expires_in_minutes: "60",
  });
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const testsQuery = useQuery({
    queryKey: ["payment-link-tests", session.hotelId],
    queryFn: () => listPaymentLinkTests(session),
    refetchInterval: 10_000,
  });
  const tests = testsQuery.data ?? [];

  const createMutation = useMutation({
    mutationFn: () =>
      createMercadoPagoPaymentLinkTest(
        {
          recipient_email: form.recipient_email,
          amount: Number(form.amount),
          description: form.description,
          currency: form.currency,
          expires_in_minutes: form.expires_in_minutes ? Number(form.expires_in_minutes) : undefined,
        },
        session,
      ),
    onSuccess: async (created) => {
      setError(null);
      setToast(
        created.email_sent_at
          ? "Prueba creada. Se envio el mail y el estado se va a acreditar automaticamente."
          : "Prueba creada. Copia el link manualmente si el mail no llega. El estado igual se revisa automaticamente.",
      );
      setForm({
        recipient_email: "",
        amount: "",
        description: "Sena de reserva",
        currency: "ARS",
        expires_in_minutes: "60",
      });
      await queryClient.invalidateQueries({ queryKey: ["payment-link-tests", session.hotelId] });
    },
    onError: (err) => {
      const message = err instanceof ApiError ? err.message : "No se pudo crear la prueba.";
      setError(message);
      setToast(null);
    },
  });

  const refreshMutation = useMutation({
    mutationFn: (testId: number) => refreshPaymentLinkTest(testId, session),
    onSuccess: async (test) => {
      setError(null);
      setToast(
        test.status === "approved"
          ? "Pago confirmado por Mercado Pago."
          : "Estado actualizado. Si la persona ya pago, el sistema lo seguira verificando automaticamente.",
      );
      await queryClient.invalidateQueries({ queryKey: ["payment-link-tests", session.hotelId] });
    },
    onError: (err) => {
      const message = err instanceof ApiError ? err.message : "No se pudo refrescar el estado.";
      setError(message);
      setToast(null);
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (testId: number) => cancelPaymentLinkTest(testId, session),
    onSuccess: async () => {
      setError(null);
      setToast("Link cancelado. Mercado Pago ya no deberia permitir nuevos pagos sobre esa preferencia.");
      await queryClient.invalidateQueries({ queryKey: ["payment-link-tests", session.hotelId] });
    },
    onError: (err) => {
      const message = err instanceof ApiError ? err.message : "No se pudo cancelar el link.";
      setError(message);
      setToast(null);
    },
  });

  const canSubmit = Boolean(form.recipient_email && form.amount && Number(form.amount) > 0);

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Configuracion</p>
        <h1 className="text-2xl font-semibold text-slate-900">Pruebas</h1>
        <p className="text-sm text-slate-600">
          Envia un link de pago de Mercado Pago por mail y deja que el sistema verifique solo cuando quede abonado.
        </p>
      </header>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Probar Mercado Pago</h2>
            <p className="text-sm text-slate-600">
              Usa la conexion guardada del hotel activo para mandar un link de pago de prueba. El estado se refresca solo cada pocos segundos.
            </p>
          </div>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Mercado Pago</span>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <label className="text-sm font-semibold text-slate-700">
            Email del huésped
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              type="email"
              placeholder="huesped@email.com"
              value={form.recipient_email}
              onChange={(e) => setForm((prev) => ({ ...prev, recipient_email: e.target.value }))}
            />
          </label>
          <label className="text-sm font-semibold text-slate-700">
            Monto
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              type="number"
              min="1"
              step="0.01"
              placeholder="25000"
              value={form.amount}
              onChange={(e) => setForm((prev) => ({ ...prev, amount: e.target.value }))}
            />
          </label>
          <label className="text-sm font-semibold text-slate-700">
            Concepto
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="Sena de reserva"
              value={form.description}
              onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
            />
          </label>
          <label className="text-sm font-semibold text-slate-700">
            Moneda
            <select
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              value={form.currency}
              onChange={(e) => setForm((prev) => ({ ...prev, currency: e.target.value }))}
            >
              <option value="ARS">ARS</option>
              <option value="USD">USD</option>
            </select>
          </label>
          <label className="text-sm font-semibold text-slate-700">
            Vence en (minutos)
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              type="number"
              min="1"
              step="1"
              placeholder="60"
              value={form.expires_in_minutes}
              onChange={(e) => setForm((prev) => ({ ...prev, expires_in_minutes: e.target.value }))}
            />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            onClick={() => createMutation.mutate()}
            disabled={!canSubmit || createMutation.isPending}
          >
            {createMutation.isPending ? "Creando prueba..." : "Probar"}
          </button>
          <p className="text-xs text-slate-500">
            El link se manda por mail y tambien queda visible abajo por si quieres copiarlo manualmente. No hace falta tocar actualizar para acreditar el pago.
          </p>
        </div>
        <p className="mt-2 text-[11px] text-slate-500">
          En entorno local el sistema verifica el pago automaticamente por consulta directa. Cuando tengamos un dominio publico HTTPS,
          tambien va a recibir el webhook de Mercado Pago.
        </p>

        {toast && <p className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{toast}</p>}
        {error && <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Seguimiento de pruebas</h2>
          {testsQuery.isFetching && <span className="text-xs text-slate-500">Verificando pagos...</span>}
        </div>

        {tests.length ? (
          <div className="grid gap-4 md:grid-cols-2">
            {tests.map((test: PaymentLinkTest) => (
              <article key={test.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">Email del huesped</p>
                    <p className="text-sm text-slate-700">{test.recipient_email}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Monto enviado</p>
                    <p className="text-sm font-semibold text-slate-900">
                      {test.currency} {test.amount.toFixed(2)}
                    </p>
                  </div>
                </div>

                <div className="mt-3 space-y-1 text-sm text-slate-700">
                  <p>
                    <strong>Concepto:</strong> {test.description}
                  </p>
                  <p>
                    <strong>Referencia:</strong> {test.external_reference}
                  </p>
                  {test.created_at && (
                    <p>
                      <strong>Creada:</strong> {new Date(test.created_at).toLocaleString()}
                    </p>
                  )}
                  {test.paid_at && (
                    <p>
                      <strong>Abonada:</strong> {new Date(test.paid_at).toLocaleString()}
                    </p>
                  )}
                  {test.refunded_at && (
                    <p>
                      <strong>Devuelta:</strong> {new Date(test.refunded_at).toLocaleString()}
                    </p>
                  )}
                  {test.expires_at && (
                    <p>
                      <strong>Vence:</strong> {new Date(test.expires_at).toLocaleString()}
                    </p>
                  )}
                  {typeof test.refunded_amount === "number" && test.refunded_amount > 0 && (
                    <p>
                      <strong>Monto devuelto:</strong> {test.currency} {test.refunded_amount.toFixed(2)}
                    </p>
                  )}
                </div>

                <div className="mt-4 grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm font-semibold text-slate-800 disabled:opacity-60"
                    onClick={() => refreshMutation.mutate(test.id)}
                    disabled={refreshMutation.isPending}
                  >
                    Refrescar
                  </button>
                  <div
                    className={`flex items-center justify-center rounded-lg px-3 py-3 text-sm font-semibold ${
                      statusTone[test.status] || "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {statusLabel[test.status] || test.status}
                  </div>
                </div>

                {(test.payment_link || test.status === "pending") && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {test.payment_link && (
                      <>
                        <a
                          href={test.payment_link}
                          target="_blank"
                          rel="noreferrer"
                          className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700"
                        >
                          Abrir link
                        </a>
                        <button
                          type="button"
                          className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700"
                          onClick={() => navigator.clipboard?.writeText(test.payment_link || "")}
                        >
                          Copiar link
                        </button>
                      </>
                    )}
                    {test.status === "pending" && (
                      <button
                        type="button"
                        className="rounded-lg border border-rose-200 px-3 py-2 text-xs font-semibold text-rose-700 disabled:opacity-60"
                        onClick={() => cancelMutation.mutate(test.id)}
                        disabled={cancelMutation.isPending}
                      >
                        Cancelar link
                      </button>
                    )}
                  </div>
                )}

                {test.last_error && <p className="mt-3 text-xs text-rose-700">{test.last_error}</p>}
              </article>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-sm text-slate-600">
            Aun no hay pruebas creadas para este hotel.
          </div>
        )}
      </section>
    </div>
  );
}

export default SettingsTestsPage;
