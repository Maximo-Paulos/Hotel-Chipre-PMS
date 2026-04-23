import { Seo } from "../../components/Seo";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { PublicButtonLink } from "../../components/marketing/PublicButtonLink";
import { ALLOW_INDEXING, resolveAppUrl } from "../../config/publicUrls";
import { benefitPoints } from "../../content/marketing";

const softwarePoints = [
  {
    title: "Menos herramientas sueltas",
    body: "Pensado para hoteles que hoy trabajan entre planillas, mensajes y sistemas separados."
  },
  {
    title: "Más orden operativo",
    body: "El equipo gana una base web clara para seguir reservas, habitaciones y cobros."
  },
  {
    title: "Decisiones más fáciles",
    body: "Dirección y recepción leen la misma información sin depender de archivos aislados."
  }
];

export function SoftwareParaHotelesPage() {
  return (
    <MarketingShell>
      <Seo
        title="Software para hoteles | Hotel Chipre PMS"
        description="Software para hoteles pensado para ordenar la operación, con onboarding guiado y un sistema de gestión hotelera claro."
        canonicalPath="/software-para-hoteles"
        noindex={!ALLOW_INDEXING}
      />
      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="max-w-3xl space-y-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Software para hoteles</p>
          <h1 className="text-4xl font-semibold tracking-tight text-slate-950">
            Software para hoteles que necesitan orden y control operativo
          </h1>
          <p className="text-lg leading-8 text-slate-700">
            Hotel Chipre PMS habla al hotel que sigue operando con herramientas separadas y quiere una base web más clara para el día a día.
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
          {softwarePoints.map((point) => (
            <article key={point.title} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold text-slate-950">{point.title}</h2>
              <p className="mt-2 text-sm leading-7 text-slate-600">{point.body}</p>
            </article>
          ))}
        </div>

        <div className="mt-10 grid gap-4 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm md:grid-cols-3">
          {benefitPoints.map((point) => (
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
            <PublicButtonLink href="/pms-hotelero" variant="ghost" className="text-slate-700 hover:text-brand-700">
              Entender el PMS hotelero
            </PublicButtonLink>
            <PublicButtonLink href="/precios" variant="ghost" className="text-slate-700 hover:text-brand-700">
              Ver planes y precios
            </PublicButtonLink>
            <PublicButtonLink href="/faq" variant="ghost" className="text-slate-700 hover:text-brand-700">
              Resolver dudas frecuentes
            </PublicButtonLink>
          </div>
        </div>

        <div className="mt-10 rounded-[2rem] border border-slate-200 bg-slate-950 p-6 text-white shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-300">Qué resuelve</p>
          <h2 className="mt-2 text-2xl font-semibold">Menos fricción entre operación, recepción y dirección</h2>
          <p className="mt-3 text-sm leading-7 text-slate-300">
            La propuesta evita el ruido técnico y apunta a una sola idea: organizar la operación del hotel en una plataforma web entendible.
          </p>
        </div>
      </section>
    </MarketingShell>
  );
}

export default SoftwareParaHotelesPage;
