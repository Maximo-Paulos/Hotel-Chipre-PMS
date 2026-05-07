import { useEffect, useMemo } from "react";
import cx from "clsx";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";

import { Seo } from "../components/Seo";
import { useOnboardingStatus } from "../hooks/useOnboardingStatus";
import { useSubscriptionStatus } from "../hooks/useSubscription";
import { useSession } from "../state/session";
import { ApiError, hasValidSession } from "../api/client";

import { HotelSelector } from "./HotelSelector";
import { UserBadge } from "./UserBadge";

type NavItem = {
  label: string;
  to: string;
  requiresRole?: Array<"owner" | "co_owner" | "manager" | "housekeeping" | "receptionist">;
  minPlan?: "starter" | "pro" | "ultra";
};

type NavSection = {
  title: string;
  items: NavItem[];
};

const baseNav = [
  {
    title: "Analytics",
    items: [
      { label: "Resumen", to: "/analytics" },
      { label: "Habitaciones", to: "/analytics/rooms", minPlan: "pro" },
      { label: "Segmentos", to: "/analytics/segments", minPlan: "pro" },
      { label: "Canales", to: "/analytics/channels", minPlan: "pro" },
      { label: "Operación", to: "/analytics/operations", minPlan: "pro" },
      { label: "Chat IA", to: "/analytics/ai-chat", minPlan: "ultra" },
      { label: "Companies", to: "/settings/companies", minPlan: "pro" },
      { label: "Room events", to: "/operacion/room-state-events", minPlan: "pro" }
    ]
  },
  {
    title: "Operacion",
    items: [
      { label: "Dashboard", to: "/dashboard" },
      { label: "Reservas", to: "/reservas" },
      { label: "Huespedes", to: "/huespedes" },
      { label: "Habitaciones", to: "/habitaciones" },
      { label: "Tarifas", to: "/operacion/tarifas" },
    ],
  },
  {
    title: "Proceso",
    items: [{ label: "Onboarding", to: "/onboarding" }],
  },
        {
          title: "Configuracion",
          items: [
            { label: "Usuarios", to: "/settings/users", requiresRole: ["owner", "co_owner"] },
            { label: "Asistente", to: "/settings/assistant", requiresRole: ["owner", "co_owner", "manager"] },
            { label: "Suscripcion", to: "/settings/subscription", requiresRole: ["owner", "co_owner"] },
            { label: "Companies", to: "/settings/companies", minPlan: "pro" },
            { label: "Conexiones", to: "/settings/connections", requiresRole: ["owner", "co_owner"] },
            { label: "Pruebas", to: "/settings/tests", requiresRole: ["owner", "co_owner"] },
            { label: "Hotel", to: "/settings/hotel", requiresRole: ["owner", "co_owner"] },
            { label: "Seguridad", to: "/settings/security", requiresRole: ["owner", "co_owner"] },
          ],
  },
];

const planRank: Record<"starter" | "pro" | "ultra", number> = {
  starter: 0,
  pro: 1,
  ultra: 2
};

const ACTIVE_SUBSCRIPTION_STATUSES = ["active", "trialing", "demo", "comped"];

