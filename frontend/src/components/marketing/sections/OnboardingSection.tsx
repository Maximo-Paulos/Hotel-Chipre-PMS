import { Section, SectionHeading } from "../Section";
import { onboardingSteps } from "../../../content/marketing";

/** A genuine sequence, so the steps are genuinely numbered. */
export function OnboardingSection() {
  return (
    <Section id="alta" tone="sunk">
      <SectionHeading
        title="Del alta a operar, en tres pasos."
        lede="El alta es guiada: el sistema te va pidiendo lo que falta en vez de dejarte frente a una configuración vacía."
      />

      <ol className="mt-12 grid gap-10 sm:grid-cols-3 sm:gap-8">
        {onboardingSteps.map((step, index) => (
          <li key={step.title} className="border-t-2 border-brass-500 pt-5">
            <span className="numeric text-sm font-semibold text-brass-600">Paso {index + 1}</span>
            <h3 className="mt-2 font-display text-xl font-semibold text-ink-950">{step.title}</h3>
            <p className="mt-2.5 text-base leading-7 text-ink-600">{step.body}</p>
          </li>
        ))}
      </ol>
    </Section>
  );
}

export default OnboardingSection;
