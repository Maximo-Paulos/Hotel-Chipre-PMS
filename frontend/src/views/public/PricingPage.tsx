import { useState } from "react";
import { Link } from "react-router-dom";
import { CheckoutStub } from "../../components/CheckoutStub";
import { FALLBACK_PLANS, useSubscriptionPlans } from "../../hooks/useSubscription";
import type { SubscriptionPlan } from "../../api/subscription";

type PlanCardProps = {
  plan: SubscriptionPlan;
  onSelect: (plan: SubscriptionPlan) => void;
};

function PlanCard({ plan, onSelect }: PlanCardProps) {
  return (
    <div
      className={`relative flex h-full flex-col rounded-2xl border bg-white/90 p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-md ${
        plan.highlight ? "border-brand-300 ring-2 ring-brand-100" : "border-slate-200"
      }`}
    >
      {plan.badge && (
        <span className="absolute -top-3 left-4 rounded-full bg-brand-600 px-3 py-1 text-xs font-semibold text-white shadow-sm">
          {plan.badge}
        </span>
      )}
      <div className="mb-4 space-y-1">
        <p className="text-sm font-semibold text-slate-500">{plan.code.toUpperCase()}</p>
        <h3 className="text-xl font-semibold text-slate-900">{plan.name}</h3>
        {plan.description && <p className="text-sm text-slate-600">{plan.description}</p>}
      </div>
      <div className="mb-4 flex items-baseline gap-2">
        {plan.price_month != null ? (
          <>
            <span className="text-3xl font-bold text-slate-900">${plan.price_month}</span>
            <span className="text-sm text-slate-500">/ mes</span>
          </>
        ) : (
          <span className="text-lg font-semibold text-slate-800">A medida</span>
        )}
      </div>
      <p className="text-sm text-slate-500">Hasta {plan.room_limit} habitaciones operables.</p>
      <ul className="mt-4 space-y-2 text-sm text-slate-700">
        {(plan.features ?? []).map((feature) => (
          <li key={feature} className="flex items-start gap-2">
            <span className="mt-1 h-2 w-2 rounded-full bg-brand-500" aria-hidden />
            <span>{feature}</span>
          </li>
        ))}
      </ul>
      <div className="mt-auto pt-6">
        <button
          type="button"
          onClick={() => onSelect(plan)}
          className={`w-full rounded-xl px-4 py-2 text-sm font-semibold transition ${
            plan.highlight
              ? "bg-brand-600 text-white hover:bg-brand-700"
              : "border border-slate-200 text-slate-800 hover:border-brand-300 hover:text-brand-700"
          }`}
        >
          {plan.price_month === 0 ? "Probar gratis" : "Checkout (demo)"}
        </button>
        <p className="mt-2 text-center text-xs text-slate-500">Checkout falso (modo demo).</p>
      </div>
    </div>
  );
}

export function PricingPage() {
  const { data: plansData = FALLBACK_PLANS, isPlaceholderData } = useSubscriptionPlans();
  const plans = plansData?.length ? plansData : FALLBACK_PLANS;
  const usingMock = isPlaceholderData || plans.some((p) => p.mock);
  const [selectedPlan, setSelectedPlan] = useState<SubscriptionPlan | null>(null);
  const [checkoutOpen, setCheckoutOpen] = useState(false);

  const handleFakeCheckout = (plan: SubscriptionPlan) => {
    setSelectedPlan(plan);
    setCheckoutOpen(true);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <Link to="/" className="text-lg font-semibold text-slate-900">
            Hotel Chipre PMS
          </Link>
          <div className="flex items-center gap-3 text-sm font-semibold">
            <Link to="/login" className="text-slate-700 hover:text-brand-700">
              Ingresar
            </Link>
            <Link
              to="/register-owner"
              className="rounded-full bg-brand-600 px-4 py-2 text-white shadow-sm hover:bg-brand-700"
            >
              Crear cuenta
            </Link>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-4 py-12 lg:py-16">
        <div className="grid gap-10 lg:grid-cols-2 lg:items-center">
          <div className="space-y-4">
            <p className="inline-flex rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700">
              Nuevos planes beta
            </p>
            <h1 className="text-3xl font-bold text-slate-900 sm:text-4xl">
              Reservas, operación y cobros en un solo lugar.
            </h1>
            <p className="text-lg text-slate-700">
              Diseñamos planes simples para hoteles de pocas habitaciones hasta propiedades con operación más compleja.
              Los precios son de muestra y el checkout está en modo demo para no tocar producción.
            </p>
            <div className="flex flex-wrap gap-3 text-sm text-slate-700">
              <span className="flex items-center gap-2 rounded-full bg-white px-3 py-2 shadow-sm">
                <span className="h-2 w-2 rounded-full bg-emerald-500" /> Datos mock seguros
              </span>
              <span className="flex items-center gap-2 rounded-full bg-white px-3 py-2 shadow-sm">
                <span className="h-2 w-2 rounded-full bg-brand-500" /> Cambiá de plan sin fricción
              </span>
              <span className="flex items-center gap-2 rounded-full bg-white px-3 py-2 shadow-sm">
                <span className="h-2 w-2 rounded-full bg-slate-500" /> En camino: checkout real
              </span>
            </div>
          </div>
          <div className="rounded-3xl border border-slate-200 bg-white/90 p-6 shadow-lg">
            <p className="text-sm font-semibold text-slate-600">Resumen rápido</p>
            <ul className="mt-3 space-y-2 text-sm text-slate-700">
              <li>· Header X-User-Id y X-Hotel-Id siempre presentes.</li>
              <li>· Room limit por plan para evitar sobreventa.</li>
              <li>· Bandeja de estado de suscripción con can_write.</li>
            </ul>
            <p className="mt-4 rounded-lg bg-brand-50 px-4 py-3 text-sm text-brand-800">
              {usingMock
                ? "Mostrando planes mock porque el backend no respondió."
                : "Datos obtenidos del backend. ¡Listo para conectar checkout!"}
            </p>
          </div>
        </div>

        <div className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {plans.map((plan) => (
            <PlanCard key={plan.code} plan={plan} onSelect={handleFakeCheckout} />
          ))}
        </div>

        <div className="mt-14 grid gap-6 rounded-2xl border border-slate-200 bg-white/90 p-6 shadow-sm md:grid-cols-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Integraciones</p>
            <p className="mt-1 text-sm text-slate-700">API REST JSON · OTA (beta) · Webhooks</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Soporte</p>
            <p className="mt-1 text-sm text-slate-700">Email y chat. SLA según plan.</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Seguridad</p>
            <p className="mt-1 text-sm text-slate-700">JWT + headers X-User-Id / X-Hotel-Id.</p>
          </div>
        </div>
      </div>

      <CheckoutStub open={checkoutOpen} plan={selectedPlan} onClose={() => setCheckoutOpen(false)} />
    </div>
  );
}

export default PricingPage;
