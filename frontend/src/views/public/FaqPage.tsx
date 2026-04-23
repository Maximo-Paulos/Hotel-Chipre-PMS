import { Seo } from "../../components/Seo";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { PublicButtonLink } from "../../components/marketing/PublicButtonLink";
import { ALLOW_INDEXING, resolveAppUrl } from "../../config/publicUrls";
import { faqItems } from "../../content/marketing";

export function FaqPage() {
  return (
    <MarketingShell>
      <Seo
        title="FAQ | Hotel Chipre PMS"
        description="Preguntas frecuentes sobre Hotel Chipre PMS, la prueba de 14 días, el acceso y el tratamiento comercial de los planes."
        canonicalPath="/faq"
        noindex={!ALLOW_INDEXING}
        structuredData={{
          "@context": "https://schema.org",
          "@type": "FAQPage",
          mainEntity: faqItems.map((item) => ({
            "@type": "Question",
            name: item.question,
            acceptedAnswer: {
              "@type": "Answer",
              text: item.answer
            }
          }))
        }}
      />
      <section className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="space-y-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">FAQ</p>
          <h1 className="text-4xl font-semibold tracking-tight text-slate-950">Preguntas frecuentes</h1>
          <p className="text-lg leading-8 text-slate-700">
            Respuestas cortas y útiles para entender el producto, la prueba de 14 días y el tratamiento comercial de los planes.
          </p>
        </div>

        <div className="mt-10 space-y-4">
          {faqItems.map((item) => (
            <details key={item.question} className="group rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <summary className="cursor-pointer list-none text-lg font-semibold text-slate-950">{item.question}</summary>
              <p className="mt-3 text-sm leading-7 text-slate-600">{item.answer}</p>
            </details>
          ))}
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
            <PublicButtonLink href="/precios" variant="ghost" className="text-slate-700 hover:text-brand-700">
              Ver planes y precios
            </PublicButtonLink>
            <PublicButtonLink href="/pms-hotelero" variant="ghost" className="text-slate-700 hover:text-brand-700">
              Entender el PMS hotelero
            </PublicButtonLink>
            <PublicButtonLink href="/software-para-hoteles" variant="ghost" className="text-slate-700 hover:text-brand-700">
              Ver software para hoteles
            </PublicButtonLink>
          </div>
        </div>

        <div className="mt-10 rounded-[2rem] border border-slate-200 bg-slate-950 p-6 text-white shadow-sm">
          <h2 className="text-2xl font-semibold">Si querés avanzar, el siguiente paso es simple</h2>
          <div className="mt-4 flex flex-wrap gap-3">
            <PublicButtonLink href={resolveAppUrl("/register-owner")} variant="primary">
              Registrarte
            </PublicButtonLink>
            <PublicButtonLink href="/precios" variant="secondary" className="border-white/15 bg-white/5 text-white hover:border-white/30 hover:text-white">
              Ver precios
            </PublicButtonLink>
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}

export default FaqPage;
