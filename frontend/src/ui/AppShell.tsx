import { Suspense, useEffect, useMemo } from "react";
import cx from "clsx";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";

import { ReservationDetailDrawer } from "../components/ReservationDetailDrawer";
import { ReservationGlobalSearch } from "../components/ReservationGlobalSearch";
import { Seo } from "../components/Seo";
import { useOnboardingStatus } from "../hooks/useOnboardingStatus";
import { useReservationDrawer } from "../hooks/useReservationDrawer";
import { useSubscriptionStatus } from "../hooks/useSubscription";
import { useSession } from "../state/session";
import { ApiError, hasValidSession } from "../api/client";
import { useCrossTabSync } from "../sync/crossTabSync";

import { HotelSelector } from "./HotelSelector";
import { UserBadge, roleLabels } from "./UserBadge";

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

// B6.1: the user already decided the visible set -- only what a receptionist
// touches every single shift stays as a flat top-level link. Everything else
// (29 -> 5) moves into collapsible <details> sections below. The global
// reservation search (B1) is what makes this safe: any reservation is one
// search away regardless of which menu group it would have lived in, so the
// menu no longer has to list every route to keep it reachable.
const dailyNav: NavItem[] = [
  { label: "Planilla", to: "/operacion/planilla", requiresRole: ["owner", "co_owner", "manager", "housekeeping", "receptionist"] },
  { label: "Reservas", to: "/reservas" },
  { label: "Huespedes", to: "/huespedes" },
  { label: "Habitaciones", to: "/habitaciones" },
  { label: "Caja", to: "/caja", requiresRole: ["owner", "co_owner", "manager", "receptionist"] },
];

