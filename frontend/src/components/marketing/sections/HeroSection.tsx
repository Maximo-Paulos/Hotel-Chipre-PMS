import { EarlyAccessForm } from "../EarlyAccessForm";
import { OccupancyBoard } from "../ui/OccupancyBoard";
import { hero } from "../../../content/marketing";

/**
 * The one orchestrated moment on the page: the board draws itself once on
 * load. Everything below the fold moves only when someone acts on it.
 */
export function HeroSection() {
  return (
    <section className="relative overflow-hidden bg-ink-950 text-white">
      {/* A single wash of brand colour behind the board, sized so the headline
          stays on flat ground and keeps its contrast. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(120%_90%_at_82%_8%,rgba(18,165,148,0.22),transparent_60%)]"
      />
      <div className="relative mx-auto grid w-full max-w-6xl gap-14 px-5 pb-20 pt-14 sm:px-8 sm:pb-24 sm:pt-20 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:items-center lg:gap-16 lg:px-10 lg:pb-28">
        <div>
          <h1 data-seq style={{ ["--i" as string]: 0 }} className="display-wide max-w-[19ch] text-display-sm text-white sm:text-display-md lg:text-display-lg">
            {hero.title}
          </h1>
          <p
            data-seq
            style={{ ["--i" as string]: 1 }}
            className="mt-5 max-w-[52ch] text-base leading-7 text-ink-200 sm:mt-6 sm:text-lg sm:leading-8 lg:text-xl lg:leading-9"
          >
            {hero.subtitle}
          </p>

          <div data-seq style={{ ["--i" as string]: 2 }} className="mt-9 max-w-xl">
            <EarlyAccessForm source="hero" tone="light" />
            <p className="mt-3.5 max-w-[46ch] text-sm leading-6 text-ink-400">{hero.note}</p>
          </div>
        </div>

        {/* The board runs off the right edge of the page the way the real
            grid runs off the right edge of its scroller. The section clips
            it, so this never produces a horizontal scrollbar. */}
        <div
          data-seq
          style={{ ["--i" as string]: 2 }}
          className="lg:mr-[calc(50%-50vw)]"
        >
          <OccupancyBoard />
        </div>
      </div>
    </section>
  );
}

export default HeroSection;
