import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

import { Seo } from "../../components/Seo";
import { MarketingIcon } from "../../components/marketing/MarketingIcon";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { PublicButtonLink } from "../../components/marketing/PublicButtonLink";

export function ThankYouPage() {
  const [hasAcceptedSubmission] = useState(() =>
    typeof window !== "undefined" && window.sessionStorage.getItem("hotel-chipre:public-inquiry-accepted") === "1"
  );

  useEffect(() => {
    if (hasAcceptedSubmission && typeof window !== "undefined") {
      window.sessionStorage.removeItem("hotel-chipre:public-inquiry-accepted");
    }
  }, [hasAcceptedSubmission]);

  if (typeof window !== "undefined" && !hasAcceptedSubmission) {
    return <Navigate to="/contacto" replace />;
  }

  return (
    <MarketingShell>
      <Seo
        title="Consulta recibida | Hotels-PMS"
        description="Tu consulta sobre Hotels-PMS fue recibida correctamente."
        canonicalPath="/gracias"
        noindex
        breadcrumbLabel="Gracias"
      />
      <section className="mx-auto max-w-3xl px-4 py-16 text-center sm:px-6 lg:px-8">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-brand-100 text-brand-700">
          <MarketingIcon name="check" size={30} />
        </div>
        <p className="mt-6 text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Consulta recibida</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-950">Gracias por escribirnos</h1>
        <p className="mx-auto mt-4 max-w-xl text-lg leading-8 text-slate-700">
          Registramos tu consulta correctamente. Podés seguir recorriendo el sitio mientras el equipo revisa la información.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <PublicButtonLink href="/" variant="primary">Volver al inicio</PublicButtonLink>
          <PublicButtonLink href="/faq" variant="secondary">Ver preguntas frecuentes</PublicButtonLink>
        </div>
      </section>
    </MarketingShell>
  );
}
