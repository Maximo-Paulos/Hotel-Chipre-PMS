import { Seo } from "../../components/Seo";
import { MarketingIcon } from "../../components/marketing/MarketingIcon";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { PublicButtonLink } from "../../components/marketing/PublicButtonLink";

export function MarketingNotFoundPage() {
  return (
    <MarketingShell>
      <Seo
        title="Página no encontrada | Hotel Chipre PMS"
        description="La página que buscás no existe o fue movida. Volvé al inicio de Hotel Chipre PMS."
        canonicalPath="/404"
        noindex
      />
      <section className="mx-auto max-w-3xl px-4 py-20 text-center sm:px-6 lg:px-8">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-slate-200 text-slate-700">
          <MarketingIcon name="chevron-right" size={30} className="rotate-180" />
        </div>
        <p className="mt-6 text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Error 404</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-950">Esta página no está disponible</h1>
        <p className="mx-auto mt-4 max-w-xl text-lg leading-8 text-slate-700">El enlace puede estar desactualizado. Encontrá el camino desde el inicio o escribinos para orientarte.</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <PublicButtonLink href="/" variant="primary">Volver al inicio</PublicButtonLink>
          <PublicButtonLink href="/contacto" variant="secondary">Contactarnos</PublicButtonLink>
        </div>
      </section>
    </MarketingShell>
  );
}
