import { Link } from "react-router-dom";

import { Seo } from "../../components/Seo";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { PublicButtonLink } from "../../components/marketing/PublicButtonLink";
import {
  ALLOW_INDEXING,
  resolveAppUrl,
  resolveSalesContactUrl,
  resolveSiteUrl
} from "../../config/publicUrls";
import {
  brandName,
  benefitPoints,
  heroBullets,
  integrationPoints,
  onboardingSteps,
  positioning,
  pricingCards,
  problemPoints,
  screenshotFrames,
  systemPoints,
  tagline
} from "../../content/marketing";

const homeSchema = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: brandName,
  url: resolveSiteUrl("/")
};

function ScreenshotGrid() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {screenshotFrames.map((shot) => (
        <figure
          key={shot.title}
          className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_20px_60px_rgba(15,23,42,0.08)]"
        >
          <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span className="h-2.5 w-2.5 rounded-full bg-rose-400" />
              <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
              <span className="ml-2 font-semibold text-slate-600">{shot.title}</span>
            </div>
          </div>
          <img
            src={shot.src}
            alt={shot.title}
            loading="lazy"
            width="1280"
            height="800"
            className="h-[220px] w-full object-cover sm:h-[240px]"
          />
          <figcaption className="p-4 text-sm leading-6 text-slate-600">{shot.description}</figcaption>
        </figure>
      ))}
    </div>
  );
}

