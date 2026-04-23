import { Seo } from "../../components/Seo";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { PublicButtonLink } from "../../components/marketing/PublicButtonLink";
import { ALLOW_INDEXING, resolveAppUrl } from "../../config/publicUrls";
import { heroBullets, positioning, systemPoints } from "../../content/marketing";

const pmsPoints = [
  {
    title: "Base operativa",
    body: "Un PMS reúne reservas, habitaciones, huéspedes y cobros en una sola base de trabajo."
  },
  {
    title: "Menos fricción",
    body: "El hotel deja de depender de planillas y mensajes sueltos para seguir la operación del día."
  },
  {
    title: "Más claridad",
    body: "Recepción, operación y dirección trabajan sobre la misma información."
  }
];

export function PmsHoteleroPage() {
  return (
    <MarketingShell>
      <Seo
        title="PMS hotelero | Hotel Chipre PMS"
        description="Sistema de gestión hotelera para hoteles independientes que centraliza reservas, habitaciones, huéspedes y cobros."
        canonicalPath="/pms-hotelero"
        noindex={!ALLOW_INDEXING}
      />

      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="max-w-3xl space-y-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">PMS hotelero</p>
          <h1 className="text-4xl font-semibold tracking-tight text-slate-950">
            Un PMS hotelero claro para centralizar la operación diaria
          </h1>
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
          {pmsPoints.map((point) => (
            <article key={point.title} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold text-slate-950">{point.title}</h2>
              <p className="mt-2 text-sm leading-7 text-slate-600">{point.body}</p>
            </article>
          ))}
        </div>

        <div className="mt-10 grid gap-4 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm md:grid-cols-3">
          {systemPoints.map((point) => (
            <article key={point.title} className="rounded-2xl bg-slate-50 p-5">
              <h3 className="text-lg font-semibold text-slate-900">{point.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">{point.body}</p>
            </article>
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
            <PublicButtonLink href="/software-para-hoteles" variant="ghost" className="text-slate-700 hover:text-brand-700">
              Ver software para hoteles
            </PublicButtonLink>
            <PublicButtonLink href="/faq" variant="ghost" className="text-slate-700 hover:text-brand-700">
              Resolver dudas frecuentes
            </PublicButtonLink>
          </div>
        </div>

        <div className="mt-10 rounded-[2rem] border border-slate-200 bg-slate-950 p-6 text-white shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-300">Cómo se siente en uso</p>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            {heroBullets.map((bullet) => (
              <article key={bullet} className="rounded-2xl border border-white/10 bg-white/5 p-5">
                <p className="text-sm leading-6 text-slate-300">{bullet}</p>
              </article>
            ))}
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}

export default PmsHoteleroPage;
