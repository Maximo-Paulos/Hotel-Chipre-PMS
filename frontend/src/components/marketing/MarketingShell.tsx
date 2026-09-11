import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { BrandMark } from "../brand/BrandMark";
import { resolveAppUrl } from "../../config/publicUrls";
import { useDialogA11y } from "../../hooks/useDialogA11y";
import { marketingRoutes } from "../../content/marketing";

type MarketingShellProps = {
  children: ReactNode;
};

export function MarketingShell({ children }: MarketingShellProps) {
  const loginUrl = resolveAppUrl("/login");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const mobileMenuRef = useDialogA11y(mobileMenuOpen, () => setMobileMenuOpen(false));

  // The header sits on the dark hero at rest and picks up a ground once the
  // page scrolls under it, so it never floats over mixed contrast.
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const closeMobileMenu = () => setMobileMenuOpen(false);

  return (
    <div className="min-h-screen bg-paper font-sans text-ink-900">
      <a
        href="#contenido"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-control focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:text-ink-900"
      >
        Ir al contenido
      </a>

      <header
        className={`sticky top-0 z-30 transition duration-200 ease-rack ${
          scrolled ? "bg-ink-950/90 backdrop-blur-md" : "bg-ink-950"
        }`}
      >
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-5 py-4 sm:px-8 lg:px-10">
          <Link to="/" aria-label="Hotels-PMS, inicio">
            <BrandMark tone="light" />
          </Link>

          <nav aria-label="Principal" className="hidden items-center gap-8 text-sm md:flex">
            {marketingRoutes.map((item) => (
              <Link key={item.to} to={item.to} className="text-ink-200 transition hover:text-white">
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <a
              href={loginUrl}
              className="hidden min-h-11 items-center rounded-control px-3 text-sm text-ink-200 transition hover:text-white sm:inline-flex"
            >
              Ingresar
            </a>
            <button
              type="button"
              className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-control border border-white/15 px-3 text-ink-100 md:hidden"
              aria-label={mobileMenuOpen ? "Cerrar menú" : "Abrir menú"}
              aria-controls="marketing-mobile-menu"
              aria-expanded={mobileMenuOpen}
              onClick={() => setMobileMenuOpen((open) => !open)}
            >
              <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" aria-hidden="true">
                {mobileMenuOpen ? (
                  <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                ) : (
                  <path d="M3 6h14M3 13h14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                )}
              </svg>
            </button>
          </div>
        </div>

        {mobileMenuOpen && (
          <div
            id="marketing-mobile-menu"
            ref={mobileMenuRef}
            className="border-t border-white/10 bg-ink-950 px-5 py-3 md:hidden"
          >
            <nav aria-label="Principal" className="flex flex-col text-base">
              {marketingRoutes.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  onClick={closeMobileMenu}
                  className="min-h-11 rounded-control px-2 py-3 text-ink-100 hover:bg-white/5"
                >
                  {item.label}
                </Link>
              ))}
              <a
                href={loginUrl}
                onClick={closeMobileMenu}
                className="min-h-11 rounded-control px-2 py-3 text-ink-100 hover:bg-white/5"
              >
                Ingresar
              </a>
            </nav>
          </div>
        )}
      </header>

      <main id="contenido">{children}</main>

      <footer className="border-t border-ink-200 bg-white">
        <div className="mx-auto grid w-full max-w-6xl gap-10 px-5 py-14 sm:px-8 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)] lg:px-10">
          <div>
            <BrandMark />
            <p className="mt-4 max-w-sm text-sm leading-7 text-ink-600">
              Sistema de gestión hotelera para hoteles independientes, boutique y de escala chica y
              mediana. Hecho en Argentina, en español, y con la operación del hotel en pesos.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-8 text-sm">
            <nav aria-label="Producto" className="flex flex-col gap-3">
              <p className="font-display font-semibold text-ink-900">Producto</p>
              <Link to="/funciones" className="text-ink-600 hover:text-ink-900">
                El sistema
              </Link>
              <Link to="/precios" className="text-ink-600 hover:text-ink-900">
                Precios
              </Link>
              <Link to="/faq" className="text-ink-600 hover:text-ink-900">
                Preguntas
              </Link>
              <a href={loginUrl} className="text-ink-600 hover:text-ink-900">
                Ingresar
              </a>
            </nav>
            <nav aria-label="Más" className="flex flex-col gap-3">
              <p className="font-display font-semibold text-ink-900">Más</p>
              <Link to="/pms-hotelero" className="text-ink-600 hover:text-ink-900">
                Qué es un PMS
              </Link>
              <Link to="/software-para-hoteles" className="text-ink-600 hover:text-ink-900">
                Software para hoteles
              </Link>
              <Link to="/terms" className="text-ink-600 hover:text-ink-900">
                Términos
              </Link>
              <Link to="/privacy" className="text-ink-600 hover:text-ink-900">
                Privacidad
              </Link>
            </nav>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default MarketingShell;
