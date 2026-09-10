import { Seo } from "../../components/Seo";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { FaqSection } from "../../components/marketing/sections/FaqSection";
import { FinalCtaSection } from "../../components/marketing/sections/FinalCtaSection";
import { PricingSection } from "../../components/marketing/sections/PricingSection";
import { ALLOW_INDEXING } from "../../config/publicUrls";

export function PricingPage() {
  return (
    <MarketingShell>
      <Seo
        title="Precios | Hotels-PMS"
        description="Una suscripción mensual por hotel, con planes por cantidad de habitaciones y de usuarios. Prueba de 14 días con el sistema completo."
        canonicalPath="/precios"
        noindex={!ALLOW_INDEXING}
      />
      <PricingSection />
      <FaqSection />
      <FinalCtaSection />
    </MarketingShell>
  );
}

export default PricingPage;
