import type { ReactNode } from "react";
import { Link } from "react-router-dom";

type PublicButtonLinkProps = {
  href: string;
  variant?: "primary" | "secondary" | "ghost";
  size?: "md" | "lg";
  className?: string;
  children: ReactNode;
};

const isExternal = (href: string) =>
  /^https?:\/\//i.test(href) || href.startsWith("mailto:") || href.startsWith("tel:") || href.startsWith("#");

const base =
  "inline-flex items-center justify-center rounded-control font-medium transition duration-200 ease-rack " +
  "focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60";

const sizes = {
  // 44px tall so it is a real touch target without needing the global override.
  md: "min-h-[2.75rem] px-4 text-sm",
  lg: "min-h-[3.25rem] px-6 text-base"
};

const variants = {
  // Brass marks the one action that matters most on a screen. Never decorative.
  primary: "bg-brass-500 text-ink-950 shadow-raise hover:bg-brass-400 active:bg-brass-600",
  secondary:
    "border border-ink-200 bg-white text-ink-800 hover:border-ink-400 hover:bg-paper-sunk active:bg-paper-sunk",
  ghost: "text-ink-600 hover:text-ink-900"
};

export function PublicButtonLink({
  href,
  variant = "secondary",
  size = "md",
  className = "",
  children
}: PublicButtonLinkProps) {
  const classes = `${base} ${sizes[size]} ${variants[variant]} ${className}`.trim();
  if (isExternal(href)) {
    return (
      <a href={href} className={classes}>
        {children}
      </a>
    );
  }
  return (
    <Link to={href} className={classes}>
      {children}
    </Link>
  );
}

export default PublicButtonLink;
