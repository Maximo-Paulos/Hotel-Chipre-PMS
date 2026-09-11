import { Section, SectionHeading } from "../Section";
import { differentiators } from "../../../content/marketing";

/**
 * Every claim here is checkable inside the product. The `proof` line is the
 * point: it is the detail a competitor's landing page cannot copy without
 * having built the thing.
 */
export function DifferentiatorsSection() {
  return (
    <Section id="diferencias" tone="deep">
      <SectionHeading
        tone="light"
        title="Lo que hace distinto a un sistema que se usa de verdad."
        lede="No son funciones de folleto. Son las decisiones que aparecen recién cuando un hotel opera todos los días sobre el mismo sistema."
      />

      <div className="mt-14 grid gap-x-14 gap-y-12 md:grid-cols-2">
        {differentiators.map((item) => (
          <article key={item.title} className="border-t border-white/15 pt-6">
            <h3 className="display-wide text-xl text-white">{item.title}</h3>
            <p className="mt-3 text-base leading-7 text-ink-200">{item.body}</p>
            <p className="numeric mt-4 text-sm leading-6 text-brand-300">{item.proof}</p>
          </article>
        ))}
      </div>
    </Section>
  );
}

export default DifferentiatorsSection;
