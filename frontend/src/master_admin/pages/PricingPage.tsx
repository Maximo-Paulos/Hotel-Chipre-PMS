import { useEffect, useState, type FormEvent } from "react";

import { masterAdminFetch } from "../api";

/**
 * The public pricing table, edited here and rendered verbatim by the landing
 * page. Leaving the price blank is a supported state, not an unfinished one:
 * the site shows "Consultar" instead of a number nobody has approved.
 */
type PricingPlan = {
  code: string;
  name: string;
  is_public: boolean;
  sort_order: number;
  price_amount: string | null;
  currency: string | null;
  billing_period: string;
  headline: string | null;
  description: string | null;
  features: string[];
  room_limit: number | null;
  staff_limit: number | null;
  cta_label: string | null;
  cta_kind: string;
  highlight: boolean;
};

const EMPTY_PLAN: PricingPlan = {
  code: "",
  name: "",
  is_public: true,
  sort_order: 0,
  price_amount: null,
  currency: null,
  billing_period: "month",
  headline: null,
  description: null,
  features: [],
  room_limit: null,
  staff_limit: null,
  cta_label: null,
  cta_kind: "early_access",
  highlight: false
};

const field = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm";
const label = "block text-xs font-semibold uppercase tracking-wide text-slate-500";

const asNumber = (value: string): number | null => {
  const parsed = parseInt(value, 10);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : null;
};

export function MasterAdminPricingPage() {
  const [plans, setPlans] = useState<PricingPlan[]>([]);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    masterAdminFetch<{ plans: PricingPlan[] }>("/api/master-admin/pricing/plans")
      .then((data) => {
        if (!cancelled) setPlans(data.plans);
      })
      .catch(() => {
        if (!cancelled) setMessage("No se pudieron cargar los planes.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const update = (index: number, patch: Partial<PricingPlan>) =>
    setPlans((current) => current.map((plan, i) => (i === index ? { ...plan, ...patch } : plan)));

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setMessage(null);
    try {
      const saved = await masterAdminFetch<{ plans: PricingPlan[] }>(
        "/api/master-admin/pricing/plans",
        { method: "PUT", data: { plans } }
      );
      setPlans(saved.plans);
      setMessage("Precios publicados. La landing los toma en el próximo minuto.");
    } catch {
      setMessage("No se pudieron guardar los planes.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Precios públicos</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-600">
          Esto es lo que muestra hotels-pms.com. Si dejás el precio vacío, la landing muestra
          &laquo;Consultar&raquo; en vez de un número. Los topes de habitaciones y usuarios deberían
          coincidir con los que el sistema realmente aplica.
        </p>
      </header>

      {message ? (
        <p className="rounded-lg bg-slate-100 px-4 py-3 text-sm text-slate-700">{message}</p>
      ) : null}

      <form onSubmit={submit} className="space-y-5">
        {plans.map((plan, index) => (
          <section key={plan.code || index} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <label className={label} htmlFor={`code-${index}`}>Código</label>
                <input
                  id={`code-${index}`}
                  className={field}
                  value={plan.code}
                  onChange={(e) => update(index, { code: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className={label} htmlFor={`name-${index}`}>Nombre</label>
                <input
                  id={`name-${index}`}
                  className={field}
                  value={plan.name}
                  onChange={(e) => update(index, { name: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className={label} htmlFor={`price-${index}`}>Precio por mes</label>
                <input
                  id={`price-${index}`}
                  className={field}
                  inputMode="decimal"
                  placeholder="vacío = Consultar"
                  value={plan.price_amount ?? ""}
                  onChange={(e) => update(index, { price_amount: e.target.value.trim() || null })}
                />
              </div>
              <div>
                <label className={label} htmlFor={`currency-${index}`}>Moneda</label>
                <input
                  id={`currency-${index}`}
                  className={field}
                  maxLength={3}
                  placeholder="ARS"
                  value={plan.currency ?? ""}
                  onChange={(e) => update(index, { currency: e.target.value.trim().toUpperCase() || null })}
                />
              </div>

              <div>
                <label className={label} htmlFor={`rooms-${index}`}>Habitaciones</label>
                <input
                  id={`rooms-${index}`}
                  className={field}
                  inputMode="numeric"
                  value={plan.room_limit ?? ""}
                  onChange={(e) => update(index, { room_limit: asNumber(e.target.value) })}
                />
              </div>
              <div>
                <label className={label} htmlFor={`staff-${index}`}>Usuarios</label>
                <input
                  id={`staff-${index}`}
                  className={field}
                  inputMode="numeric"
                  value={plan.staff_limit ?? ""}
                  onChange={(e) => update(index, { staff_limit: asNumber(e.target.value) })}
                />
              </div>
              <div>
                <label className={label} htmlFor={`order-${index}`}>Orden</label>
                <input
                  id={`order-${index}`}
                  className={field}
                  inputMode="numeric"
                  value={plan.sort_order}
                  onChange={(e) => update(index, { sort_order: asNumber(e.target.value) ?? 0 })}
                />
              </div>
              <div className="flex items-end gap-4 text-sm text-slate-700">
                <label className="inline-flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={plan.is_public}
                    onChange={(e) => update(index, { is_public: e.target.checked })}
                  />
                  Visible
                </label>
                <label className="inline-flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={plan.highlight}
                    onChange={(e) => update(index, { highlight: e.target.checked })}
                  />
                  Destacado
                </label>
              </div>

              <div className="sm:col-span-2 lg:col-span-4">
                <label className={label} htmlFor={`headline-${index}`}>Bajada</label>
                <input
                  id={`headline-${index}`}
                  className={field}
                  value={plan.headline ?? ""}
                  onChange={(e) => update(index, { headline: e.target.value || null })}
                />
              </div>
              <div className="sm:col-span-2 lg:col-span-4">
                <label className={label} htmlFor={`features-${index}`}>
                  Qué incluye (una por línea)
                </label>
                <textarea
                  id={`features-${index}`}
                  className={`${field} min-h-24`}
                  value={plan.features.join("\n")}
                  onChange={(e) =>
                    update(index, {
                      features: e.target.value.split("\n").map((line) => line.trim()).filter(Boolean)
                    })
                  }
                />
              </div>
            </div>
          </section>
        ))}

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            {saving ? "Publicando…" : "Publicar precios"}
          </button>
          <button
            type="button"
            onClick={() => setPlans((current) => [...current, { ...EMPTY_PLAN, sort_order: (current.length + 1) * 10 }])}
            className="rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700"
          >
            Agregar plan
          </button>
        </div>
      </form>
    </div>
  );
}

export default MasterAdminPricingPage;
