import { Suspense, useEffect, useMemo, useState } from "react";
import cx from "clsx";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { NotificationsPanel } from "../components/NotificationsPanel";
import { ReservationDetailDrawer } from "../components/ReservationDetailDrawer";
import { ReservationGlobalSearch } from "../components/ReservationGlobalSearch";
import { Seo } from "../components/Seo";
import { useDialogA11y } from "../hooks/useDialogA11y";
import { useHotelConfig } from "../hooks/useHotelConfig";
import { useInstallPrompt } from "../hooks/useInstallPrompt";
import { useUnreadNotificationCount } from "../hooks/useNotifications";
import { useOnboardingStatus } from "../hooks/useOnboardingStatus";
import { useOnlineStatus } from "../hooks/useOnlineStatus";
import { useEffectivePermissions } from "../hooks/usePermissions";
import { useReservationDrawer } from "../hooks/useReservationDrawer";
import { useSubscriptionStatus } from "../hooks/useSubscription";
import { defaultPathForRole, useSession } from "../state/session";
import { ApiError, hasValidSession } from "../api/client";
import { useCrossTabSync, useRealtimeStatus } from "../sync/crossTabSync";
import { BrandMark } from "../components/brand/BrandMark";

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
// NavItem.label holds an i18n key (namespace "appshell"), resolved with t()
// at render time -- these arrays are module-level so they can't call the
// useTranslation() hook themselves.
const dailyNav: NavItem[] = [
  { label: "nav.daily.planning", to: "/operacion/planilla", requiresAnyPermission: ["occupancy:view"], hideForPreviewRoles: ["housekeeping"] },
  { label: "nav.daily.reservations", to: "/reservas", requiresAnyPermission: ["reservation:read"], hideForPreviewRoles: ["housekeeping"] },
  { label: "nav.daily.guests", to: "/huespedes", requiresAnyPermission: ["guest:read"], hideForPreviewRoles: ["housekeeping"] },
  { label: "nav.daily.rooms", to: "/habitaciones", requiresAnyPermission: ["room:read"] },
  { label: "nav.daily.tasks", to: "/operacion/tareas", requiresAnyPermission: ["operations:tasks:view", "operations:tasks:report", "operations:tasks:manage"] },
  { label: "nav.daily.cashRegister", to: "/caja", requiresAnyPermission: ["cash:view"], hideForPreviewRoles: ["housekeeping"] },
];

