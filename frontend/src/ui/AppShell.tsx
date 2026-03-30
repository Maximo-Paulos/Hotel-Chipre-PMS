import { useEffect } from "react";
import { Link, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useOnboardingStatus } from "../hooks/useOnboardingStatus";
import { useSession } from "../state/session";

import { HotelSelector } from "./HotelSelector";
import { UserBadge } from "./UserBadge";

export function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const { session } = useSession();
  const isPublic = ["/login", "/register-owner", "/forgot-password", "/reset-password", "/verify-email"].includes(
    location.pathname
  );
  const isAuthenticated = session.userId !== "guest";

  const { data: onboarding, isFetching, error } = useOnboardingStatus({
    enabled: !isPublic && isAuthenticated
  });

  useEffect(() => {
    if (!isPublic && !isAuthenticated) {
      navigate("/login", { replace: true });
    }
  }, [isPublic, isAuthenticated, navigate]);

  useEffect(() => {
    if (!isPublic && onboarding && !onboarding.completed && !location.pathname.startsWith("/onboarding")) {
      navigate("/onboarding", { replace: true });
    }
  }, [isPublic, onboarding, location.pathname, navigate]);

  if (isPublic) return <Outlet />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="border-b bg-slate-900 px-6 py-2 text-sm text-white">
        <span className="font-semibold">Hotel Chipre PMS</span> - Hotel ID {session.hotelId} - Usuario{" "}
        {session.email || session.userId}
      </div>
      {!isFetching && onboarding && !onboarding.completed && (
        <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-900">
          Onboarding pendiente: {onboarding.missing_steps.join(", ") || "revisá los pasos"}.
          <button
            className="ml-3 text-amber-800 underline"
            onClick={() => navigate("/onboarding", { replace: true })}
            type="button"
          >
            Completar ahora
          </button>
        </div>
      )}
      {error && (
        <div className="border-b border-rose-200 bg-rose-50 px-6 py-2 text-sm text-rose-900">
          Sin conexión con el backend. Seguimos en modo offline para no bloquear la UI.
        </div>
      )}
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
