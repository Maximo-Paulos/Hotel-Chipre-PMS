import { Suspense, useEffect, useMemo, useState } from "react";
import cx from "clsx";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";

import { NotificationsPanel } from "../components/NotificationsPanel";
import { ReservationDetailDrawer } from "../components/ReservationDetailDrawer";
import { ReservationGlobalSearch } from "../components/ReservationGlobalSearch";
import { Seo } from "../components/Seo";
import { useDialogA11y } from "../hooks/useDialogA11y";
import { useInstallPrompt } from "../hooks/useInstallPrompt";
import { useUnreadNotificationCount } from "../hooks/useNotifications";
import { useOnboardingStatus } from "../hooks/useOnboardingStatus";
import { useOnlineStatus } from "../hooks/useOnlineStatus";
import { useEffectivePermissions } from "../hooks/usePermissions";
import { useReservationDrawer } from "../hooks/useReservationDrawer";
import { useSubscriptionStatus } from "../hooks/useSubscription";
import { defaultPathForRole, useSession } from "../state/session";
import { ApiError, hasValidSession } from "../api/client";
import { useCrossTabSync } from "../sync/crossTabSync";

import { BottomNav, type BottomNavTab } from "./BottomNav";
import { HotelSelector } from "./HotelSelector";
import { UserBadge, roleLabels } from "./UserBadge";

