import { EarlyAccessForm } from "../EarlyAccessForm";
import { hero } from "../../../content/marketing";

export function FinalCtaSection() {
  return (
    <section className="bg-ink-950 text-white">
      <div className="mx-auto w-full max-w-6xl px-5 py-20 sm:px-8 sm:py-24 lg:px-10">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.85fr)] lg:items-end lg:gap-16">
          <h2 className="display-wide max-w-[16ch] text-display-sm text-white sm:text-display-md">
            Poné todo el hotel en un solo lugar.
          </h2>
          <div>
            <EarlyAccessForm source="final" tone="light" />
            <p className="mt-3.5 text-sm leading-6 text-ink-400">{hero.note}</p>
          </div>
        </div>
      </div>
    </section>
  );
}

export default FinalCtaSection;
