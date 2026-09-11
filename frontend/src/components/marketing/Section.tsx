import type { ReactNode } from "react";

type SectionProps = {
  id?: string;
  /** `paper` is the default page ground; `deep` is the petrol-navy band. */
  tone?: "paper" | "sunk" | "deep";
  className?: string;
  children: ReactNode;
};

const tones = {
  paper: "bg-paper text-ink-900",
  sunk: "bg-paper-sunk text-ink-900",
  deep: "bg-ink-950 text-white"
};

/**
 * One container, one vertical rhythm. Sections used to each invent their own
 * padding and max width, which is why the old page drifted between three
 * corner radii and a different shadow per card.
 */
export function Section({ id, tone = "paper", className = "", children }: SectionProps) {
  return (
    <section id={id} className={`${tones[tone]} ${className}`.trim()}>
      <div className="mx-auto w-full max-w-6xl px-5 py-20 sm:px-8 sm:py-24 lg:px-10">{children}</div>
    </section>
  );
}

type SectionHeadingProps = {
  title: string;
  lede?: string;
  tone?: "light" | "dark";
  className?: string;
  children?: ReactNode;
};

export function SectionHeading({ title, lede, tone = "dark", className = "", children }: SectionHeadingProps) {
  return (
    <div className={`max-w-2xl ${className}`.trim()}>
      <h2
        className={`display-wide text-display-sm sm:text-display-md ${
          tone === "light" ? "text-white" : "text-ink-950"
        }`}
      >
        {title}
      </h2>
      {lede ? (
        <p
          className={`mt-5 text-lg leading-8 ${tone === "light" ? "text-ink-200" : "text-ink-600"}`}
        >
          {lede}
        </p>
      ) : null}
      {children}
    </div>
  );
}

export default Section;