type NavItem = {
  label: string;
  to: string;
  requiresAnyPermission?: string[];
  requiresAllPermissions?: string[];
  // Presentation-only narrowing for the role preview. This is deliberately
  // not an authorization check; PermissionGate uses the real baseRole.
  hideForPreviewRoles?: Array<"owner" | "co_owner" | "manager" | "housekeeping" | "receptionist">;
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
  { label: "Planilla", to: "/operacion/planilla", requiresAnyPermission: ["occupancy:view"], hideForPreviewRoles: ["housekeeping"] },
  { label: "Reservas", to: "/reservas", requiresAnyPermission: ["reservation:read"], hideForPreviewRoles: ["housekeeping"] },
  { label: "Huespedes", to: "/huespedes", requiresAnyPermission: ["guest:read"], hideForPreviewRoles: ["housekeeping"] },
  { label: "Habitaciones", to: "/habitaciones", requiresAnyPermission: ["room:read"] },
  { label: "Caja", to: "/caja", requiresAnyPermission: ["cash:view"], hideForPreviewRoles: ["housekeeping"] },
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
      { label: "Resumen", to: "/analytics", requiresAnyPermission: ["analytics:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "Habitaciones", to: "/analytics/rooms", requiresAnyPermission: ["analytics:advanced:view"], hideForPreviewRoles: ["housekeeping"], minPlan: "pro" },
      { label: "Segmentos", to: "/analytics/segments", requiresAnyPermission: ["analytics:advanced:view"], hideForPreviewRoles: ["housekeeping"], minPlan: "pro" },
      { label: "Canales", to: "/analytics/channels", requiresAnyPermission: ["analytics:advanced:view"], hideForPreviewRoles: ["housekeeping"], minPlan: "pro" },
      { label: "Operación", to: "/analytics/operations", requiresAnyPermission: ["reports:operational:view"], hideForPreviewRoles: ["housekeeping"], minPlan: "pro" },
      { label: "Chat IA", to: "/analytics/ai-chat", requiresAnyPermission: ["analytics:ai:view"], hideForPreviewRoles: ["housekeeping"], minPlan: "ultra" },
      { label: "Room events", to: "/operacion/room-state-events", requiresAnyPermission: ["reports:operational:view"], hideForPreviewRoles: ["housekeeping"], minPlan: "pro" }
    ]
  },
  {
    title: "Mas operacion",
    items: [
      { label: "Dashboard", to: "/dashboard", requiresAnyPermission: ["dashboard:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "Reportes", to: "/reportes", requiresAnyPermission: ["reports:operational:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "Lista de espera", to: "/operacion/lista-espera", requiresAnyPermission: ["waitlist:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "Lavanderia", to: "/operacion/lavanderia", requiresAnyPermission: ["laundry:read"] },
      { label: "Stock", to: "/operacion/stock", requiresAnyPermission: ["stock:read"], hideForPreviewRoles: ["housekeeping"] },
      { label: "Tarifas", to: "/operacion/tarifas", requiresAnyPermission: ["rates:read"], hideForPreviewRoles: ["housekeeping"] },
      { label: "Promociones", to: "/operacion/promociones", requiresAnyPermission: ["promotions:read"], hideForPreviewRoles: ["housekeeping"] },
      { label: "Onboarding", to: "/onboarding", requiresAnyPermission: ["hotel_settings:update"], hideForPreviewRoles: ["housekeeping"] },
    ],
  },
  {
    title: "Configuracion",
    items: [
      { label: "Usuarios", to: "/settings/users", requiresAnyPermission: ["settings:users:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "Asistente", to: "/settings/assistant", requiresAnyPermission: ["settings:assistant:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "Suscripcion", to: "/settings/subscription", requiresAnyPermission: ["settings:subscription:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "Empresas", to: "/settings/companies", requiresAnyPermission: ["company:view"], hideForPreviewRoles: ["housekeeping"], minPlan: "pro" },
      { label: "API Keys", to: "/settings/api-keys", requiresAnyPermission: ["apikey:manage"], hideForPreviewRoles: ["housekeeping"] },
      { label: "Permisos", to: "/settings/permissions", requiresAnyPermission: ["permissions:manage"], hideForPreviewRoles: ["housekeeping"] },
      { label: "Conexiones", to: "/settings/connections", requiresAnyPermission: ["settings:integrations:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "Pruebas", to: "/settings/tests", requiresAnyPermission: ["settings:tests:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "Hotel", to: "/settings/hotel", requiresAnyPermission: ["hotel_settings:read"], hideForPreviewRoles: ["housekeeping"] },
      { label: "Seguridad", to: "/settings/security", requiresAnyPermission: ["settings:security:view"], hideForPreviewRoles: ["housekeeping"] },
      // Housekeeping's menu is deliberately minimal even if an administrator
      // grants it another read permission: it stays inside rooms and laundry.
      { label: "Notificaciones", to: "/settings/notifications", requiresAnyPermission: ["settings:notifications:view"], hideForPreviewRoles: ["housekeeping"] },
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
  const [alertsOpen, setAlertsOpen] = useState(false);
  const mobileMenuPanelRef = useDialogA11y(mobileMenuOpen, () => setMobileMenuOpen(false));
  const installPrompt = useInstallPrompt();
  const isOnline = useOnlineStatus();
  const unreadNotifications = useUnreadNotificationCount();

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
        .filter((item) => !item.hideForPreviewRoles || (role ? !item.hideForPreviewRoles.includes(role) : false))
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

  // Mobile bottom nav: reuses the exact same NavItem objects (and filterItems
  // gating) as the desktop sidebar/slide-over -- one permission model, not a
  // parallel one. Housekeeping gets its own small set (Habitaciones,
  // Lavanderia) instead of the operator set (Planilla/Reservas/Huespedes)
  // because those routes are role-gated away from housekeeping already (see
  // router.tsx); an item that isn't allowed simply never enters the list,
  // same as "disappears automatically" on desktop.
  const bottomNavTabs = useMemo<BottomNavTab[]>(() => {
    const habitaciones = dailyNav.find((item) => item.to === "/habitaciones");
    const lavanderia = groupedNav.flatMap((section) => section.items).find((item) => item.label === "Lavanderia");
    const candidates: NavItem[] = isHousekeeping
      ? [habitaciones, lavanderia].filter((item): item is NavItem => Boolean(item))
      : dailyNav.filter((item) => item.to !== "/caja");
    const links = filterItems(candidates).map((item): BottomNavTab => ({ kind: "link", label: item.label, to: item.to }));
    const tabs: BottomNavTab[] = [...links];
    if (isHousekeeping) {
      tabs.push({
        kind: "button",
        label: "Alertas",
        onClick: () => setAlertsOpen(true),
        testId: "bottom-nav-alerts-button",
        badge: unreadNotifications > 0
      });
    }
    tabs.push({
      kind: "button",
      label: "Más",
      onClick: () => setMobileMenuOpen(true),
      testId: "bottom-nav-more-button",
      active: mobileMenuOpen
    });
    return tabs;
  }, [isHousekeeping, filterItems, mobileMenuOpen, unreadNotifications]);

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

      {!isOnline && (
        <div
          className="border-b border-amber-300 bg-amber-100 px-4 py-3 text-sm text-amber-950 sm:px-6"
          data-testid="offline-banner"
          role="status"
          aria-live="assertive"
        >
          <strong>Sin conexión.</strong> Los datos visibles pueden estar desactualizados. Las acciones de reservas, check-in/out y
          cobros requieren conexión y no se guardan para reintentar automáticamente.
        </div>
      )}

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
                : "No se pudo conectar con el backend. Los datos visibles pueden estar desactualizados; las acciones de escritura requieren reconexión."}
        </div>
      )}

      {installPrompt.canInstall && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-emerald-200 bg-emerald-50 px-6 py-2 text-sm text-emerald-900">
          <span>Instalá Hotel Chipre PMS en este dispositivo para acceso rápido.</span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={installPrompt.promptInstall}
              className="min-h-11 rounded-lg border border-emerald-300 bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700"
            >
              Instalar
            </button>
            <button
              type="button"
              onClick={installPrompt.dismiss}
              className="min-h-11 rounded-lg border border-emerald-200 px-3 py-1.5 text-xs font-semibold text-emerald-800 hover:bg-emerald-100"
            >
              Ahora no
            </button>
          </div>
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
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setAlertsOpen(true)}
                  aria-label={unreadNotifications > 0 ? `Ver alertas (${unreadNotifications} sin leer)` : "Ver alertas"}
                  data-testid="mobile-alerts-button"
                  className="relative inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-100"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5" aria-hidden="true">
                    <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
                    <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                  </svg>
                  {unreadNotifications > 0 && (
                    <span
                      aria-hidden="true"
                      data-testid="notifications-badge"
                      className="absolute right-1.5 top-1.5 h-2.5 w-2.5 rounded-full bg-rose-600"
                    />
                  )}
                </button>
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
            </div>

            <div className="hidden px-4 py-3 md:flex md:items-center md:justify-end md:gap-3">
              {hasAnyPermission(["reservation:create", "checkin:perform"]) && <ReservationGlobalSearch />}
              <button
                type="button"
                onClick={() => setAlertsOpen(true)}
                aria-label={unreadNotifications > 0 ? `Ver alertas (${unreadNotifications} sin leer)` : "Ver alertas"}
                className="relative inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-100"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5" aria-hidden="true">
                  <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
                  <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                </svg>
                {unreadNotifications > 0 && (
                  <span aria-hidden="true" className="absolute right-1.5 top-1.5 h-2.5 w-2.5 rounded-full bg-rose-600" />
                )}
              </button>
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
                ref={mobileMenuPanelRef}
                tabIndex={-1}
                className="flex h-full w-full max-w-xs animate-slide-in-right flex-col overflow-y-auto border-l border-slate-200 bg-white shadow-xl outline-none"
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

          {/* Bottom padding clears the fixed BottomNav (56px tall) plus the
              home-indicator safe area on notched phones; md+ keeps the
              original padding since the bottom nav is md:hidden there. */}
          <main className="min-w-0 flex-1 px-4 pb-[calc(56px+env(safe-area-inset-bottom)+1.5rem)] pt-8 sm:px-8 md:pb-8">
            <div className="mx-auto max-w-6xl min-w-0">
              <Suspense fallback={<p className="text-sm text-slate-500">Cargando...</p>}>
                <Outlet />
              </Suspense>
            </div>
          </main>
        </div>
      </div>

      <BottomNav tabs={bottomNavTabs} />

      {hasAnyPermission(["reservation:create", "checkin:perform"]) && (
        <ReservationDetailDrawer reservationId={drawerReservationId} onClose={closeReservation} />
      )}

      <NotificationsPanel open={alertsOpen} onClose={() => setAlertsOpen(false)} />
    </div>
  );
}
