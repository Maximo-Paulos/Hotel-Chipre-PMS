import { Seo } from "../../components/Seo";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { PublicButtonLink } from "../../components/marketing/PublicButtonLink";
import { ALLOW_INDEXING, resolveAppUrl } from "../../config/publicUrls";
import { heroBullets, positioning } from "../../content/marketing";

const schema = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Inicio", item: "/" },
    { "@type": "ListItem", position: 2, name: "PMS hotelero", item: "/pms-hotelero" }
  ]
};

export function PmsHoteleroPage() {
  return (
    <MarketingShell>
      <Seo
        title="PMS hotelero | Hotel Chipre PMS"
        description="Sistema de gestión hotelera para hoteles independientes que centraliza reservas, habitaciones, huéspedes y cobros."
        canonicalPath="/pms-hotelero"
        noindex={!ALLOW_INDEXING}
        structuredData={schema}
      />

      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="max-w-3xl space-y-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">PMS hotelero</p>
          <h1 className="text-4xl font-semibold tracking-tight text-slate-950">Un PMS hotelero claro para centralizar la operación diaria</h1>
          <p className="text-lg leading-8 text-slate-700">{positioning}</p>
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
          {heroBullets.map((bullet) => (
            <article key={bullet} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <p className="text-sm leading-7 text-slate-700">{bullet}</p>
            </article>
          ))}
        </div>
      </section>
    </MarketingShell>
  );
}

export default PmsHoteleroPage;
