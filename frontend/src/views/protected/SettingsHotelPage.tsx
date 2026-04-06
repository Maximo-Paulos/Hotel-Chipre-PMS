import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getHotelConfig, updateHotelConfig, type HotelConfig } from "../../api/config";
import { useSession } from "../../state/session";

export function SettingsHotelPage() {
  const { session } = useSession();
  const [form, setForm] = useState<Partial<HotelConfig>>({});

  const configQuery = useQuery({
    queryKey: ["hotel-config", session.hotelId],
    queryFn: () => getHotelConfig(session),
    onSuccess: (data) => setForm(data)
  });

  const updateMutation = useMutation({
    mutationFn: (payload: Partial<HotelConfig>) => updateHotelConfig(payload, session),
    onSuccess: (data) => setForm(data)
  });

  const handleChange = (key: keyof HotelConfig, value: unknown) => setForm((prev) => ({ ...prev, [key]: value }));
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateMutation.mutate(form);
  };

  if (!session.hotelId) {
    return <p className="text-sm text-rose-700">Seleccioná un hotel para editar su configuración.</p>;
  }

  const ownerOnly = session.role === "owner" || session.role === "co_owner";

  return (
    <div className="space-y-4">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Settings</p>
        <h1 className="text-2xl font-semibold text-slate-900">Configuración del hotel</h1>
        <p className="text-sm text-slate-600">Los cambios aplican solo al hotel ID {session.hotelId}.</p>
      </header>

      {configQuery.isLoading ? (
        <p className="text-sm text-slate-600">Cargando configuración...</p>
      ) : (
        <form onSubmit={handleSubmit} className="grid gap-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          {/* Identidad */}
          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-sm font-semibold text-slate-700">
              Nombre
              <input
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                value={form.hotel_name ?? ""}
                onChange={(e) => handleChange("hotel_name", e.target.value)}
              />
            </label>
            <label className="text-sm font-semibold text-slate-700">
              Zona horaria
              <input
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                value={form.hotel_timezone ?? ""}
                onChange={(e) => handleChange("hotel_timezone", e.target.value)}
              />
            </label>
          </div>

          {/* Pagos y políticas */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-slate-200 p-4">
              <h3 className="text-sm font-semibold text-slate-800">Pagos y depósitos</h3>
              <div className="grid gap-3 md:grid-cols-3 mt-2">
                <label className="text-sm font-semibold text-slate-700">
                  Depósito (%)
                  <input
                    type="number"
                    min={0}
                    max={100}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    value={form.deposit_percentage ?? 0}
                    onChange={(e) => handleChange("deposit_percentage", parseFloat(e.target.value || "0"))}
                  />
                </label>
                <label className="text-sm font-semibold text-slate-700">
                  Cancelación gratis (horas)
                  <input
                    type="number"
                    min={0}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    value={form.free_cancellation_hours ?? 0}
                    onChange={(e) => handleChange("free_cancellation_hours", parseInt(e.target.value || "0", 10))}
                  />
                </label>
                <label className="text-sm font-semibold text-slate-700">
                  Penalidad (%)
                  <input
                    type="number"
                    min={0}
                    max={100}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    value={form.cancellation_penalty_percentage ?? 0}
                    onChange={(e) => handleChange("cancellation_penalty_percentage", parseFloat(e.target.value || "0"))}
                  />
                </label>
              </div>
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                {[
                  ["enable_cash", "Efectivo"],
                  ["enable_credit_card", "Crédito"],
                  ["enable_debit_card", "Débito"],
                  ["enable_mercado_pago", "MercadoPago"],
                  ["enable_paypal", "PayPal"],
                  ["enable_bank_transfer", "Transferencia"]
                ].map(([key, label]) => (
                  <label key={key} className="flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={Boolean((form as Record<string, unknown>)[key])}
                      onChange={(e) => handleChange(key as keyof HotelConfig, e.target.checked)}
                    />
                    {label}
                  </label>
                ))}
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <label className="text-sm font-semibold text-slate-700">
                  Validar tarjeta
                  <input
                    type="checkbox"
                    className="ml-2"
                    checked={Boolean(form.card_validation_enabled)}
                    onChange={(e) => handleChange("card_validation_enabled", e.target.checked)}
                  />
                </label>
                <label className="text-sm font-semibold text-slate-700">
                  Reintentos de pago
                  <input
                    type="number"
                    min={0}
                    max={10}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    value={form.payment_retry_attempts ?? 2}
                    onChange={(e) => handleChange("payment_retry_attempts", parseInt(e.target.value || "0", 10))}
                  />
                </label>
                <label className="text-sm font-semibold text-slate-700">
                  Pre-autorización (%)
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step={1}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    value={form.auth_amount_pct ?? 0}
                    onChange={(e) => handleChange("auth_amount_pct", parseFloat(e.target.value || "0"))}
                  />
                </label>
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 p-4">
              <h3 className="text-sm font-semibold text-slate-800">Disponibilidad y OTA</h3>
              <div className="grid gap-3 md:grid-cols-2">
                <label className="text-sm font-semibold text-slate-700">
                  Sync inventario (min)
                  <input
                    type="number"
                    min={1}
                    max={1440}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    value={form.sync_interval_minutes ?? 5}
                    onChange={(e) => handleChange("sync_interval_minutes", parseInt(e.target.value || "5", 10))}
                  />
                </label>
                <label className="text-sm font-semibold text-slate-700">
                  Buffer anti-overbooking (hab)
                  <input
                    type="number"
                    min={0}
                    max={50}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    value={form.safety_buffer_rooms ?? 0}
                    onChange={(e) => handleChange("safety_buffer_rooms", parseInt(e.target.value || "0", 10))}
                  />
                </label>
                <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                  <input
                    type="checkbox"
                    checked={Boolean(form.allow_overbooking)}
                    onChange={(e) => handleChange("allow_overbooking", e.target.checked)}
                  />
                  Permitir overbooking controlado
                </label>
                <label className="text-sm font-semibold text-slate-700">
                  Sobre-asignación máx (%)
                  <input
                    type="number"
                    min={0}
                    max={100}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    value={form.max_overallocation_pct ?? 0}
                    onChange={(e) => handleChange("max_overallocation_pct", parseFloat(e.target.value || "0"))}
                  />
                </label>
                <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                  <input
                    type="checkbox"
                    checked={Boolean(form.ota_autopush_enabled)}
                    onChange={(e) => handleChange("ota_autopush_enabled", e.target.checked)}
                  />
                  Auto publicar no-show/ocupación a OTA
                </label>
                <label className="text-sm font-semibold text-slate-700">
                  Corte no-show (horas)
                  <input
                    type="number"
                    min={0}
                    max={72}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    value={form.no_show_cutoff_hours ?? 24}
                    onChange={(e) => handleChange("no_show_cutoff_hours", parseInt(e.target.value || "0", 10))}
                  />
                </label>
              </div>
            </div>
          </div>

          {/* Visibilidad y permisos */}
          {ownerOnly ? (
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-lg border border-slate-200 p-4">
                <h3 className="text-sm font-semibold text-slate-800">Calendario y permisos</h3>
                <p className="text-xs text-slate-500">Visibilidad para recepcionistas y managers.</p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <label className="text-sm font-semibold text-slate-700">
                    Días pasados visibles al recepcionista
                    <input
                      type="range"
                      min={0}
                      max={90}
                      step={1}
                      className="mt-2 w-full"
                      value={form.receptionist_view_past_days ?? 0}
                      onChange={(e) => handleChange("receptionist_view_past_days", parseInt(e.target.value, 10))}
                    />
                    <span className="text-xs text-slate-600">
                      Puede revisar hasta {form.receptionist_view_past_days ?? 0} días hacia atrás en el calendario.
                    </span>
                  </label>
                  <label className="text-sm font-semibold text-slate-700">
                    Días futuros visibles al recepcionista
                    <input
                      type="range"
                      min={0}
                      max={365}
                      step={1}
                      className="mt-2 w-full"
                      value={form.receptionist_view_future_days ?? 30}
                      onChange={(e) => handleChange("receptionist_view_future_days", parseInt(e.target.value, 10))}
                    />
                    <span className="text-xs text-slate-600">
                      Puede ver reservas hasta {form.receptionist_view_future_days ?? 30} días hacia adelante.
                    </span>
                  </label>
                </div>
                <div className="mt-4 space-y-2">
                  {[
                    ["allow_revenue_manager", "Permitir a managers ver métricas de revenue"],
                    ["allow_revenue_receptionist", "Permitir a recepcionistas ver métricas de revenue"],
                    ["require_document_for_checkin", "Requerir documento para check-in"],
                    ["require_terms_acceptance", "Requerir aceptación de términos en reservas"]
                  ].map(([key, label]) => (
                    <label key={key} className="flex items-center gap-2 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={Boolean((form as Record<string, unknown>)[key])}
                        onChange={(e) => handleChange(key as keyof HotelConfig, e.target.checked)}
                      />
                      {label}
                    </label>
                  ))}
                </div>
              </div>

              <div className="rounded-lg border border-slate-200 p-4">
                <h3 className="text-sm font-semibold text-slate-800">Notificaciones y bloqueos</h3>
                <p className="text-xs text-slate-500">Define alerts y bloqueos rápidos.</p>
                <label className="text-sm font-semibold text-slate-700">
                  Canales en stop-sell (JSON array)
                  <textarea
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    rows={2}
                    value={form.stop_sell_channels ?? ""}
                    onChange={(e) => handleChange("stop_sell_channels", e.target.value)}
                    placeholder='["booking","expedia"]'
                  />
                </label>
                <label className="mt-3 text-sm font-semibold text-slate-700">
                  Notificaciones operativas (JSON)
                  <textarea
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    rows={3}
                    value={form.event_notifications ?? ""}
                    onChange={(e) => handleChange("event_notifications", e.target.value)}
                    placeholder='[{"event":"no_show","channel":"email","quiet_hours":"22-07"}]'
                  />
                </label>
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
              Solo el dueño puede editar las opciones avanzadas de visibilidad y permisos.
            </div>
          )}

          <label className="text-sm font-semibold text-slate-700">
            Políticas adicionales (JSON libre)
            <textarea
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              rows={3}
              value={form.extra_policies ?? ""}
              onChange={(e) => handleChange("extra_policies", e.target.value)}
            />
          </label>

          <div className="flex items-center justify-end gap-3">
            {updateMutation.isError && (
              <p className="text-sm text-rose-700">No se pudo guardar. Revisá conexión o permisos.</p>
            )}
            {updateMutation.isSuccess && (
              <p className="text-sm text-emerald-700">Cambios guardados correctamente.</p>
            )}
            <button
              type="submit"
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
              disabled={updateMutation.isLoading}
            >
              Guardar cambios
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
