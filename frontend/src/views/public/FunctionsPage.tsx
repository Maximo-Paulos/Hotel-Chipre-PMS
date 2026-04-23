import { Seo } from "../../components/Seo";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { PublicButtonLink } from "../../components/marketing/PublicButtonLink";
import { ALLOW_INDEXING, resolveAppUrl } from "../../config/publicUrls";
import { benefitPoints, screenshotFrames, systemPoints } from "../../content/marketing";

const schema = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Inicio", item: "/" },
    { "@type": "ListItem", position: 2, name: "Funciones", item: "/funciones" }
  ]
};

export function FunctionsPage() {
  return (
    <MarketingShell>
      <Seo
        title="Funciones de Hotel Chipre PMS | Reservas, habitaciones, cobros y reportes"
        description="Explora las funciones principales del PMS: reservas, habitaciones, huéspedes, cobros, onboarding e integraciones visibles."
        canonicalPath="/funciones"
        noindex={!ALLOW_INDEXING}
        structuredData={schema}
      />
      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="max-w-3xl space-y-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Funciones</p>
          <h1 className="text-4xl font-semibold tracking-tight text-slate-950">Funcionalidad central para operar el hotel con claridad</h1>
          <p className="text-lg leading-8 text-slate-700">
            La página de funciones debe explicar exactamente qué cubre el sistema hoy, sin prometer módulos que todavía no están cerrados.
          </p>
          <div className="flex flex-wrap gap-3">
            <PublicButtonLink href={resolveAppUrl("/register-owner")} variant="primary">
              Registrarte
            </PublicButtonLink>
            <PublicButtonLink href="/precios" variant="secondary">
              Ver precios
            </PublicButtonLink>
          </div>
        </div>

        <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {systemPoints.map((point) => (
            <article key={point.title} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold text-slate-950">{point.title}</h2>
              <p className="mt-2 text-sm leading-7 text-slate-600">{point.body}</p>
            </article>
          ))}
        </div>

        <div className="mt-10 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Screenshots reales</p>
          <div className="mt-5 grid gap-4 xl:grid-cols-3">
            {screenshotFrames.map((shot) => (
              <figure key={shot.title} className="overflow-hidden rounded-3xl border border-slate-200 bg-slate-50">
                <img src={shot.src} alt={shot.title} loading="lazy" width="1280" height="800" className="h-56 w-full object-cover" />
                <figcaption className="p-4 text-sm leading-6 text-slate-600">{shot.description}</figcaption>
              </figure>
            ))}
          </div>
        </div>

        <div className="mt-10 rounded-[2rem] border border-slate-200 bg-slate-950 p-6 text-white shadow-sm">
          <h2 className="text-2xl font-semibold">¿Qué aporta esto al hotel?</h2>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            {benefitPoints.map((point) => (
              <article key={point.title} className="rounded-2xl border border-white/10 bg-white/5 p-5">
                <h3 className="font-semibold">{point.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-300">{point.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}

export default FunctionsPage;