// Grouping criterion: "Analitica" is every reporting/dashboard page a manager
// checks periodically, not per-shift. "Mas operacion" is real day-to-day
// hotel work that isn't touched *every* shift (stock counts, laundry batches,
// waitlist, rate edits) plus Dashboard/Onboarding, which stay reachable here
// even though the daily row above and the logo link already cover the home
// screen. "Configuracion" is unchanged -- it was already its own group.
const groupedNav: NavSection[] = [
  {
    title: "nav.sections.analytics.title",
    items: [
      { label: "nav.sections.analytics.summary", to: "/analytics", requiresAnyPermission: ["analytics:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "nav.sections.analytics.rooms", to: "/analytics/rooms", requiresAnyPermission: ["analytics:advanced:view"], hideForPreviewRoles: ["housekeeping"], minPlan: "pro" },
      { label: "nav.sections.analytics.segments", to: "/analytics/segments", requiresAnyPermission: ["analytics:advanced:view"], hideForPreviewRoles: ["housekeeping"], minPlan: "pro" },
      { label: "nav.sections.analytics.channels", to: "/analytics/channels", requiresAnyPermission: ["analytics:advanced:view"], hideForPreviewRoles: ["housekeeping"], minPlan: "pro" },
      { label: "nav.sections.analytics.operations", to: "/analytics/operations", requiresAnyPermission: ["reports:operational:view"], hideForPreviewRoles: ["housekeeping"], minPlan: "pro" },
      { label: "nav.sections.analytics.aiChat", to: "/analytics/ai-chat", requiresAnyPermission: ["analytics:ai:view"], hideForPreviewRoles: ["housekeeping"], minPlan: "ultra" },
      { label: "nav.sections.analytics.roomEvents", to: "/operacion/room-state-events", requiresAnyPermission: ["reports:operational:view"], hideForPreviewRoles: ["housekeeping"], minPlan: "pro" }
    ]
  },
  {
    title: "nav.sections.moreOperations.title",
    items: [
      { label: "nav.sections.moreOperations.dashboard", to: "/dashboard", requiresAnyPermission: ["dashboard:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "nav.sections.moreOperations.reports", to: "/reportes", requiresAnyPermission: ["reports:operational:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "nav.sections.moreOperations.audit", to: "/operacion/auditoria", requiresAnyPermission: ["operations:audit:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "nav.sections.moreOperations.waitlist", to: "/operacion/lista-espera", requiresAnyPermission: ["waitlist:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "nav.sections.moreOperations.laundry", to: "/operacion/lavanderia", requiresAnyPermission: ["laundry:read"] },
      { label: "nav.sections.moreOperations.stock", to: "/operacion/stock", requiresAnyPermission: ["stock:read"], hideForPreviewRoles: ["housekeeping"] },
      { label: "nav.sections.moreOperations.rates", to: "/operacion/tarifas", requiresAnyPermission: ["rates:read"], hideForPreviewRoles: ["housekeeping"] },
      { label: "nav.sections.moreOperations.promotions", to: "/operacion/promociones", requiresAnyPermission: ["promotions:read"], hideForPreviewRoles: ["housekeeping"] },
      { label: "nav.sections.moreOperations.onboarding", to: "/onboarding", requiresAnyPermission: ["hotel_settings:update"], hideForPreviewRoles: ["housekeeping"] },
    ],
  },
  {
    title: "nav.sections.settings.title",
    items: [
      { label: "nav.sections.settings.users", to: "/settings/users", requiresAnyPermission: ["settings:users:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "nav.sections.settings.assistant", to: "/settings/assistant", requiresAnyPermission: ["settings:assistant:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "nav.sections.settings.subscription", to: "/settings/subscription", requiresAnyPermission: ["settings:subscription:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "nav.sections.settings.companies", to: "/settings/companies", requiresAnyPermission: ["company:view"], hideForPreviewRoles: ["housekeeping"], minPlan: "pro" },
      { label: "nav.sections.settings.apiKeys", to: "/settings/api-keys", requiresAnyPermission: ["apikey:manage"], hideForPreviewRoles: ["housekeeping"] },
      { label: "nav.sections.settings.permissions", to: "/settings/permissions", requiresAnyPermission: ["permissions:manage"], hideForPreviewRoles: ["housekeeping"] },
      { label: "nav.sections.settings.connections", to: "/settings/connections", requiresAnyPermission: ["settings:integrations:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "nav.sections.settings.tests", to: "/settings/tests", requiresAnyPermission: ["settings:tests:view"], hideForPreviewRoles: ["housekeeping"] },
      { label: "nav.sections.settings.hotel", to: "/settings/hotel", requiresAnyPermission: ["hotel_settings:read"], hideForPreviewRoles: ["housekeeping"] },
      { label: "nav.sections.settings.security", to: "/settings/security", requiresAnyPermission: ["settings:security:view"], hideForPreviewRoles: ["housekeeping"] },
      // Keep this presentation-only exception for the role preview. A real
      // housekeeping user with the permission must still see the link.
      { label: "nav.sections.settings.notifications", to: "/settings/notifications", requiresAnyPermission: ["settings:notifications:view"], hideForPreviewRoles: ["housekeeping"] },
    ],
  },
];

const planRank: Record<"starter" | "pro" | "ultra", number> = {
  starter: 0,
  pro: 1,
  ultra: 2
};

const ACTIVE_SUBSCRIPTION_STATUSES = ["active", "trialing", "demo", "comped"];

/**
 * The healthy realtime state, as a dot instead of a full-width banner.
 *
 * Nothing to act on means nothing to read: the label stays in the
 * accessibility tree and in the tooltip, so a screen reader and a hover both
 * still answer "is this live?", but the operator's screen is not spending a
 * strip of chrome to say everything is fine. The unhealthy states still take
 * the banner above.
 */
function RealtimeDot({ label }: { label: string }) {
  return (
    <span
      className="hidden items-center lg:inline-flex"
      data-testid="realtime-dot"
      role="status"
      aria-live="polite"
      title={label}
    >
      <span aria-hidden="true" className="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,0.15)]" />
      <span className="sr-only">{label}</span>
    </span>
  );
}

export function AppShell() {
  const { t } = useTranslation("appshell");
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
  const previewRole = role && role !== realRole ? role : null;
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
  const realtimeStatus = useRealtimeStatus();

  useCrossTabSync();
  // Mounted once here (not just on ReservationsPage, its only prior caller)
  // so a hotel's interface_language takes effect on every protected route,
  // including the Settings page where it's actually changed.
  const { data: hotelConfig } = useHotelConfig();

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
    t("subscription.capReached", { used: subscription.rooms_in_use, limit: subscription.room_limit });
  const writeBlocked = subscription?.can_write === false;
  const inactiveSubscription =
    subscription && !ACTIVE_SUBSCRIPTION_STATUSES.includes(subscription.status);
  const subscriptionCTA = "/settings/subscription";

  const filterItems = useMemo(() => {
    return (items: NavItem[]) =>
      items
        .filter((item) => !previewRole || !item.hideForPreviewRoles?.includes(previewRole))
        .filter((item) => !item.requiresAnyPermission || hasAnyPermission(item.requiresAnyPermission))
        .filter((item) => !item.requiresAllPermissions || hasAllPermissions(item.requiresAllPermissions))
        .filter((item) => !item.minPlan || (subscription?.plan ? (planRank[subscription.plan as keyof typeof planRank] ?? 0) >= (planRank[item.minPlan] ?? 0) : false))
        .filter((item) => !(item.to === "/onboarding" && onboarding?.completed));
  }, [previewRole, onboarding?.completed, subscription?.plan, hasAnyPermission, hasAllPermissions]);

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
    const lavanderia = groupedNav.flatMap((section) => section.items).find((item) => item.to === "/operacion/lavanderia");
    const candidates: NavItem[] = isHousekeeping
      ? [habitaciones, lavanderia].filter((item): item is NavItem => Boolean(item))
      : dailyNav.filter((item) => item.to !== "/caja");
    const links = filterItems(candidates).map((item): BottomNavTab => ({ kind: "link", label: t(item.label), to: item.to }));
    const tabs: BottomNavTab[] = [...links];
    if (isHousekeeping) {
      tabs.push({
        kind: "button",
        label: t("bottomNav.alerts"),
        onClick: () => setAlertsOpen(true),
        testId: "bottom-nav-alerts-button",
        badge: unreadNotifications > 0
      });
    }
    tabs.push({
      kind: "button",
      label: t("bottomNav.more"),
      onClick: () => setMobileMenuOpen(true),
      testId: "bottom-nav-more-button",
      active: mobileMenuOpen
    });
    return tabs;
  }, [isHousekeeping, filterItems, mobileMenuOpen, unreadNotifications, t]);

  const path = location.pathname;
  if (onboarding?.completed && path.startsWith("/onboarding")) return <Navigate to="/dashboard" replace />;

  if (!isLoggedIn) return <Navigate to="/login" replace />;
  if (isLoggedIn && !isVerified) return <Navigate to="/verify-email" replace />;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <Seo title={t("seo.title")} description={t("seo.description")} noindex />
      {/* The dark identity strip that used to sit here repeated three facts the
          shell already shows -- the brand mark in the sidebar, the hotel in
          HotelSelector, the address in UserBadge -- and cost ~34px of every
          screen to do it. A bar is for something the operator has to act on. */}

      {!isOnline && (
        <div
          className="border-b border-amber-300 bg-amber-100 px-4 py-3 text-sm text-amber-950 sm:px-6"
          data-testid="offline-banner"
          role="status"
          aria-live="assertive"
        >
          <strong>{t("offline.title")}</strong> {t("offline.description")}
        </div>
      )}

      {/* Realtime only takes a banner when it is NOT fine. A permanent green
          strip announcing that the connection works is chrome the operator
          reads past, and it cost another ~44px on every screen; the healthy
          state is a dot in the header instead (RealtimeDot below). The
          exception states keep the fixed min-height so the reconnect loop
          never shifts the layout under the operator's click. */}
      {realtimeStatus !== "disabled" && realtimeStatus !== "connected" && (
        <div
          className={cx(
            "flex min-h-[2.75rem] items-center border-b px-4 py-1.5 text-xs sm:px-6",
            realtimeStatus === "degraded"
              ? "border-amber-300 bg-amber-100 text-amber-950"
              : "border-sky-200 bg-sky-50 text-sky-900"
          )}
          data-testid="realtime-status"
          role="status"
          aria-live="polite"
        >
          {realtimeStatus === "connecting" && t("realtime.connecting")}
          {realtimeStatus === "reconnecting" && t("realtime.reconnecting")}
          {realtimeStatus === "degraded" && t("realtime.degraded")}
        </div>
      )}

      {session.role && session.baseRole && session.role !== session.baseRole && (
        <div
          className="border-b border-sky-200 bg-sky-50 px-6 py-2 text-sm text-sky-900"
          data-testid="viewing-as-banner"
        >
          {t("viewingAs.banner", { role: roleLabels[session.role], baseRole: roleLabels[session.baseRole] })}{" "}
          <button
            className="font-semibold underline"
            onClick={() => setRole(session.baseRole ?? null)}
            type="button"
            data-testid="reset-role-btn"
          >
            {t("viewingAs.reset")}
          </button>
        </div>
      )}

      {!isHousekeeping && (writeBlocked || inactiveSubscription) && (
        <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-900">
          {writeBlocked ? t("subscription.readOnly") : t("subscription.inactive")}{" "}
          {t("subscription.planSummary", {
            plan: subscription?.plan || t("subscription.noPlan"),
            used: subscription?.rooms_in_use,
            limit: subscription?.room_limit
          })}{" "}
          <Link to={subscriptionCTA} className="font-semibold underline">
            {t("subscription.reactivate")}
          </Link>
        </div>
      )}

      {!isHousekeeping && capBanner && (
        <div className="border-b border-rose-200 bg-rose-50 px-6 py-2 text-sm text-rose-900">{capBanner}</div>
      )}

      {!isFetching && onboarding && !onboarding.completed && !location.pathname.startsWith("/onboarding") && (
        <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-900">
          {t("onboarding.pending", { steps: onboarding.missing_steps.join(", ") || t("onboarding.pendingFallback") })}
          <button
            className="ml-3 text-amber-800 underline"
            onClick={() => navigate("/onboarding", { replace: true })}
            type="button"
          >
            {t("onboarding.completeNow")}
          </button>
        </div>
      )}

      {onboardingError && (
        <div className="border-b border-rose-200 bg-rose-50 px-6 py-2 text-sm text-rose-900">
          {onboardingError.status === 402
              ? t("onboarding.error402")
              : onboardingError.status === 403
                ? t("onboarding.error403")
                : t("onboarding.errorGeneric")}
        </div>
      )}

      {installPrompt.canInstall && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-emerald-200 bg-emerald-50 px-6 py-2 text-sm text-emerald-900">
          <span>{t("install.prompt")}</span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={installPrompt.promptInstall}
              className="min-h-11 rounded-lg border border-brand-600 bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-700"
            >
              {t("install.install")}
            </button>
            <button
              type="button"
              onClick={installPrompt.dismiss}
              className="min-h-11 rounded-lg border border-emerald-200 px-3 py-1.5 text-xs font-semibold text-emerald-800 hover:bg-emerald-100"
            >
              {t("install.dismiss")}
            </button>
          </div>
        </div>
      )}

      <div className="flex min-h-[calc(100vh-80px)]">
        <aside className="hidden w-72 shrink-0 border-r border-slate-200 bg-white/90 backdrop-blur md:flex md:flex-col">
          <div className="px-5 pb-4 pt-6">
            <Link to={homePath} className="block">
              <BrandMark />
            </Link>
            {/* Where am I: the active hotel, the way a Mac sidebar heads its
                list with the account it belongs to. It replaces a marketing
                tagline, and it is the one place the shell still names the
                hotel now that the single-hotel selector is gone. */}
            {hotelConfig?.hotel_name && (
              <p
                data-testid="active-hotel-name"
                className="mt-3 truncate text-sm font-semibold text-slate-800"
                title={hotelConfig.hotel_name}
              >
                {hotelConfig.hotel_name}
              </p>
            )}
          </div>
          <nav className="flex-1 space-y-4 px-3 pb-6">
            <div className="flex flex-col gap-1">
              {visibleDailyNav.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cx(
                      "flex items-center justify-between rounded-control px-3 py-2 text-sm font-medium",
                      isActive ? "bg-brand-50 text-brand-700" : "text-slate-700 hover:bg-slate-100",
                    )
                  }
                >
                  <span>{t(item.label)}</span>
                </NavLink>
              ))}
            </div>

            {/* B6.1: everything that isn't daily-use lives behind a native
                <details> disclosure per group -- no JS state, closed by
                default, and every route stays a click away instead of
                disappearing. */}
            {visibleNavSections.map((section) => (
              <details key={section.title} className="group">
                <summary className="flex cursor-pointer select-none list-none items-center justify-between rounded-control px-3 py-1.5 text-[13px] font-semibold text-slate-500 hover:bg-slate-100 hover:text-slate-700 [&::-webkit-details-marker]:hidden">
                  {t(section.title)}
                  <svg
                    viewBox="0 0 16 16"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.75"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="h-3.5 w-3.5 transition-transform duration-200 ease-rack group-open:rotate-90"
                    aria-hidden="true"
                  >
                    <path d="M6 4l4 4-4 4" />
                  </svg>
                </summary>
                <div className="mt-1 flex flex-col gap-1">
                  {section.items.map((item) => (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      className={({ isActive }) =>
                        cx(
                          "flex items-center justify-between rounded-control px-3 py-2 text-sm font-medium",
                          isActive ? "bg-brand-50 text-brand-700" : "text-slate-700 hover:bg-slate-100",
                        )
                      }
                    >
                      <span>{t(item.label)}</span>
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
                <BrandMark variant="mark" className="h-8 w-8" />
              </Link>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setAlertsOpen(true)}
                  aria-label={unreadNotifications > 0 ? t("alerts.viewUnread", { count: unreadNotifications }) : t("alerts.view")}
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
                  aria-label={t("mobileMenu.openMenu")}
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

            {/* Search is the tool, so it leads the row; status and identity sit
                on the trailing edge. `justify-between` instead of the old
                `justify-end` stops the search box from drifting into the
                controls as the viewport narrows. */}
            <div className="hidden px-4 py-3 md:flex md:items-center md:justify-between md:gap-3">
              {hasAnyPermission(["reservation:create", "checkin:perform"]) ? <ReservationGlobalSearch /> : <span />}
              <div className="flex items-center gap-3">
              {realtimeStatus === "connected" && <RealtimeDot label={t("realtime.connected")} />}
              <button
                type="button"
                onClick={() => setAlertsOpen(true)}
                aria-label={unreadNotifications > 0 ? t("alerts.viewUnread", { count: unreadNotifications }) : t("alerts.view")}
                className="relative inline-flex min-h-11 min-w-11 items-center justify-center rounded-control border border-slate-200 text-slate-700 transition hover:bg-slate-100 active:scale-[0.98]"
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
            </div>
          </header>

          {mobileMenuOpen && (
            <div
              className="fixed inset-0 z-50 flex md:hidden"
              role="dialog"
              aria-modal="true"
              aria-label={t("mobileMenu.ariaLabel")}
            >
              <div className="flex-1 animate-fade-in bg-black/30" onClick={() => setMobileMenuOpen(false)} />
              <div
                id="mobile-menu-panel"
                ref={mobileMenuPanelRef}
                tabIndex={-1}
                className="flex h-full w-full max-w-xs animate-slide-in-right flex-col overflow-y-auto border-l border-slate-200 bg-white shadow-xl outline-none"
              >
                <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
                  {/* Same "where am I" as the desktop sidebar header: without
                      it a single-hotel operator on a phone saw the hotel's name
                      nowhere once the one-option selector stopped rendering.
                      Long names wrap instead of pushing the panel wider. */}
                  <div className="min-w-0">
                    <span className="block text-sm font-semibold text-slate-900">{t("mobileMenu.title")}</span>
                    {hotelConfig?.hotel_name && (
                      <span data-testid="mobile-active-hotel-name" className="block break-words text-xs text-slate-500">
                        {hotelConfig.hotel_name}
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => setMobileMenuOpen(false)}
                    aria-label={t("mobileMenu.closeMenu")}
                    className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg text-xl leading-none text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                  >
                    ×
                  </button>
                </div>

                <nav aria-label={t("mobileMenu.navAriaLabel")} className="flex flex-col gap-1 px-3 py-3">
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
                      {t(item.label)}
                    </NavLink>
                  ))}
                </nav>

                {visibleNavSections.map((section) => (
                  <nav key={section.title} aria-label={t(section.title)} className="flex flex-col gap-1 border-t border-slate-100 px-3 py-3">
                    <p className="px-3 pb-1 text-[13px] font-semibold text-slate-500">{t(section.title)}</p>
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
                        {t(item.label)}
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
              <Suspense fallback={<p className="text-sm text-slate-500">{t("loading")}</p>}>
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
