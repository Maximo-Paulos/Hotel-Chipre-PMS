import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { resolveAppUrl } from "../../config/publicUrls";
import { useDialogA11y } from "../../hooks/useDialogA11y";

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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const mobileMenuRef = useDialogA11y(mobileMenuOpen, () => setMobileMenuOpen(false));

  const closeMobileMenu = () => setMobileMenuOpen(false);

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
            <PublicButtonLink href={loginUrl} variant="ghost" className="inline-flex">
              Ingresar
            </PublicButtonLink>
            <PublicButtonLink href={registerUrl} variant="primary">
              Registrarte
            </PublicButtonLink>
            <button
              type="button"
              className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-slate-200 bg-white px-3 text-slate-700 shadow-sm hover:border-brand-300 hover:text-brand-700 md:hidden"
              aria-label={mobileMenuOpen ? "Cerrar menú" : "Abrir menú"}
              aria-controls="marketing-mobile-menu"
              aria-expanded={mobileMenuOpen}
              onClick={() => setMobileMenuOpen((open) => !open)}
            >
              <span aria-hidden="true" className="text-lg leading-none">{mobileMenuOpen ? "×" : "☰"}</span>
            </button>
          </div>
        </div>
        {mobileMenuOpen && (
          <div id="marketing-mobile-menu" ref={mobileMenuRef} className="border-t border-slate-200 bg-white px-4 py-3 md:hidden">
            <nav aria-label="Navegación principal" className="flex flex-col gap-1 text-sm font-medium text-slate-700">
              {navItems.map((item) => (
                <Link key={item.to} to={item.to} onClick={closeMobileMenu} className="rounded-lg px-3 py-3 hover:bg-slate-50 hover:text-brand-700">
                  {item.label}
                </Link>
              ))}
              <a href={loginUrl} onClick={closeMobileMenu} className="rounded-lg px-3 py-3 hover:bg-slate-50 hover:text-brand-700">
                Ingresar
              </a>
            </nav>
          </div>
        )}
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
            <Link to="/pms-hotelero" className="text-slate-600 hover:text-brand-700">
              PMS hotelero
            </Link>
            <Link to="/software-para-hoteles" className="text-slate-600 hover:text-brand-700">
              Software para hoteles
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
            <Link to="/terms" className="text-slate-600 hover:text-brand-700">
              Términos y Condiciones
            </Link>
            <Link to="/privacy" className="text-slate-600 hover:text-brand-700">
              Política de Privacidad
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
