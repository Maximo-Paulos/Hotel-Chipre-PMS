import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { resolveAppUrl } from "../../config/publicUrls";

import { PublicButtonLink } from "./PublicButtonLink";

const navItems = [
  { label: "Funciones", to: "/funciones" },
  { label: "Precios", to: "/precios" },
  { label: "FAQ", to: "/faq" }
];

type MarketingShellProps = {
  children: ReactNode;
};

export function MarketingShell({ children }: MarketingShellProps) {
  const loginUrl = resolveAppUrl("/login");
  const registerUrl = resolveAppUrl("/register-owner");

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.14),_transparent_38%),linear-gradient(180deg,_#f8fafc_0%,_#eef7ff_52%,_#ffffff_100%)] text-slate-900">
      <header className="sticky top-0 z-30 border-b border-white/70 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <Link to="/" className="flex items-center gap-3">
            <img src="/brand/logo-avatar.png" alt="Hotel Chipre PMS" className="h-10 w-10 rounded-full border border-slate-200 object-cover" />
            <div className="leading-tight">
              <p className="text-sm font-semibold text-slate-900">Hotel Chipre PMS</p>
              <p className="text-xs text-slate-500">Sistema de gestión hotelera</p>
            </div>
          </Link>

          <nav className="hidden items-center gap-6 text-sm font-medium text-slate-600 md:flex">
            {navItems.map((item) => (
              <Link key={item.to} to={item.to} className="transition hover:text-brand-700">
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <PublicButtonLink href={loginUrl} variant="ghost" className="hidden sm:inline-flex">
              Ingresar
            </PublicButtonLink>
            <PublicButtonLink href={registerUrl} variant="primary">
              Registrarte
            </PublicButtonLink>
          </div>
        </div>
      </header>

      <main>{children}</main>

      <footer className="border-t border-slate-200/80 bg-white/90">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:px-6 lg:grid-cols-[1.3fr_0.7fr] lg:px-8">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <img src="/brand/logo-avatar.png" alt="Hotel Chipre PMS" className="h-10 w-10 rounded-full border border-slate-200 object-cover" />
              <div>
                <p className="font-semibold text-slate-900">Hotel Chipre PMS</p>
                <p className="text-sm text-slate-500">Todo tu hotel, en un solo sistema.</p>
              </div>
            </div>
            <p className="max-w-xl text-sm leading-6 text-slate-600">
              Plataforma web para hoteles independientes que necesitan centralizar reservas, habitaciones, huéspedes y cobros con claridad operativa.
            </p>
          </div>

          <div className="flex flex-col gap-3 text-sm">
            <Link to="/funciones" className="text-slate-600 hover:text-brand-700">
              Funciones
            </Link>
            <Link to="/precios" className="text-slate-600 hover:text-brand-700">
              Precios
            </Link>
            <Link to="/faq" className="text-slate-600 hover:text-brand-700">
              FAQ
            </Link>
            <a href={loginUrl} className="text-slate-600 hover:text-brand-700">
              Ingresar
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
