import { Section } from "../Section";
import { founder } from "../../../content/marketing";

/**
 * The strongest thing this product can say and the one a competitor cannot
 * copy: it is built by someone who runs a hotel with it. Set as a single
 * column of prose rather than a card, because it is a person talking.
 */
export function FounderSection() {
  return (
    <Section id="origen" tone="sunk">
      <div className="max-w-2xl">
        <h2 className="display-wide text-display-sm text-ink-950 sm:text-display-md">{founder.title}</h2>
        <div className="mt-7 space-y-5">
          {founder.body.map((paragraph) => (
            <p key={paragraph.slice(0, 24)} className="text-lg leading-8 text-ink-700">
              {paragraph}
            </p>
          ))}
        </div>
        <p className="mt-8 border-l-2 border-brass-500 pl-4 text-base text-ink-600">
          {founder.signature}
        </p>
      </div>
    </Section>
  );
}

export default FounderSection;
