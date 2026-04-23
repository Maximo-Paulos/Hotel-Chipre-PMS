import { Seo } from "../../components/Seo";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { PublicButtonLink } from "../../components/marketing/PublicButtonLink";
import { ALLOW_INDEXING, resolveAppUrl } from "../../config/publicUrls";
import { benefitPoints, screenshotFrames, systemPoints } from "../../content/marketing";

const functionHighlights = [
  {
    title: "Reservas y huéspedes",
    body: "Consultar y operar la información principal del día sin saltar entre herramientas."
  },
  {
    title: "Habitaciones y cobros",
    body: "Ver el estado operativo con más claridad y seguir el flujo de cobros dentro del sistema."
  },
  {
    title: "Reportes base",
    body: "Tener una vista simple para revisar qué está pasando en la operación del hotel."
  }
];

export function FunctionsPage() {
  return (
    <MarketingShell>
      <Seo
        title="Funciones de Hotel Chipre PMS | Reservas, habitaciones, huéspedes, cobros y reportes"
        description="Explora las funciones principales del PMS hotelero: reservas, habitaciones, huéspedes, cobros, reportes y onboarding guiado."
        canonicalPath="/funciones"
        noindex={!ALLOW_INDEXING}
      />
      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="max-w-3xl space-y-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Funciones</p>
          <h1 className="text-4xl font-semibold tracking-tight text-slate-950">
            Funcionalidad central para operar el hotel con claridad
          </h1>
          <p className="text-lg leading-8 text-slate-700">
            El sistema cubre la base operativa que más importa al hotel independiente: reservas, habitaciones, huéspedes, cobros y reportes, todo en una misma plataforma.
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

        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {functionHighlights.map((item) => (
            <article key={item.title} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold text-slate-950">{item.title}</h2>
              <p className="mt-2 text-sm leading-7 text-slate-600">{item.body}</p>
            </article>
          ))}
        </div>

        <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {systemPoints.map((point) => (
            <article key={point.title} className="rounded-3xl border border-slate-200 bg-slate-50 p-5 shadow-sm">
              <h3 className="text-lg font-semibold text-slate-950">{point.title}</h3>
              <p className="mt-2 text-sm leading-7 text-slate-600">{point.body}</p>
            </article>
          ))}
        </div>

        <div className="mt-10 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Seguir explorando</p>
          <div className="mt-4 flex flex-wrap gap-3 text-sm font-medium">
            <PublicButtonLink href="/" variant="ghost" className="text-slate-700 hover:text-brand-700">
              Volver al inicio
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
            <PublicButtonLink href="/faq" variant="ghost" className="text-slate-700 hover:text-brand-700">
              Resolver dudas frecuentes
            </PublicButtonLink>
          </div>
        </div>

        <div className="mt-10 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Pantallas reales</p>
          <div className="mt-5 grid gap-4 xl:grid-cols-3">
            {screenshotFrames.map((shot) => (
              <figure key={shot.title} className="overflow-hidden rounded-3xl border border-slate-200 bg-slate-50">
                <img src={shot.src} alt={shot.title} loading="lazy" width="1280" height="800" className="h-56 w-full object-cover" />
                <figcaption className="p-4 text-sm leading-6 text-slate-600">{shot.description}</figcaption>
              </figure>
            ))}
          </div>
        </div>

        <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_1fr]">
          <div className="rounded-[2rem] border border-slate-200 bg-slate-950 p-6 text-white shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-300">Qué aporta al hotel</p>
            <div className="mt-4 grid gap-4">
              {benefitPoints.map((point) => (
                <article key={point.title} className="rounded-2xl border border-white/10 bg-white/5 p-5">
                  <h3 className="font-semibold">{point.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-300">{point.body}</p>
                </article>
              ))}
            </div>
          </div>

          <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Qué ve el equipo</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-950">Una base operativa clara para el trabajo diario</h2>
            <p className="mt-3 text-sm leading-7 text-slate-600">
              La página de funciones responde a una pregunta simple: qué cubre hoy el producto y por qué ayuda al hotel a trabajar con menos fricción.
            </p>
            <ul className="mt-5 space-y-3 text-sm leading-6 text-slate-700">
              <li className="rounded-2xl bg-slate-50 p-4">Consultar reservas y huéspedes sin buscar entre herramientas separadas.</li>
              <li className="rounded-2xl bg-slate-50 p-4">Ver habitaciones y cobros con una estructura más fácil de seguir.</li>
              <li className="rounded-2xl bg-slate-50 p-4">Entrar al onboarding con pasos simples y un flujo guiado.</li>
            </ul>
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}

export default FunctionsPage;
