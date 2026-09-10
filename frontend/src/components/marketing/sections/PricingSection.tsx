import { useQuery } from "@tanstack/react-query";

import { fetchPublicPricing, type PublicPricingPlan } from "../../../api/marketing";
import { Section, SectionHeading } from "../Section";

/**
 * Rendered from /api/public/pricing, which the owner edits in the master-admin
 * console. A plan with no published price says "Consultar" rather than showing
 * a number nobody has approved -- that is the state the site ships in.
 */
function formatPrice(plan: PublicPricingPlan): string | null {
  if (!plan.price_amount) return null;
  const amount = Number(plan.price_amount);
  if (!Number.isFinite(amount)) return null;
  if (!plan.currency) return new Intl.NumberFormat("es-AR").format(amount);
  try {
    return new Intl.NumberFormat("es-AR", {
      style: "currency",
      currency: plan.currency,
      maximumFractionDigits: 0
    }).format(amount);
  } catch {
    return `${plan.currency} ${new Intl.NumberFormat("es-AR").format(amount)}`;
  }
}

function PlanColumn({ plan, trialDays }: { plan: PublicPricingPlan; trialDays: number }) {
  const price = formatPrice(plan);

  return (
    <article
      className={`flex flex-col bg-white px-6 py-8 ${
        plan.highlight ? "border-t-2 border-brass-500" : "border-t-2 border-transparent"
      }`}
    >
      <h3 className="font-display text-xl font-semibold text-ink-950">{plan.name}</h3>
      {plan.headline ? <p className="mt-1.5 text-sm leading-6 text-ink-500">{plan.headline}</p> : null}

      <p className="mt-6 flex items-baseline gap-1.5">
        {price ? (
          <>
            <span className="numeric display-wide text-display-sm text-ink-950">{price}</span>
            <span className="text-sm text-ink-500">/ mes</span>
          </>
        ) : (
          <span className="display-wide text-2xl text-ink-950">Consultar</span>
        )}
      </p>

      <dl className="mt-6 space-y-2.5 border-t border-ink-200 pt-5 text-sm text-ink-700">
        {plan.room_limit != null ? (
          <div className="flex justify-between gap-4">
            <dt className="text-ink-500">Habitaciones</dt>
            <dd className="numeric font-medium">hasta {plan.room_limit}</dd>
          </div>
        ) : null}
        {plan.staff_limit != null ? (
          <div className="flex justify-between gap-4">
            <dt className="text-ink-500">Usuarios</dt>
            <dd className="numeric font-medium">hasta {plan.staff_limit}</dd>
          </div>
        ) : null}
        <div className="flex justify-between gap-4">
          <dt className="text-ink-500">Prueba</dt>
          <dd className="numeric font-medium">{trialDays} días</dd>
        </div>
      </dl>

      {plan.features.length ? (
        <ul className="mt-5 space-y-2 text-sm leading-6 text-ink-600">
          {plan.features.map((feature) => (
            <li key={feature} className="flex gap-2.5">
              <span aria-hidden="true" className="mt-2 h-1 w-1 shrink-0 rounded-full bg-brand-500" />
              {feature}
            </li>
          ))}
        </ul>
      ) : null}

      {plan.description ? (
        <p className="mt-5 text-sm leading-6 text-ink-500">{plan.description}</p>
      ) : null}
    </article>
  );
}

export function PricingSection() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["public-pricing"],
    queryFn: ({ signal }) => fetchPublicPricing(signal),
    staleTime: 5 * 60_000
  });

  return (
    <Section id="precios">
      <SectionHeading
        title="Una suscripción por hotel, no una por herramienta."
        lede="Los planes se separan por cuántas habitaciones y cuántas personas del equipo usan el sistema. Estamos cerrando los precios definitivos y los publicamos acá apenas estén."
      />

      {isError ? (
        <p className="mt-10 max-w-xl rounded-panel bg-paper-sunk px-6 py-5 text-base leading-7 text-ink-600">
          No pudimos cargar los planes ahora mismo. Escribinos y te los pasamos por mail.
        </p>
      ) : (
        <div className="mt-12 grid gap-px overflow-hidden rounded-panel bg-ink-200 md:grid-cols-3">
          {isPending
            ? [0, 1, 2].map((index) => (
                <div key={index} className="min-h-[22rem] bg-white px-6 py-8" aria-hidden="true">
                  <div className="h-5 w-24 rounded bg-ink-100" />
                  <div className="mt-7 h-9 w-32 rounded bg-ink-100" />
                  <div className="mt-8 space-y-3">
                    <div className="h-3 w-full rounded bg-ink-100" />
                    <div className="h-3 w-4/5 rounded bg-ink-100" />
                  </div>
                </div>
              ))
            : data?.plans.map((plan) => (
                <PlanColumn key={plan.code} plan={plan} trialDays={data.trial_days} />
              ))}
        </div>
      )}

      <p className="mt-6 max-w-2xl text-sm leading-7 text-ink-500">
        La prueba corre con el sistema completo y no pide tarjeta para empezar.
      </p>
    </Section>
  );
}

export default PricingSection;