export function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const { session } = useSession();
  const isLoggedIn = hasValidSession(session);
  const isVerified = Boolean(session.isVerified);
  const role = session.role;

  const { data: onboarding, isFetching, error } = useOnboardingStatus({ enabled: isLoggedIn && isVerified });
  const { data: subscription } = useSubscriptionStatus();
  const onboardingError = error as ApiError | undefined;

  useEffect(() => {
    if (!isLoggedIn) navigate("/login", { replace: true });
  }, [isLoggedIn, navigate]);

  useEffect(() => {
    if (isLoggedIn && !isVerified && location.pathname !== "/verify-email") {
      navigate("/verify-email", { replace: true });
    }
  }, [isLoggedIn, isVerified, location.pathname, navigate]);

  useEffect(() => {
    if (onboardingError?.status === 403) {
      navigate("/verify-email", { replace: true });
    }
  }, [onboardingError, navigate]);

  const capReached =
    subscription && subscription.room_limit > 0 && subscription.rooms_in_use >= subscription.room_limit;
  const capBanner =
    capReached &&
    `Limite de habitaciones alcanzado (${subscription.rooms_in_use}/${subscription.room_limit}). Ajusta tu plan en Configuracion > Suscripcion.`;
  const writeBlocked = subscription?.can_write === false;
  const inactiveSubscription =
    subscription && !ACTIVE_SUBSCRIPTION_STATUSES.includes(subscription.status);
  const subscriptionCTA = "/settings/subscription";

  const visibleNavSections = useMemo<NavSection[]>(() => {
    return baseNav
      .map((section) => {
        const items = section.items
          .filter((item) => !item.requiresRole || (role ? item.requiresRole.includes(role) : false))
          .filter((item) => !item.minPlan || (subscription?.plan ? (planRank[subscription.plan] ?? 0) >= (planRank[item.minPlan] ?? 0) : false))
          .filter((item) => !(item.to === "/onboarding" && onboarding?.completed));
        if (!items.length) return null;
        return { ...section, items } as NavSection;
      })
      .filter((section): section is NavSection => Boolean(section));
  }, [role, onboarding?.completed, subscription?.plan]);

  const path = location.pathname;
  if (role === "housekeeping" && path.startsWith("/settings")) return <Navigate to="/reservas" replace />;
  if (role === "manager" && path.startsWith("/settings") && path !== "/settings/assistant") {
    return <Navigate to="/reservas" replace />;
  }
  if (onboarding?.completed && path.startsWith("/onboarding")) return <Navigate to="/dashboard" replace />;

  if (!isLoggedIn) return <Navigate to="/login" replace />;
  if (isLoggedIn && !isVerified) return <Navigate to="/verify-email" replace />;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <Seo title="Hotel Chipre PMS | App" description="Acceso al sistema operativo de Hotel Chipre PMS." noindex />
      <div className="border-b bg-slate-900 px-6 py-2 text-xs text-white">
        <span className="font-semibold">Hotel Chipre PMS</span>
        <span className="ml-3 text-slate-200">Hotel ID {session.hotelId ?? "-"}</span>
        <span className="ml-3 text-slate-200">Usuario {session.email || session.userId || "Sin sesion"}</span>
      </div>

      {(writeBlocked || inactiveSubscription) && (
        <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-900">
          {writeBlocked ? "Suscripcion en modo solo lectura (can_write=false)." : "Suscripcion inactiva."}{" "}
          Plan: {subscription?.plan || "sin plan"} · Habitaciones: {subscription?.rooms_in_use}/{subscription?.room_limit}.{" "}
          <Link to={subscriptionCTA} className="font-semibold underline">
            Reactivar o cambiar plan
          </Link>
        </div>
      )}

      {capBanner && (
        <div className="border-b border-rose-200 bg-rose-50 px-6 py-2 text-sm text-rose-900">{capBanner}</div>
      )}

      {!isFetching && onboarding && !onboarding.completed && !location.pathname.startsWith("/onboarding") && (
        <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-900">
          Onboarding pendiente: {onboarding.missing_steps.join(", ") || "revisa los pasos"}.
          <button
            className="ml-3 text-amber-800 underline"
            onClick={() => navigate("/onboarding", { replace: true })}
            type="button"
          >
            Completar ahora
          </button>
        </div>
      )}

      {onboardingError && (
        <div className="border-b border-rose-200 bg-rose-50 px-6 py-2 text-sm text-rose-900">
          {onboardingError.status === 402
            ? "Suscripcion inactiva. Reactiva el plan para seguir usando el sistema."
            : onboardingError.status === 403
              ? "Debes verificar tu email para continuar."
              : "Sin conexion con el backend. Seguimos en modo offline para no bloquear la UI."}
        </div>
      )}

      <div className="flex min-h-[calc(100vh-80px)]">
        <aside className="hidden w-72 shrink-0 border-r border-slate-200 bg-white/90 backdrop-blur md:flex md:flex-col">
          <div className="px-5 pb-4 pt-6">
            <Link to="/dashboard" className="block">
              <img
                src="/brand/logo-full.png"
                alt="Hotel Chipre PMS"
                className="h-16 w-auto object-contain"
              />
            </Link>
            <p className="mt-2 text-xs text-slate-500">Layout de navegacion prototipo</p>
          </div>
          <nav className="flex-1 space-y-6 px-3 pb-6">
            {visibleNavSections.map((section) => (
              <div key={section.title}>
                <p className="px-2 text-xs uppercase tracking-wide text-slate-500">{section.title}</p>
                <div className="mt-2 flex flex-col gap-1">
                  {section.items.map((item) => (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      className={({ isActive }) =>
                        cx(
                          "flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium",
                          isActive ? "bg-brand-50 text-brand-700" : "text-slate-700 hover:bg-slate-100",
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
                <Link to="/dashboard" className="flex items-center gap-2 text-lg font-semibold text-slate-900 md:hidden">
                  <img
                    src="/brand/logo-avatar.png"
                    alt="Hotel Chipre PMS"
                    className="h-9 w-9 rounded-full border border-slate-200 object-cover"
                  />
                  <span className="leading-tight">Hotel Chipre PMS</span>
                </Link>
                <nav className="flex items-center gap-2 md:hidden">
                  {visibleNavSections.find((section) => section.title === "Analytics")?.items.map((item) => (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      className={({ isActive }) =>
                        cx(
                          "rounded-full px-3 py-1 text-xs font-semibold",
                          isActive ? "bg-brand-100 text-brand-800" : "bg-slate-100 text-slate-600",
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
