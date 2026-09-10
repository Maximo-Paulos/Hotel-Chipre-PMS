import { Seo } from "../../components/Seo";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { DifferentiatorsSection } from "../../components/marketing/sections/DifferentiatorsSection";
import { FinalCtaSection } from "../../components/marketing/sections/FinalCtaSection";
import { ModulesSection } from "../../components/marketing/sections/ModulesSection";
import { OnboardingSection } from "../../components/marketing/sections/OnboardingSection";
import { ProductTourSection } from "../../components/marketing/sections/ProductTourSection";
import { ALLOW_INDEXING } from "../../config/publicUrls";

/**
 * The long form of the home page's product argument. It composes the same
 * sections rather than keeping a second, drifting copy of them -- the previous
 * version cropped the product images to 224px with object-cover, which is why
 * they read as broken.
 */
export function FunctionsPage() {
  return (
    <MarketingShell>
      <Seo
        title="El sistema | Hotels-PMS"
        description="Reservas, planilla de ocupación, recepción, housekeeping, tarifas, caja y arqueo, stock, lavandería, empresas, analítica y permisos por rol, en un solo sistema."
        canonicalPath="/funciones"
        noindex={!ALLOW_INDEXING}
      />
      <ModulesSection />
      <ProductTourSection />
      <DifferentiatorsSection />
      <OnboardingSection />
      <FinalCtaSection />
    </MarketingShell>
  );
}

export default FunctionsPage;