// Grouping criterion: "Analitica" is every reporting/dashboard page a manager
// checks periodically, not per-shift. "Mas operacion" is real day-to-day
// hotel work that isn't touched *every* shift (stock counts, laundry batches,
// waitlist, rate edits) plus Dashboard/Onboarding, which stay reachable here
// even though the daily row above and the logo link already cover the home
// screen. "Configuracion" is unchanged -- it was already its own group.
const groupedNav: NavSection[] = [
  {
    title: "Analitica",
    items: [
      { label: "Resumen", to: "/analytics" },
      { label: "Habitaciones", to: "/analytics/rooms", minPlan: "pro" },
      { label: "Segmentos", to: "/analytics/segments", minPlan: "pro" },
      { label: "Canales", to: "/analytics/channels", minPlan: "pro" },
      { label: "Operación", to: "/analytics/operations", minPlan: "pro" },
      { label: "Chat IA", to: "/analytics/ai-chat", minPlan: "ultra" },
      { label: "Room events", to: "/operacion/room-state-events", minPlan: "pro" }
    ]
  },
  {
    title: "Mas operacion",
    items: [
      { label: "Dashboard", to: "/dashboard" },
      { label: "Reportes", to: "/reportes", requiresRole: ["owner", "co_owner", "manager"] },
      { label: "Lista de espera", to: "/operacion/lista-espera", requiresRole: ["owner", "co_owner", "manager", "receptionist"] },
      { label: "Lavanderia", to: "/operacion/lavanderia", requiresRole: ["owner", "co_owner", "manager", "housekeeping"] },
      { label: "Stock", to: "/operacion/stock", requiresRole: ["owner", "co_owner", "manager"] },
      { label: "Tarifas", to: "/operacion/tarifas", requiresRole: ["owner", "co_owner", "manager"] },
      { label: "Onboarding", to: "/onboarding" },
    ],
  },
  {
    title: "Configuracion",
    items: [
      { label: "Usuarios", to: "/settings/users", requiresRole: ["owner", "co_owner"] },
      { label: "Asistente", to: "/settings/assistant", requiresRole: ["owner", "co_owner", "manager"] },
      { label: "Suscripcion", to: "/settings/subscription", requiresRole: ["owner", "co_owner"] },
      { label: "Empresas", to: "/settings/companies", requiresRole: ["owner", "co_owner"], minPlan: "pro" },
      { label: "API Keys", to: "/settings/api-keys", requiresRole: ["owner", "co_owner"] },
      { label: "Permisos", to: "/settings/permissions", requiresRole: ["owner", "co_owner"] },
      { label: "WhatsApp", to: "/settings/whatsapp", requiresRole: ["owner", "co_owner"] },
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
  const { session, setRole } = useSession();
  const isLoggedIn = hasValidSession(session);
  const isVerified = Boolean(session.isVerified);
  // C4: `role` here drives the "Cambiar vista" preview only (which nav items
  // show, which /settings sub-routes redirect away) -- it has no security
  // implication by itself: every route it reveals is a client-side link or
  // redirect, and the backend independently authorizes every real request
  // off `session.baseRole` via the JWT/HotelMembership, never off this
  // value. Pages that gate an actual mutation or a sensitive data fetch
  // (permissions matrix, API keys, WhatsApp secrets, stock adjustments,
  // check-in override, inviting/revoking users) read `session.baseRole`
  // instead -- see UserBadge/session.tsx and those pages' own comments.
  const role = session.role;
  const { reservationId: drawerReservationId, closeReservation } = useReservationDrawer();

  useCrossTabSync();

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

  const filterItems = useMemo(() => {
    return (items: NavItem[]) =>
      items
        .filter((item) => !item.requiresRole || (role ? item.requiresRole.includes(role) : false))
        .filter((item) => !item.minPlan || (subscription?.plan ? (planRank[subscription.plan as keyof typeof planRank] ?? 0) >= (planRank[item.minPlan] ?? 0) : false))
        .filter((item) => !(item.to === "/onboarding" && onboarding?.completed));
  }, [role, onboarding?.completed, subscription?.plan]);

  const visibleDailyNav = useMemo(() => filterItems(dailyNav), [filterItems]);

  const visibleNavSections = useMemo<NavSection[]>(() => {
    return groupedNav
      .map((section) => {
        const items = filterItems(section.items);
        if (!items.length) return null;
        return { ...section, items } as NavSection;
      })
      .filter((section): section is NavSection => Boolean(section));
  }, [filterItems]);

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
      <div className="flex flex-wrap gap-x-3 gap-y-1 border-b bg-slate-900 px-4 py-2 text-xs text-white sm:px-6">
        <span className="font-semibold">Hotel Chipre PMS</span>
        <span className="text-slate-200">Hotel ID {session.hotelId ?? "-"}</span>
        <span className="min-w-0 break-all text-slate-200">Usuario {session.email || session.userId || "Sin sesion"}</span>
      </div>

      {session.role && session.baseRole && session.role !== session.baseRole && (
        <div
          className="border-b border-sky-200 bg-sky-50 px-6 py-2 text-sm text-sky-900"
          data-testid="viewing-as-banner"
        >
          Viendo como {roleLabels[session.role]} — es solo una previsualizacion, tus permisos reales siguen siendo
          los de {roleLabels[session.baseRole]}.{" "}
          <button
            className="font-semibold underline"
            onClick={() => setRole(session.baseRole ?? null)}
            type="button"
            data-testid="reset-role-btn"
          >
            Volver a mi rol
          </button>
        </div>
      )}

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
          <nav className="flex-1 space-y-4 px-3 pb-6">
            <div className="flex flex-col gap-1">
              {visibleDailyNav.map((item) => (
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

            {/* B6.1: everything that isn't daily-use lives behind a native
                <details> disclosure per group -- no JS state, closed by
                default, and every route stays a click away instead of
                disappearing. */}
            {visibleNavSections.map((section) => (
              <details key={section.title} className="group">
                <summary className="cursor-pointer select-none rounded-lg px-2 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500 hover:bg-slate-100">
                  {section.title}
                </summary>
                <div className="mt-1 flex flex-col gap-1">
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
              </details>
            ))}
          </nav>
        </aside>

        <div className="flex min-h-screen min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
            <div className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex min-w-0 items-center gap-3">
                <Link to="/dashboard" className="flex min-h-11 shrink-0 items-center gap-2 text-lg font-semibold text-slate-900 md:hidden">
                  <img
                    src="/brand/logo-avatar.png"
                    alt="Hotel Chipre PMS"
                    className="h-9 w-9 rounded-full border border-slate-200 object-cover"
                  />
                  <span className="leading-tight">Hotel Chipre PMS</span>
                </Link>
                <nav aria-label="Navegación móvil" className="flex min-w-0 max-w-full flex-1 items-center gap-2 overflow-x-auto overscroll-x-contain md:hidden">
                  {visibleDailyNav.map((item) => (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      className={({ isActive }) =>
                        cx(
                          "inline-flex min-h-11 shrink-0 items-center rounded-full px-3 py-1 text-xs font-semibold",
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
                <ReservationGlobalSearch />
                <HotelSelector />
                <UserBadge />
              </div>
            </div>

            {/* B6.1 mobile: the 5 daily links above stay a horizontal-scroll
                bar (usable at 5 items, unlike the old 29). Everything else
                sits behind one native disclosure instead of widening that
                scroll bar further. */}
            {visibleNavSections.length > 0 && (
              <details className="border-t border-slate-100 px-4 py-2 md:hidden">
                <summary className="flex min-h-11 cursor-pointer select-none items-center text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Más opciones
                </summary>
                <nav aria-label="Más navegación móvil" className="mt-2 flex flex-col gap-4">
                  {visibleNavSections.map((section) => (
                    <div key={section.title}>
                      <p className="px-1 text-xs uppercase tracking-wide text-slate-400">{section.title}</p>
                      <div className="mt-1 flex flex-col gap-1">
                        {section.items.map((item) => (
                          <NavLink
                            key={item.to}
                            to={item.to}
                            className={({ isActive }) =>
                              cx(
                                "flex min-h-11 items-center rounded-lg px-3 py-2 text-sm font-medium",
                                isActive ? "bg-brand-50 text-brand-700" : "text-slate-700 hover:bg-slate-100",
                              )
                            }
                          >
                            {item.label}
                          </NavLink>
                        ))}
                      </div>
                    </div>
                  ))}
                </nav>
              </details>
            )}
          </header>

          <main className="min-w-0 flex-1 px-4 py-8 sm:px-8">
            <div className="mx-auto max-w-6xl min-w-0">
              <Suspense fallback={<p className="text-sm text-slate-500">Cargando...</p>}>
                <Outlet />
              </Suspense>
            </div>
          </main>
        </div>
      </div>

      <ReservationDetailDrawer reservationId={drawerReservationId} onClose={closeReservation} />
    </div>
  );
}
