import clsx from "clsx";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect } from "react";

import { useOnboardingStatus } from "../hooks/useOnboardingStatus";
import { useSubscriptionStatus } from "../hooks/useSubscription";
import { useSession } from "../state/session";
import { HotelSelector } from "./HotelSelector";
import { UserBadge } from "./UserBadge";

const navSections = [
  {
    title: "Operación",
    items: [
      { label: "Dashboard", to: "/dashboard" },
      { label: "Reservas", to: "/reservas" },
      { label: "Habitaciones", to: "/habitaciones" }
    ]
  },
  {
    title: "Proceso",
    items: [{ label: "Onboarding", to: "/onboarding" }]
  },
  {
    title: "Configuración",
    items: [
      { label: "Usuarios", to: "/settings/users" },
      { label: "Hotel", to: "/settings/hotel" },
      { label: "Seguridad", to: "/settings/security" }
    ]
  }
];

export function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const { session } = useSession();
  const isLoggedIn = session.accessToken !== undefined && session.userId !== "guest";
  const isVerified = Boolean(session.isVerified);

  const { data: onboarding, isFetching, error } = useOnboardingStatus({ enabled: isLoggedIn && isVerified });
  const { data: subscription } = useSubscriptionStatus();

  useEffect(() => {
    if (!isLoggedIn) navigate("/login", { replace: true });
  }, [isLoggedIn, navigate]);

  useEffect(() => {
    if (isLoggedIn && !isVerified && location.pathname !== "/verify-email") navigate("/verify-email", { replace: true });
  }, [isLoggedIn, isVerified, location.pathname, navigate]);

  const role = session.role;
  const path = location.pathname;
  if (role === "housekeeping" && path.startsWith("/settings")) return <Navigate to="/reservas" replace />;
  if (role === "manager" && path.startsWith("/settings")) return <Navigate to="/reservas" replace />;

  if (!isLoggedIn) return <Navigate to="/login" replace />;
  if (isLoggedIn && !isVerified) return <Navigate to="/verify-email" replace />;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="border-b bg-slate-900 px-6 py-2 text-xs text-white">
        <span className="font-semibold">Hotel Chipre PMS</span>
        <span className="ml-3 text-slate-200">Hotel ID {session.hotelId}</span>
        <span className="ml-3 text-slate-200">Usuario {session.email || session.userId}</span>
      </div>

      {subscription && subscription.status !== "active" && (
        <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-900">
          Suscripción inactiva. Reactivá tu plan. Plan: {subscription.plan || "sin plan"} · Habitaciones: {subscription.rooms_in_use}/{subscription.room_limit}
        </div>
      )}

      {!isFetching && onboarding && !onboarding.completed && !location.pathname.startsWith("/onboarding") && (
        <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-900">
          Onboarding pendiente: {onboarding.missing_steps.join(", ") || "revisá los pasos"}.
          <button className="ml-3 text-amber-800 underline" onClick={() => navigate("/onboarding", { replace: true })} type="button">
            Completar ahora
          </button>
        </div>
      )}

      {error && (
        <div className="border-b border-rose-200 bg-rose-50 px-6 py-2 text-sm text-rose-900">
          Sin conexión con el backend. Seguimos en modo offline para no bloquear la UI.
        </div>
      )}

      <div className="flex min-h-[calc(100vh-80px)]">
        <aside className="hidden w-72 shrink-0 border-r border-slate-200 bg-white/90 backdrop-blur md:flex md:flex-col">
          <div className="px-5 pb-4 pt-6">
            <Link to="/dashboard" className="text-lg font-semibold text-slate-900">
              Hotel Chipre PMS
            </Link>
            <p className="text-xs text-slate-500">Layout de navegación prototipo</p>
          </div>
          <nav className="flex-1 space-y-6 px-3 pb-6">
            {navSections.map((section) => (
              <div key={section.title}>
                <p className="px-2 text-xs uppercase tracking-wide text-slate-500">{section.title}</p>
                <div className="mt-2 flex flex-col gap-1">
                  {section.items.map((item) => (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      className={({ isActive }) =>
                        clsx(
                          "flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium",
                          isActive ? "bg-brand-50 text-brand-700" : "text-slate-700 hover:bg-slate-100"
                        )
                      }
                    >
                      <span>{item.label}</span>
                    </NavLink>
                  ))}
                </div>
              </div>
            ))}
          </nav>
        </aside>

        <div className="flex min-h-screen flex-1 flex-col">
          <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
            <div className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <Link to="/dashboard" className="text-lg font-semibold text-slate-900 md:hidden">
                  Hotel Chipre PMS
                </Link>
                <nav className="flex items-center gap-2 md:hidden">
                  {navSections[0]?.items.map((item) => (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      className={({ isActive }) =>
                        clsx(
                          "rounded-full px-3 py-1 text-xs font-semibold",
                          isActive ? "bg-brand-100 text-brand-800" : "bg-slate-100 text-slate-600"
                        )
                      }
                    >
                      {item.label}
                    </NavLink>
                  ))}
                </nav>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <HotelSelector />
                <UserBadge />
              </div>
            </div>
          </header>

          <main className="flex-1 px-4 py-8 sm:px-8">
            <div className="mx-auto max-w-6xl">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
