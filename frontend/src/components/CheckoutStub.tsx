import type { SubscriptionPlan } from "../api/subscription";

type CheckoutStubProps = {
  open: boolean;
  plan: SubscriptionPlan | null;
  onClose: () => void;
};

export function CheckoutStub({ open, plan, onClose }: CheckoutStubProps) {
  if (!open || !plan) return null;

  const price =
    plan.price_month != null && plan.price_month >= 0 ? `$${plan.price_month}/mes` : "A medida (contacto humano)";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-4 py-6">
      <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-brand-700">Checkout en preparación</p>
            <h3 className="text-lg font-semibold text-slate-900">{plan.name}</h3>
            <p className="text-xs text-slate-500">Plan {plan.code.toUpperCase()}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-sm text-slate-500 hover:text-slate-800"
            aria-label="Cerrar modal de checkout"
          >
            ×
          </button>
        </div>

        <div className="space-y-3 px-5 py-4 text-sm text-slate-700">
          <p>
            Estamos preparando el flujo de pago real (PayPal / links bancarios). Este paso es solo una maqueta para
            validar la UX: no se realizará ningún cobro ni cambio de plan en el backend.
          </p>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Referencia de precio</p>
            <p className="text-base font-semibold text-slate-900">{price}</p>
            <p className="text-xs text-slate-500">Usamos valores de muestra mientras se conecta el checkout real.</p>
          </div>

          {plan.features?.length ? (
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Incluye</p>
              <ul className="mt-1 space-y-1 text-sm text-slate-700">
                {plan.features.slice(0, 4).map((feature) => (
                  <li key={feature} className="flex items-start gap-2">
                    <span className="mt-1 h-2 w-2 rounded-full bg-brand-500" aria-hidden />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-slate-200 px-5 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300"
          >
            Volver
          </button>
          <button
            type="button"
            disabled
            className="rounded-lg border border-slate-200 bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-500"
            title="Aún no habilitado"
          >
            Pago en preparación
          </button>
        </div>
      </div>
    </div>
  );
}
