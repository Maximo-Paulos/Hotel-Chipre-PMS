import { Section, SectionHeading } from "../Section";
import { problemPoints, scatteredPlaces } from "../../../content/marketing";

/**
 * Names the six places the state of a hotel actually lives before a PMS.
 * The list is the argument -- reading it is the moment the visitor recognises
 * their own hotel -- so it gets the weight, not a diagram.
 */
export function ProblemSection() {
  return (
    <Section id="problema" tone="sunk">
      <SectionHeading
        title="Hoy el estado del hotel vive en seis lugares."
        lede="Ninguno de los seis sabe lo que saben los otros cinco, y el que atiende el mostrador tiene que juntarlos de memoria."
      />

      <ul className="mt-12 grid gap-px overflow-hidden rounded-panel bg-ink-200 sm:grid-cols-2 lg:grid-cols-3">
        {scatteredPlaces.map((place) => (
          <li key={place.label} className="bg-paper px-6 py-7">
            <p className="font-display text-base font-semibold text-ink-900">{place.label}</p>
            <p className="mt-1.5 text-sm leading-6 text-ink-500">{place.detail}</p>
          </li>
        ))}
      </ul>

      <div className="mt-14 grid gap-10 sm:grid-cols-3 sm:gap-8">
        {problemPoints.map((point) => (
          <div key={point.title} className="border-t border-ink-300 pt-5">
            <h3 className="font-display text-lg font-semibold text-ink-900">{point.title}</h3>
            <p className="mt-2.5 text-base leading-7 text-ink-600">{point.body}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}

export default ProblemSection;
