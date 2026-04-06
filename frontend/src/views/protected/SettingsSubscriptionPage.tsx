import React, { useState } from "react";
import { useSubscriptionStatus, useSubscriptionPlans } from "../../hooks/useSubscription";
import { changeSubscriptionPlan } from "../../api/subscription";
import { useSession } from "../../state/session";
import { ApiError } from "../../api/client";

export default function SettingsSubscriptionPage() {
  const { session } = useSession();
  const statusQuery = useSubscriptionStatus();
  const plansQuery = useSubscriptionPlans();
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const currentPlan = statusQuery.data?.plan || "(sin plan)";

  const handleChange = async (planCode: string) => {
    setError(null);
    setToast(null);
    setUpdating(true);
    try {
      await changeSubscriptionPlan(planCode, session);
      await Promise.all([statusQuery.refetch(), plansQuery.refetch()]);
      setToast("Plan actualizado correctamente");
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "No se pudo actualizar el plan";
      setError(msg);
    } finally {
      setUpdating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Suscripción</h1>
        <p className="text-sm text-slate-600">Administrá el plan y el límite de habitaciones.</p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Estado actual</h2>
        {statusQuery.isLoading ? (
          <p className="text-sm text-slate-500">Cargando…</p>
        ) : statusQuery.data ? (
          <ul className="mt-2 text-sm text-slate-700 space-y-1">
            <li><strong>Plan:</strong> {statusQuery.data.plan ?? "Sin plan"}</li>
            <li><strong>Estado:</strong> {statusQuery.data.status}</li>
            <li><strong>Habitaciones usadas:</strong> {statusQuery.data.rooms_in_use}/{statusQuery.data.room_limit}</li>
            <li><strong>Hotel ID:</strong> {statusQuery.data.hotel_id}</li>
          </ul>
        ) : (
          <p className="text-sm text-rose-600">No se pudo obtener el estado.</p>
        )}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Planes disponibles</h2>
        {plansQuery.isLoading ? (
          <p className="text-sm text-slate-500">Cargando…</p>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {plansQuery.data?.map((plan) => {
              const isCurrent = plan.code === statusQuery.data?.plan;
              return (
                <div key={plan.code} className={`rounded-lg border px-4 py-3 ${isCurrent ? "border-brand-300 bg-brand-50" : "border-slate-200"}`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{plan.name}</p>
                      <p className="text-xs text-slate-600">Hasta {plan.room_limit} habitaciones</p>
                      {plan.price_month != null && (
                        <p className="text-xs text-slate-500">${plan.price_month.toFixed(2)} / mes</p>
                      )}
                    </div>
                    <button
                      type="button"
                      disabled={isCurrent || updating}
                      onClick={() => handleChange(plan.code)}
                      className={`rounded-lg px-3 py-2 text-xs font-semibold ${isCurrent ? "bg-slate-100 text-slate-600" : "bg-brand-600 text-white hover:bg-brand-700"} disabled:opacity-60`}
                    >
                      {isCurrent ? "Plan actual" : "Elegir plan"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {error && <p className="mt-3 rounded-md bg-rose-50 p-2 text-rose-700">{error}</p>}
        {toast && <p className="mt-3 rounded-md bg-emerald-50 p-2 text-emerald-700">{toast}</p>}
      </div>
    </div>
  );
}
