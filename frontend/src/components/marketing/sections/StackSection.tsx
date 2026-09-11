import { Section, SectionHeading } from "../Section";
import { replacedTools, riskReversal } from "../../../content/marketing";

/**
 * The commercial argument, kept unpriced on purpose: we do not know what a
 * given hotel pays for the pieces it already stitches together, and a made-up
 * saving is the first claim a buyer can catch us on.
 */
export function StackSection() {
  return (
    <Section id="reemplaza">
      <SectionHeading
        title="Cinco herramientas sueltas, una sola suscripción."
        lede="Ninguna de las cinco habla con las otras cuatro. Ese es el trabajo que hoy hace alguien a mano, todos los días."
      />

      <div className="mt-12 grid gap-10 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] lg:gap-16">
        <ul className="divide-y divide-ink-200 border-y border-ink-200">
          {replacedTools.map((tool) => (
            <li key={tool.name} className="flex items-baseline gap-4 py-4">
              <span
                aria-hidden="true"
                className="mt-1 h-px w-6 shrink-0 bg-brass-500"
              />
              <span>
                <span className="font-display text-base font-semibold text-ink-950">{tool.name}</span>
                <span className="text-base text-ink-500"> — {tool.detail}</span>
              </span>
            </li>
          ))}
        </ul>

        <div className="grid gap-8 sm:grid-cols-3 lg:grid-cols-1 lg:gap-7">
          {riskReversal.map((item) => (
            <div key={item.title}>
              <h3 className="font-display text-base font-semibold text-ink-950">{item.title}</h3>
              <p className="mt-1.5 text-sm leading-6 text-ink-600">{item.body}</p>
            </div>
          ))}
        </div>
      </div>
    </Section>
  );
}

export default StackSection;
