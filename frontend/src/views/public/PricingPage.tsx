import { Seo } from "../../components/Seo";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { PublicButtonLink } from "../../components/marketing/PublicButtonLink";
import { ALLOW_INDEXING, resolveAppUrl, resolveSalesContactUrl } from "../../config/publicUrls";
import { faqItems, pricingCards } from "../../content/marketing";

export function PricingPage() {
  return (
    <MarketingShell>
      <Seo
        title="Precios de Hotel Chipre PMS | Starter, Pro y Ultra"
        description="Conoce los planes Starter, Pro y Ultra de Hotel Chipre PMS. Starter incluye prueba de 14 días; Pro y Ultra se gestionan con ventas."
        canonicalPath="/precios"
        noindex={!ALLOW_INDEXING}
      />

      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="max-w-3xl space-y-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Precios</p>
          <h1 className="text-4xl font-semibold tracking-tight text-slate-950">Planes simples, claros y orientados a operación real</h1>
          <p className="text-lg leading-8 text-slate-700">
            Starter incluye prueba de 14 días. Pro y Ultra se gestionan con ventas hasta cerrar el flujo de compra online.
          </p>
          <div className="flex flex-wrap gap-3">
            <PublicButtonLink href={resolveAppUrl("/register-owner")} variant="primary">
              Registrarte
            </PublicButtonLink>
            <PublicButtonLink href={resolveAppUrl("/login")} variant="secondary">
              Ingresar
            </PublicButtonLink>
          </div>
        </div>

        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {pricingCards.map((plan) => (
            <article key={plan.code} className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">{plan.code}</p>
              <h2 className="mt-2 text-2xl font-semibold text-slate-950">{plan.name}</h2>
              <p className="mt-3 text-sm leading-7 text-slate-600">{plan.description}</p>
              <div className="mt-6">
                <PublicButtonLink
                  href={plan.code === "starter" ? resolveAppUrl("/register-owner") : resolveSalesContactUrl()}
                  variant={plan.code === "starter" ? "primary" : "secondary"}
                >
                  {plan.cta}
                </PublicButtonLink>
              </div>
            </article>
          ))}
        </div>

        <div className="mt-10 rounded-[2rem] border border-slate-200 bg-slate-950 p-6 text-white shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-300">Regla de pricing</p>
          <ul className="mt-4 grid gap-3 text-sm leading-6 text-slate-300 md:grid-cols-3">
            <li>No publicar detalle fino no cerrado.</li>
            <li>No publicar integraciones específicas en las cards.</li>
            <li>No publicar límites, staff limits, Stripe ni capacidades avanzadas no cerradas.</li>
          </ul>
        </div>

        <div className="mt-10 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Seguir explorando</p>
          <div className="mt-4 flex flex-wrap gap-3 text-sm font-medium">
            <PublicButtonLink href="/" variant="ghost" className="text-slate-700 hover:text-brand-700">
              Volver al inicio
            </PublicButtonLink>
            <PublicButtonLink href="/funciones" variant="ghost" className="text-slate-700 hover:text-brand-700">
              Ver qué cubre el sistema
            </PublicButtonLink>
            <PublicButtonLink href="/pms-hotelero" variant="ghost" className="text-slate-700 hover:text-brand-700">
              Entender el PMS hotelero
            </PublicButtonLink>
            <PublicButtonLink href="/software-para-hoteles" variant="ghost" className="text-slate-700 hover:text-brand-700">
              Ver software para hoteles
            </PublicButtonLink>
            <PublicButtonLink href="/faq" variant="ghost" className="text-slate-700 hover:text-brand-700">
              Resolver dudas frecuentes
            </PublicButtonLink>
          </div>
        </div>

        <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_1fr]">
          <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">FAQ</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-950">Objeciones frecuentes</h2>
            <div className="mt-4 space-y-3">
              {faqItems.slice(2, 7).map((item) => (
                <details key={item.question} className="group rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <summary className="cursor-pointer list-none text-sm font-semibold text-slate-950">{item.question}</summary>
                  <p className="mt-3 text-sm leading-7 text-slate-600">{item.answer}</p>
                </details>
              ))}
            </div>
          </div>

          <div className="rounded-[2rem] border border-slate-200 bg-slate-950 p-6 text-white shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-300">CTA final</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight">Hablar con ventas para planes pagos</h2>
            <p className="mt-3 text-sm leading-7 text-slate-300">
              Mientras la compra online no esté abierta, esta es la opción correcta para Pro y Ultra.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <PublicButtonLink href={resolveSalesContactUrl()} variant="primary">
                Hablar con ventas
              </PublicButtonLink>
              <PublicButtonLink
                href={resolveAppUrl("/register-owner")}
                variant="secondary"
                className="border-white/15 bg-white/5 text-white hover:border-white/30 hover:text-white"
              >
                Registrarte
              </PublicButtonLink>
            </div>
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}

export default PricingPage;
