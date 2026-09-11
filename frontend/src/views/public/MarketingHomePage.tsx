import { Seo } from "../../components/Seo";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { DifferentiatorsSection } from "../../components/marketing/sections/DifferentiatorsSection";
import { FaqSection } from "../../components/marketing/sections/FaqSection";
import { FinalCtaSection } from "../../components/marketing/sections/FinalCtaSection";
import { FounderSection } from "../../components/marketing/sections/FounderSection";
import { HeroSection } from "../../components/marketing/sections/HeroSection";
import { IntegrationsStrip } from "../../components/marketing/sections/IntegrationsStrip";
import { ModulesSection } from "../../components/marketing/sections/ModulesSection";
import { OnboardingSection } from "../../components/marketing/sections/OnboardingSection";
import { PricingSection } from "../../components/marketing/sections/PricingSection";
import { ProblemSection } from "../../components/marketing/sections/ProblemSection";
import { ProductTourSection } from "../../components/marketing/sections/ProductTourSection";
import { StackSection } from "../../components/marketing/sections/StackSection";
import { ALLOW_INDEXING, resolveSiteUrl } from "../../config/publicUrls";
import { brandName, faqItems, positioning } from "../../content/marketing";

const homeSchema = [
  {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: brandName,
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web",
    description: positioning,
    url: resolveSiteUrl("/"),
    inLanguage: "es-AR"
  },
  {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqItems.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: { "@type": "Answer", text: item.answer }
    }))
  }
];

export function MarketingHomePage() {
  return (
    <MarketingShell>
      <Seo
        title="Hotels-PMS | El sistema de gestión que unifica todo el hotel"
        description="Reservas, recepción, housekeeping, tarifas, caja, stock y lavandería sobre los mismos datos. Sistema de gestión hotelera para hoteles chicos y medianos."
        canonicalPath="/"
        noindex={!ALLOW_INDEXING}
        structuredData={homeSchema}
      />

      <HeroSection />
      <IntegrationsStrip />
      <ProblemSection />
      <StackSection />
      <ModulesSection />
      <ProductTourSection />
      <DifferentiatorsSection />
      <FounderSection />
      <OnboardingSection />
      <PricingSection />
      <FaqSection />
      <FinalCtaSection />
    </MarketingShell>
  );
}

export default MarketingHomePage;
