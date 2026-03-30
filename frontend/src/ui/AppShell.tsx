import { Outlet, Link, useLocation } from "react-router-dom";
import { HotelSelector } from "./HotelSelector";
import { UserBadge } from "./UserBadge";

export function AppShell() {
  const location = useLocation();
  const isPublic = ["/login", "/register-owner", "/forgot-password", "/reset-password", "/verify-email"].includes(
    location.pathname
  );

  if (isPublic) return <Outlet />;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-6">
            <Link to="/dashboard" className="text-lg font-semibold text-brand-700">
              Hotel Chipre PMS
            </Link>
            <nav className="flex items-center gap-4 text-sm text-slate-600">
              <Link to="/dashboard" className="hover:text-brand-700">
                Dashboard
              </Link>
              <Link to="/onboarding" className="hover:text-brand-700">
                Onboarding
              </Link>
              <Link to="/settings/users" className="hover:text-brand-700">
                Usuarios
              </Link>
              <Link to="/settings/hotel" className="hover:text-brand-700">
                Hotel
              </Link>
              <Link to="/settings/security" className="hover:text-brand-700">
                Seguridad
              </Link>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <HotelSelector />
            <UserBadge />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
