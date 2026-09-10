type BrandMarkProps = {
  /** `mark` is the glyph alone; `full` pairs it with the wordmark. */
  variant?: "mark" | "full";
  className?: string;
  /** Renders the wordmark for light-on-dark surfaces. */
  tone?: "dark" | "light";
};

/**
 * The mark is one square holding three ascending bars behind four contact
 * pins. It reads three ways on purpose -- a chip die, a building, and a
 * filling occupancy grid -- which is the same triple meaning the original
 * original chip mark was reaching for, minus the circuit filigree that
 * turned to mush below about 80px. It is drawn on a 24px grid so it stays
 * legible at favicon size.
 */
function Glyph({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className={className}>
      <rect
        x="4.25"
        y="4.25"
        width="15.5"
        height="15.5"
        rx="3.25"
        stroke="currentColor"
        strokeWidth="1.75"
      />
      <g stroke="currentColor" strokeWidth="1.75" strokeLinecap="round">
        <path d="M1.6 9.25h2.65M1.6 14.75h2.65M19.75 9.25h2.65M19.75 14.75h2.65" />
      </g>
      <g fill="currentColor">
        <rect x="7.75" y="13" width="2.25" height="3.5" rx="0.6" />
        <rect x="10.9" y="10.25" width="2.25" height="6.25" rx="0.6" />
        <rect x="14.05" y="7.5" width="2.25" height="9" rx="0.6" />
      </g>
    </svg>
  );
}

export function BrandMark({ variant = "full", className = "", tone = "dark" }: BrandMarkProps) {
  if (variant === "mark") {
    return <Glyph className={`h-7 w-7 text-brand-600 ${className}`.trim()} />;
  }

  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`.trim()}>
      <Glyph className={tone === "light" ? "h-7 w-7 text-brand-300" : "h-7 w-7 text-brand-600"} />
      <span
        className={`font-display text-[1.0625rem] leading-none tracking-[-0.01em] ${
          tone === "light" ? "text-white" : "text-ink-900"
        }`}
        style={{ fontStretch: "108%" }}
      >
        <span className="font-medium">Hotels</span>
        <span className={tone === "light" ? "text-brand-300" : "text-brand-600"}>-</span>
        <span className="font-bold">PMS</span>
      </span>
    </span>
  );
}

export default BrandMark;