export function MarketingHomePage() {
  return (
    <MarketingShell>
      <Seo
        title="PMS hotelero para hoteles independientes | Hotel Chipre PMS"
        description="Sistema de gestión hotelera para centralizar reservas, habitaciones, huéspedes y cobros en un solo lugar. Prueba 14 días con Hotel Chipre PMS."
        canonicalPath="/"
        noindex={!ALLOW_INDEXING}
        structuredData={homeSchema}
      />

      <section className="mx-auto grid max-w-6xl gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:px-8 lg:py-20">
        <div className="space-y-6">
          <p className="inline-flex rounded-full border border-brand-200 bg-brand-50 px-4 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-brand-700">
            PMS hotelero para hoteles independientes
          </p>
          <div className="space-y-4">
            <h1 className="max-w-2xl text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">
              PMS hotelero para operar tu hotel desde un solo lugar
            </h1>
            <p className="max-w-2xl text-lg leading-8 text-slate-700">{positioning}</p>
          </div>

          <div className="flex flex-wrap gap-3">
            <PublicButtonLink href={resolveAppUrl("/register-owner")} variant="primary">
              Registrarte
            </PublicButtonLink>
            <PublicButtonLink href={resolveAppUrl("/login")} variant="secondary">
              Ingresar
            </PublicButtonLink>
            <PublicButtonLink href="/precios" variant="ghost">
              Ver precios
            </PublicButtonLink>
          </div>

          <div className="flex flex-wrap gap-4 text-sm font-medium text-slate-600">
            <Link to="/pms-hotelero" className="underline decoration-slate-300 underline-offset-4 hover:text-brand-700">
              PMS hotelero
            </Link>
            <Link to="/software-para-hoteles" className="underline decoration-slate-300 underline-offset-4 hover:text-brand-700">
              Software para hoteles
            </Link>
            <Link to="/faq" className="underline decoration-slate-300 underline-offset-4 hover:text-brand-700">
              Preguntas frecuentes
            </Link>
          </div>

          <ul className="grid gap-3 sm:grid-cols-3">
            {heroBullets.map((bullet) => (
              <li
                key={bullet}
                className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-4 text-sm leading-6 text-slate-700 shadow-sm"
              >
                {bullet}
              </li>
            ))}
          </ul>

          <div className="rounded-3xl border border-slate-200 bg-white/90 p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">La promesa</p>
            <p className="mt-2 text-sm leading-7 text-slate-700">{tagline}</p>
          </div>
        </div>

        <div className="space-y-4">
          <ScreenshotGrid />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 pb-12 sm:px-6 lg:px-8">
        <div className="grid gap-4 rounded-[2rem] border border-slate-200 bg-white/90 p-6 shadow-sm md:grid-cols-3">
          {problemPoints.map((point) => (
            <article key={point.title} className="rounded-2xl bg-slate-50 p-5">
              <h2 className="text-lg font-semibold text-slate-900">{point.title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">{point.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="space-y-4">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Todo en un solo sistema</p>
            <h2 className="text-3xl font-semibold tracking-tight text-slate-950">Centraliza la operación del hotel sin sumar complejidad</h2>
            <p className="text-base leading-7 text-slate-600">
              Reservas, habitaciones, huéspedes, cobros y reportes viven en una misma plataforma web para que el equipo trabaje con más claridad.
            </p>
            <PublicButtonLink href="/funciones" variant="secondary">
              Ver funciones
            </PublicButtonLink>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {systemPoints.map((point) => (
              <article key={point.title} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                <h3 className="text-lg font-semibold text-slate-900">{point.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">{point.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="rounded-[2rem] border border-slate-200 bg-white/90 p-6 shadow-sm">
          <div className="max-w-2xl space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Screenshots reales</p>
            <h2 className="text-3xl font-semibold tracking-tight text-slate-950">La app muestra el producto real, no solo promesas</h2>
            <p className="text-sm leading-7 text-slate-600">
              Estas capturas muestran dashboard, reservas y conexiones reales del sistema para que la propuesta sea fácil de entender.
            </p>
          </div>
          <div className="mt-6">
            <ScreenshotGrid />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-[1fr_1fr]">
          <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">
              Integraciones disponibles dentro del sistema
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
              Conexiones visibles en la configuración del sistema
            </h2>
            <p className="mt-3 text-sm leading-7 text-slate-600">
              Hotel Chipre PMS muestra integraciones y conexiones configurables dentro del producto para acompañar la operación diaria del hotel desde una misma plataforma.
            </p>
            <ul className="mt-4 space-y-2 text-sm leading-6 text-slate-700">
              {integrationPoints.map((item) => (
                <li key={item} className="flex gap-3">
                  <span className="mt-2 h-2 w-2 rounded-full bg-brand-500" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-[2rem] border border-slate-200 bg-slate-950 p-6 text-white shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-300">Por qué importa</p>
            <div className="mt-4 grid gap-4">
              {benefitPoints.map((point) => (
                <article key={point.title} className="rounded-2xl border border-white/10 bg-white/5 p-5">
                  <h3 className="text-lg font-semibold">{point.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-300">{point.body}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-[0.95fr_1.05fr]">
          <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Cómo funciona / onboarding</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">Empieza con un flujo guiado</h2>
            <p className="mt-3 text-sm leading-7 text-slate-600">
              La puesta en marcha está guiada desde el alta hasta la configuración inicial para que el hotel empiece con orden.
            </p>
            <ol className="mt-5 space-y-3">
              {onboardingSteps.map((step, index) => (
                <li key={step} className="flex gap-4 rounded-2xl bg-slate-50 p-4">
                  <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white">
                    {index + 1}
                  </span>
                  <span className="text-sm leading-6 text-slate-700">{step}</span>
                </li>
              ))}
            </ol>
          </div>

          <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Beneficios por tarea</p>
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              {benefitPoints.map((point) => (
                <article key={point.title} className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                  <h3 className="text-base font-semibold text-slate-900">{point.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{point.body}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="rounded-[2rem] border border-slate-200 bg-white/90 p-6 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-2xl space-y-3">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Pricing teaser</p>
              <h2 className="text-3xl font-semibold tracking-tight text-slate-950">Starter, Pro y Ultra para distintas etapas de operación</h2>
              <p className="text-sm leading-7 text-slate-600">
                Starter incluye prueba de 14 días. Pro y Ultra se gestionan con ventas hasta cerrar el flujo de compra online.
              </p>
            </div>
            <PublicButtonLink href="/precios" variant="secondary">
              Ver precios
            </PublicButtonLink>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {pricingCards.map((plan) => (
              <article key={plan.code} className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">{plan.code}</p>
                <h3 className="mt-2 text-xl font-semibold text-slate-950">{plan.name}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">{plan.description}</p>
                <p className="mt-4 text-sm font-semibold text-brand-700">{plan.cta}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-[1fr_1fr]">
          <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">FAQ</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">Resolvemos objeciones sin inflar el producto</h2>
            <p className="mt-3 text-sm leading-7 text-slate-600">
              El FAQ responde con claridad y sin prometer módulos o alcances que no están cerrados.
            </p>
            <div className="mt-5 space-y-3">
              <details className="group rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <summary className="cursor-pointer list-none text-sm font-semibold text-slate-900">¿Qué incluye la prueba de 14 días?</summary>
                <p className="mt-3 text-sm leading-6 text-slate-600">
                  Starter se presenta públicamente con una prueba de 14 días para conocer el sistema antes de decidir.
                </p>
              </details>
              <details className="group rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <summary className="cursor-pointer list-none text-sm font-semibold text-slate-900">¿Cómo consulto planes pagos?</summary>
                <p className="mt-3 text-sm leading-6 text-slate-600">
                  Pro y Ultra se gestionan con el equipo comercial hasta que la compra online esté abierta.
                </p>
              </details>
              <details className="group rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <summary className="cursor-pointer list-none text-sm font-semibold text-slate-900">¿La app y la landing van separadas?</summary>
                <p className="mt-3 text-sm leading-6 text-slate-600">
                  Sí. La landing vive en marketing/root y la app queda como producto operativo con indexación controlada.
                </p>
              </details>
            </div>
          </div>

          <div className="rounded-[2rem] border border-slate-200 bg-slate-950 p-6 text-white shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-300">CTA final</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight">Empieza a conocer la plataforma</h2>
            <p className="mt-3 text-sm leading-7 text-slate-300">
              Crea tu cuenta, revisa el sistema y valida si encaja con la operación real de tu hotel.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <PublicButtonLink href={resolveAppUrl("/register-owner")} variant="primary">
                Registrarte
              </PublicButtonLink>
              <PublicButtonLink
                href={resolveAppUrl("/login")}
                variant="secondary"
                className="border-white/15 bg-white/5 text-white hover:border-white/30 hover:text-white"
              >
                Ingresar
              </PublicButtonLink>
              <PublicButtonLink
                href={resolveSalesContactUrl()}
                variant="ghost"
                className="text-slate-200 hover:text-white"
              >
                Hablar con ventas
              </PublicButtonLink>
            </div>
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}

export default MarketingHomePage;
