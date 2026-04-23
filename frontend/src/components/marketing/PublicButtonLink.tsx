import type { ReactNode } from "react";
import { Link } from "react-router-dom";

type PublicButtonLinkProps = {
  href: string;
  variant?: "primary" | "secondary" | "ghost";
  className?: string;
  children: ReactNode;
};

const isExternal = (href: string) => /^https?:\/\//i.test(href) || href.startsWith("mailto:") || href.startsWith("tel:");

const baseClasses =
  "inline-flex items-center justify-center rounded-full px-4 py-2 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2";

const variantClasses: Record<NonNullable<PublicButtonLinkProps["variant"]>, string> = {
  primary: "bg-brand-600 text-white shadow-sm hover:bg-brand-700",
  secondary: "border border-slate-200 bg-white text-slate-800 hover:border-brand-300 hover:text-brand-700",
  ghost: "text-slate-700 hover:text-brand-700"
};

export function PublicButtonLink({ href, variant = "secondary", className = "", children }: PublicButtonLinkProps) {
  const classes = `${baseClasses} ${variantClasses[variant]} ${className}`.trim();
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
