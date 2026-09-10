import { Section, SectionHeading } from "../Section";
import { faqItems } from "../../../content/marketing";

export function FaqSection() {
  return (
    <Section id="preguntas">
      <SectionHeading
        title="Lo que todo el mundo pregunta antes de decidir."
        lede="Incluidas las respuestas que no nos convienen."
      />

      <div className="mt-12 divide-y divide-ink-200 border-y border-ink-200">
        {faqItems.map((item) => (
          <details key={item.question} className="group py-5">
            <summary className="flex cursor-pointer list-none items-start justify-between gap-6 text-left">
              <span className="font-display text-lg font-semibold text-ink-950">{item.question}</span>
              <span
                aria-hidden="true"
                className="mt-1 shrink-0 text-2xl leading-none text-ink-400 transition-transform duration-200 ease-rack group-open:rotate-45"
              >
                +
              </span>
            </summary>
            <p className="mt-3 max-w-3xl text-base leading-7 text-ink-600">{item.answer}</p>
          </details>
        ))}
      </div>
    </Section>
  );
}

export default FaqSection;
