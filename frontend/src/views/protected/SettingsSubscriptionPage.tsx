import React, { useMemo, useState } from "react";

import { ApiError } from "../../api/client";
import { CheckoutStub } from "../../components/CheckoutStub";
import {
  changeSubscriptionPlan,
  startTrial,
  type SubscriptionPlan
} from "../../api/subscription";
import { useSubscriptionPlans, useSubscriptionStatus } from "../../hooks/useSubscription";
import { useSession } from "../../state/session";

const WRITE_ENABLED_STATUSES = ["active", "trialing", "demo", "comped"];

const statusTone = (status?: string | null) => {
  if (status === "active" || status === "trialing" || status === "comped" || status === "demo") {
    return "bg-emerald-50 text-emerald-700";
  }
  if (status === "suspended") {
    return "bg-rose-50 text-rose-700";
  }
  return "bg-amber-100 text-amber-800";
};

export default function SettingsSubscriptionPage() {
  const { session } = useSession();
  const statusQuery = useSubscriptionStatus();
  const plansQuery = useSubscriptionPlans();
  const subscription = statusQuery.data;
  const availablePlans = useMemo(
    () => (plansQuery.data?.length ? plansQuery.data : subscription?.available_plans) ?? [],
    [plansQuery.data, subscription?.available_plans]
  );
  const isMock = subscription?.source === "mock" || availablePlans.some((plan) => plan.mock);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<SubscriptionPlan | null>(null);
  const [checkoutOpen, setCheckoutOpen] = useState(false);

  const limits = Array.isArray(subscription?.limits) ? subscription?.limits : [];
  const currentPlan = subscription?.plan || "(sin plan)";
  const currentPlanData = useMemo(
    () => availablePlans.find((plan) => plan.code === subscription?.plan) ?? null,
    [availablePlans, subscription?.plan]
  );
  const checkoutPlan = useMemo(
    () => selectedPlan ?? currentPlanData ?? availablePlans[0] ?? null,
    [availablePlans, currentPlanData, selectedPlan]
  );

  const status = subscription?.status ?? null;
  const writeBlocked = subscription?.can_write === false;
  const isSuspended = status === "suspended";
  const isComped = status === "comped";
  const isTrialing = status === "trialing";
  const isOperational = Boolean(status && WRITE_ENABLED_STATUSES.includes(status));
  const showTrialButton = !isTrialing && !isComped && !updating;

  const handleChange = async (planCode: string) => {
    if (writeBlocked && !isSuspended) {
      setError("Suscripción en modo solo lectura. Reactivá el plan para habilitar cambios.");
      return;
    }
    setError(null);
    setToast(null);
    setUpdating(true);
    try {
      await changeSubscriptionPlan(planCode, session);
      await Promise.all([statusQuery.refetch(), plansQuery.refetch()]);
      setToast("Plan actualizado correctamente.");
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "No se pudo actualizar el plan.";
      setError(msg);
    } finally {
      setUpdating(false);
    }
  };

  const handleStartTrial = async (planCode: string) => {
    setError(null);
    setToast(null);
    setUpdating(true);
    try {
      await startTrial(planCode, session);
      await Promise.all([statusQuery.refetch(), plansQuery.refetch()]);
      setToast("Prueba gratuita iniciada.");
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "No se pudo iniciar la prueba gratuita.";
      setError(msg);
    } finally {
      setUpdating(false);
    }
  };

  const handleOpenCheckout = (plan?: SubscriptionPlan | null) => {
    const fallback = plan ?? currentPlanData ?? availablePlans[0] ?? null;
    setSelectedPlan(fallback);
    setCheckoutOpen(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Suscripción</h1>
          <p className="text-sm text-slate-600">Administrá el plan, el estado operativo y los límites del PMS.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {isMock && (
            <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
              Modo mock/offline
            </span>
          )}
          {isTrialing && typeof subscription?.trial_remaining_days === "number" && (
            <span className="inline-flex items-center rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700">
              Prueba gratis · {subscription.trial_remaining_days} días restantes
            </span>
          )}
          {isComped && (
            <span className="inline-flex items-center rounded-full bg-violet-50 px-3 py-1 text-xs font-semibold text-violet-700">
              Comped activo
            </span>
          )}
        </div>
      </div>

      {isSuspended && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">
          <p>La suscripción está suspendida y el hotel quedó en modo restringido.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => handleOpenCheckout(currentPlanData)}
              className="rounded-lg bg-rose-600 px-3 py-2 text-xs font-semibold text-white hover:bg-rose-700"
            >
              Reactivar con checkout demo
            </button>
            {showTrialButton && (
              <button
                type="button"
                onClick={() => handleStartTrial("pro")}
                className="rounded-lg border border-rose-300 bg-white px-3 py-2 text-xs font-semibold text-rose-800 hover:border-rose-400"
              >
                Iniciar prueba gratis
              </button>
            )}
          </div>
        </div>
      )}

      {(writeBlocked || (status && !isOperational && !isSuspended)) && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p>
            {writeBlocked
              ? "Suscripción en modo solo lectura (can_write=false)."
              : "La suscripción no está operativa y puede bloquear acciones de escritura."}
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => handleOpenCheckout(currentPlanData)}
              className="rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs font-semibold text-amber-900 hover:border-amber-400"
            >
              Reactivar
            </button>
            {showTrialButton && (
              <button
                type="button"
                onClick={() => handleStartTrial("pro")}
                className="rounded-lg border border-amber-200 px-3 py-2 text-xs font-semibold text-amber-800 hover:border-amber-300"
              >
                Iniciar prueba gratis
              </button>
            )}
          </div>
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-900">Estado actual</h2>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
              Plan {currentPlan}
            </span>
            {showTrialButton && (
              <button
                type="button"
                onClick={() => handleStartTrial("pro")}
                className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 hover:border-sky-300"
              >
                Iniciar prueba gratis
              </button>
            )}
          </div>
        </div>
        {statusQuery.isLoading ? (
          <p className="text-sm text-slate-500">Cargando...</p>
        ) : subscription ? (
          <>
            <ul className="mt-3 space-y-2 text-sm text-slate-700">
              <li className="flex items-center gap-2">
                <strong>Estado:</strong>
                <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusTone(subscription.status)}`}>
                  {subscription.status ?? "desconocido"}
                </span>
              </li>
              <li>
                <strong>Permiso de escritura:</strong> {subscription.can_write === false ? "Bloqueado" : "Habilitado"}
              </li>
              <li>
                <strong>Habitaciones usadas:</strong> {subscription.rooms_in_use}/{subscription.room_limit}
              </li>
              <li>
                <strong>Staff incluido:</strong> {subscription.staff_limit ?? "sin dato"}
              </li>
              <li>
                <strong>Hotel ID:</strong> {subscription.hotel_id ?? "-"}
              </li>
              {subscription.trial_end_at && (
                <li>
                  <strong>Fin de prueba:</strong> {new Date(subscription.trial_end_at).toLocaleDateString("es-AR")}
                </li>
              )}
              {isMock && <li className="text-amber-700">Fuente: mock/offline.</li>}
            </ul>

            {limits.length > 0 && (
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {limits.map((limit) => {
                  const label = limit.label ?? limit.code ?? "Límite";
                  const used =
                    typeof limit.used === "number"
                      ? limit.used
                      : limit.code === "rooms"
                        ? subscription.rooms_in_use
                        : undefined;
                  const max = typeof limit.limit === "number" ? limit.limit : null;
                  const pct =
                    max && typeof used === "number" && max > 0 ? Math.min(100, Math.round((used / max) * 100)) : null;
                  return (
                    <div
                      key={`${label}-${limit.code ?? "custom"}`}
                      className="rounded-lg border border-slate-200 bg-slate-50 p-3"
                    >
                      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
                      <p className="text-sm font-semibold text-slate-900">
                        {used ?? "-"} / {max ?? "sin tope"}
                      </p>
                      {pct !== null && (
                        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-white">
                          <div className="h-full bg-brand-500" style={{ width: `${pct}%` }} />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </>
        ) : (
          <p className="text-sm text-rose-600">No se pudo obtener el estado.</p>
        )}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Planes disponibles</h2>
          <a
            className="text-sm font-semibold text-brand-700 hover:underline"
            href="/pricing"
            target="_blank"
            rel="noreferrer"
          >
            Ver landing de precios
          </a>
        </div>
        {plansQuery.isLoading ? (
          <p className="text-sm text-slate-500">Cargando...</p>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {availablePlans.map((plan) => {
              const isCurrent = plan.code === subscription?.plan;
              const canStartTrial = showTrialButton && plan.code !== "starter";
              return (
                <div
                  key={plan.code}
                  className={`rounded-lg border px-4 py-3 ${
                    isCurrent ? "border-brand-300 bg-brand-50" : "border-slate-200"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{plan.name}</p>
                      <p className="text-xs text-slate-600">Hasta {plan.room_limit} habitaciones</p>
                      {plan.price_month != null && <p className="text-xs text-slate-500">${plan.price_month} / mes</p>}
                      {plan.features && (
                        <ul className="mt-1 space-y-1 text-xs text-slate-600">
                          {plan.features.slice(0, 3).map((feature) => (
                            <li key={feature}>· {feature}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        disabled={isCurrent || updating || (writeBlocked && !isSuspended)}
                        onClick={() => handleChange(plan.code)}
                        className={`rounded-lg px-3 py-2 text-xs font-semibold ${
                          isCurrent ? "bg-slate-100 text-slate-600" : "bg-brand-600 text-white hover:bg-brand-700"
                        } disabled:cursor-not-allowed disabled:opacity-60`}
                      >
                        {writeBlocked && !isSuspended ? "Bloqueado" : isCurrent ? "Plan actual" : "Elegir plan"}
                      </button>
                      {canStartTrial && (
                        <button
                          type="button"
                          disabled={updating}
                          onClick={() => handleStartTrial(plan.code)}
                          className="rounded-lg border border-sky-200 px-3 py-2 text-xs font-semibold text-sky-700 hover:border-sky-300"
                        >
                          Iniciar prueba gratis
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => handleOpenCheckout(plan)}
                        className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:border-brand-300 hover:text-brand-700"
                      >
                        Checkout demo
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {error && <p className="mt-3 rounded-md bg-rose-50 p-2 text-rose-700">{error}</p>}
        {toast && <p className="mt-3 rounded-md bg-emerald-50 p-2 text-emerald-700">{toast}</p>}
      </div>

      <CheckoutStub open={checkoutOpen} plan={checkoutPlan} onClose={() => setCheckoutOpen(false)} />
    </div>
  );
}
