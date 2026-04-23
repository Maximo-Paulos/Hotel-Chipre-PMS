import { Seo } from "../../components/Seo";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { PublicButtonLink } from "../../components/marketing/PublicButtonLink";
import { ALLOW_INDEXING, resolveAppUrl } from "../../config/publicUrls";
import { benefitPoints } from "../../content/marketing";

const schema = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Inicio", item: "/" },
    { "@type": "ListItem", position: 2, name: "Software para hoteles", item: "/software-para-hoteles" }
  ]
};

export function SoftwareParaHotelesPage() {
  return (
    <MarketingShell>
      <Seo
        title="Software para hoteles | Hotel Chipre PMS"
        description="Software para hoteles pensado para ordenar la operación, con onboarding guiado, planes Starter, Pro y Ultra."
        canonicalPath="/software-para-hoteles"
        noindex={!ALLOW_INDEXING}
        structuredData={schema}
      />
      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="max-w-3xl space-y-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Software para hoteles</p>
          <h1 className="text-4xl font-semibold tracking-tight text-slate-950">Software para hoteles que necesitan orden y control operativo</h1>
          <p className="text-lg leading-8 text-slate-700">
            La propuesta debe hablarle al hotel que hoy todavía opera con herramientas separadas y necesita una base web más clara.
          </p>
          <div className="flex flex-wrap gap-3">
            <PublicButtonLink href="/precios" variant="primary">
              Ver precios
            </PublicButtonLink>
            <PublicButtonLink href={resolveAppUrl("/register-owner")} variant="secondary">
              Registrarte
            </PublicButtonLink>
          </div>
        </div>

        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {benefitPoints.map((point) => (
            <article key={point.title} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold text-slate-950">{point.title}</h2>
              <p className="mt-2 text-sm leading-7 text-slate-600">{point.body}</p>
            </article>
          ))}
        </div>
      </section>
    </MarketingShell>
  );
}

export default SoftwareParaHotelesPage;
