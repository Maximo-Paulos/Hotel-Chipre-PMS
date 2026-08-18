import { Suspense, useEffect, useMemo, useState } from "react";
import cx from "clsx";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";

import { ReservationDetailDrawer } from "../components/ReservationDetailDrawer";
import { ReservationGlobalSearch } from "../components/ReservationGlobalSearch";
import { Seo } from "../components/Seo";
import { useOnboardingStatus } from "../hooks/useOnboardingStatus";
import { useEffectivePermissions } from "../hooks/usePermissions";
import { useReservationDrawer } from "../hooks/useReservationDrawer";
import { useSubscriptionStatus } from "../hooks/useSubscription";
import { defaultPathForRole, useSession } from "../state/session";
import { ApiError, hasValidSession } from "../api/client";
import { useCrossTabSync } from "../sync/crossTabSync";

import { HotelSelector } from "./HotelSelector";
import { UserBadge, roleLabels } from "./UserBadge";

type NavItem = {
  label: string;
  to: string;
  requiresRole?: Array<"owner" | "co_owner" | "manager" | "housekeeping" | "receptionist">;
  requiresAnyPermission?: string[];
  requiresAllPermissions?: string[];
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
  { label: "Planilla", to: "/operacion/planilla", requiresRole: ["owner", "co_owner", "manager", "receptionist"] },
  { label: "Reservas", to: "/reservas", requiresRole: ["owner", "co_owner", "manager", "receptionist"], requiresAnyPermission: ["reservation:create", "checkin:perform"] },
  { label: "Huespedes", to: "/huespedes", requiresAnyPermission: ["guest:view"] },
  { label: "Habitaciones", to: "/habitaciones" },
  { label: "Caja", to: "/caja", requiresAnyPermission: ["cash:operate"] },
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
      { label: "Resumen", to: "/analytics", requiresRole: ["owner", "co_owner"] },
      { label: "Habitaciones", to: "/analytics/rooms", requiresRole: ["owner", "co_owner"], minPlan: "pro" },
      { label: "Segmentos", to: "/analytics/segments", requiresRole: ["owner", "co_owner"], minPlan: "pro" },
      { label: "Canales", to: "/analytics/channels", requiresRole: ["owner", "co_owner"], minPlan: "pro" },
      { label: "Operación", to: "/analytics/operations", requiresRole: ["owner", "co_owner", "manager"], requiresAnyPermission: ["reports:operational:view"], minPlan: "pro" },
      { label: "Chat IA", to: "/analytics/ai-chat", requiresRole: ["owner", "co_owner"], minPlan: "ultra" },
      { label: "Room events", to: "/operacion/room-state-events", requiresRole: ["owner", "co_owner", "manager"], requiresAnyPermission: ["reports:operational:view"], minPlan: "pro" }
    ]
  },
  {
    title: "Mas operacion",
    items: [
      { label: "Dashboard", to: "/dashboard", requiresRole: ["owner", "co_owner", "manager", "receptionist"] },
      { label: "Reportes", to: "/reportes", requiresAnyPermission: ["reports:operational:view"] },
      { label: "Lista de espera", to: "/operacion/lista-espera", requiresRole: ["owner", "co_owner", "manager", "receptionist"] },
      { label: "Lavanderia", to: "/operacion/lavanderia", requiresAnyPermission: ["laundry:operate_remitos", "laundry:manage_vendors"] },
      { label: "Stock", to: "/operacion/stock", requiresAnyPermission: ["stock:operate"] },
      { label: "Tarifas", to: "/operacion/tarifas", requiresRole: ["owner", "co_owner", "manager"] },
      { label: "Promociones", to: "/operacion/promociones", requiresRole: ["owner", "co_owner", "manager"], requiresAnyPermission: ["promotions:read"] },
      { label: "Onboarding", to: "/onboarding", requiresRole: ["owner", "co_owner"] },
    ],
  },
  {
    title: "Configuracion",
    items: [
      { label: "Usuarios", to: "/settings/users", requiresRole: ["owner", "co_owner"] },
      { label: "Asistente", to: "/settings/assistant", requiresRole: ["owner", "co_owner", "manager"] },
      { label: "Suscripcion", to: "/settings/subscription", requiresRole: ["owner", "co_owner"] },
      { label: "Empresas", to: "/settings/companies", requiresRole: ["owner", "co_owner"], minPlan: "pro" },
      { label: "API Keys", to: "/settings/api-keys", requiresRole: ["owner", "co_owner"], requiresAnyPermission: ["apikey:manage"] },
      { label: "Permisos", to: "/settings/permissions", requiresRole: ["owner", "co_owner"], requiresAnyPermission: ["permissions:manage"] },
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
  const realRole = session.baseRole ?? session.role;
  const isHousekeeping = realRole === "housekeeping";
  const homePath = defaultPathForRole(realRole);
  const { hasAnyPermission, hasAllPermissions } = useEffectivePermissions();
  const { reservationId: drawerReservationId, closeReservation } = useReservationDrawer();
  // The owner's phone-in-hand complaint (B7) was two competing mobile nav
  // mechanisms at once (a horizontal-scroll pill row + a separate native
  // <details> "Mas opciones" text link that doesn't read as a menu). One
  // recognizable menu button + one slide-over panel replaces both.
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useCrossTabSync();

  const { data: onboarding, isFetching, error } = useOnboardingStatus({
    enabled: isLoggedIn && isVerified && ["owner", "co_owner"].includes(realRole ?? "")
  });
  const { data: subscription } = useSubscriptionStatus({ enabled: !isHousekeeping });
  const onboardingError = error as ApiError | undefined;

  useEffect(() => {
    if (!isLoggedIn) navigate("/login", { replace: true });
  }, [isLoggedIn, navigate]);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

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
        .filter((item) => !item.requiresAnyPermission || hasAnyPermission(item.requiresAnyPermission))
        .filter((item) => !item.requiresAllPermissions || hasAllPermissions(item.requiresAllPermissions))
        .filter((item) => !item.minPlan || (subscription?.plan ? (planRank[subscription.plan as keyof typeof planRank] ?? 0) >= (planRank[item.minPlan] ?? 0) : false))
        .filter((item) => !(item.to === "/onboarding" && onboarding?.completed));
  }, [role, onboarding?.completed, subscription?.plan, hasAnyPermission, hasAllPermissions]);

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
          Vista previa como {roleLabels[session.role]} — no cambia permisos ni identidad; tus permisos efectivos siguen siendo
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

      {!isHousekeeping && (writeBlocked || inactiveSubscription) && (
        <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-900">
          {writeBlocked ? "Suscripcion en modo solo lectura (can_write=false)." : "Suscripcion inactiva."}{" "}
          Plan: {subscription?.plan || "sin plan"} · Habitaciones: {subscription?.rooms_in_use}/{subscription?.room_limit}.{" "}
          <Link to={subscriptionCTA} className="font-semibold underline">
            Reactivar o cambiar plan
          </Link>
        </div>
      )}

      {!isHousekeeping && capBanner && (
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
            <Link to={homePath} className="block">
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
            {/* B7 mobile: logo + a single recognizable menu button. No
                horizontal scroll, no second nav row competing for space --
                everything (daily links, grouped sections, search, hotel
                selector, user badge) lives in the slide-over panel below. */}
            <div className="flex items-center justify-between gap-3 px-4 py-3 md:hidden">
              <Link to={homePath} className="flex min-h-11 shrink-0 items-center text-slate-900">
                <img
                  src="/brand/logo-avatar.png"
                  alt="Hotel Chipre PMS"
                  className="h-9 w-9 rounded-full border border-slate-200 object-cover"
                />
              </Link>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(true)}
                aria-label="Abrir menú"
                aria-haspopup="true"
                aria-expanded={mobileMenuOpen}
                aria-controls="mobile-menu-panel"
                data-testid="mobile-menu-button"
                className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-100"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="h-5 w-5" aria-hidden="true">
                  <line x1="4" y1="6" x2="20" y2="6" />
                  <line x1="4" y1="12" x2="20" y2="12" />
                  <line x1="4" y1="18" x2="20" y2="18" />
                </svg>
              </button>
            </div>

            <div className="hidden px-4 py-3 md:flex md:items-center md:justify-end md:gap-3">
              {hasAnyPermission(["reservation:create", "checkin:perform"]) && <ReservationGlobalSearch />}
              <HotelSelector />
              <UserBadge />
            </div>
          </header>

          {mobileMenuOpen && (
            <div
              className="fixed inset-0 z-50 flex md:hidden"
              role="dialog"
              aria-modal="true"
              aria-label="Menú de navegación"
            >
              <div className="flex-1 animate-fade-in bg-black/30" onClick={() => setMobileMenuOpen(false)} />
              <div
                id="mobile-menu-panel"
                className="flex h-full w-full max-w-xs animate-slide-in-right flex-col overflow-y-auto border-l border-slate-200 bg-white shadow-xl"
              >
                <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
                  <span className="text-sm font-semibold text-slate-900">Menú</span>
                  <button
                    type="button"
                    onClick={() => setMobileMenuOpen(false)}
                    aria-label="Cerrar menú"
                    className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg text-xl leading-none text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                  >
                    ×
                  </button>
                </div>

                <nav aria-label="Navegación móvil" className="flex flex-col gap-1 px-3 py-3">
                  {visibleDailyNav.map((item) => (
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
                </nav>

                {visibleNavSections.map((section) => (
                  <nav key={section.title} aria-label={section.title} className="flex flex-col gap-1 border-t border-slate-100 px-3 py-3">
                    <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">{section.title}</p>
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
                  </nav>
                ))}

                <div className="flex flex-col gap-3 border-t border-slate-100 px-3 py-3">
                  {hasAnyPermission(["reservation:create", "checkin:perform"]) && <ReservationGlobalSearch />}
                  <HotelSelector />
                  <UserBadge />
                </div>
              </div>
            </div>
          )}

          <main className="min-w-0 flex-1 px-4 py-8 sm:px-8">
            <div className="mx-auto max-w-6xl min-w-0">
              <Suspense fallback={<p className="text-sm text-slate-500">Cargando...</p>}>
                <Outlet />
              </Suspense>
            </div>
          </main>
        </div>
      </div>

      {hasAnyPermission(["reservation:create", "checkin:perform"]) && (
        <ReservationDetailDrawer reservationId={drawerReservationId} onClose={closeReservation} />
      )}
    </div>
  );
}
