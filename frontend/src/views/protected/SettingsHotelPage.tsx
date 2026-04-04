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

          <div className="grid gap-3 md:grid-cols-3">
            <label className="text-sm font-semibold text-slate-700">
              Depósito (%)
              <input
                type="number"
                min={0}
                max={100}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                value={form.deposit_percentage ?? 0}
                onChange={(e) => handleChange("deposit_percentage", parseFloat(e.target.value))}
              />
            </label>
            <label className="text-sm font-semibold text-slate-700">
              Cancelación gratis (horas)
              <input
                type="number"
                min={0}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                value={form.free_cancellation_hours ?? 0}
                onChange={(e) => handleChange("free_cancellation_hours", parseInt(e.target.value, 10))}
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
                onChange={(e) => handleChange("cancellation_penalty_percentage", parseFloat(e.target.value))}
              />
            </label>
          </div>

          <div className="grid gap-2 md:grid-cols-3">
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

          <label className="text-sm font-semibold text-slate-700">
            Políticas adicionales
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
