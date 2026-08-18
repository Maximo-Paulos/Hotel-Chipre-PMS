import { lazy, useEffect, type ReactNode } from "react";
import { createBrowserRouter, Navigate, useLocation } from "react-router-dom";

import { isAppHostname, resolveAppLocation, resolveSiteLocation } from "./config/publicUrls";
import { useOnboardingStatus } from "./hooks/useOnboardingStatus";
import { useSession } from "./state/session";
import { AppShell } from "./ui/AppShell";
import { PermissionGate } from "./components/PermissionGate";
import { FaqPage } from "./views/public/FaqPage";
import { FunctionsPage } from "./views/public/FunctionsPage";
import { MarketingHomePage } from "./views/public/MarketingHomePage";
import { PmsHoteleroPage } from "./views/public/PmsHoteleroPage";
import { PricingPage as PricingPageView } from "./views/public/PricingPage";
import { SoftwareParaHotelesPage } from "./views/public/SoftwareParaHotelesPage";
import {
  MasterAdminProtectedShell,
  MasterAdminRoot
} from "./master_admin/layout";

// Marketing pages stay eager: they render on hotels-pms.com for SEO/first paint,
// and are excluded from the app-host bundle path entirely (see appRoutes below).

// Auth/public app-host pages: no SEO need, safe to lazy-load.
const LoginPage = lazy(() => import("./views/public/LoginPage").then((m) => ({ default: m.LoginPage })));
const RegisterOwnerPage = lazy(() =>
  import("./views/public/RegisterOwnerPage").then((m) => ({ default: m.RegisterOwnerPage }))
);
const ForgotPasswordPage = lazy(() =>
  import("./views/public/ForgotPasswordPage").then((m) => ({ default: m.ForgotPasswordPage }))
);
const ResetPasswordPage = lazy(() =>
  import("./views/public/ResetPasswordPage").then((m) => ({ default: m.ResetPasswordPage }))
);
const AcceptInvitationPage = lazy(() =>
  import("./views/public/AcceptInvitationPage").then((m) => ({ default: m.AcceptInvitationPage }))
);
const VerifyEmailPage = lazy(() =>
  import("./views/public/VerifyEmailPage").then((m) => ({ default: m.VerifyEmailPage }))
);

// Protected app pages.
const CashRegisterPage = lazy(() =>
  import("./views/protected/CashRegisterPage").then((m) => ({ default: m.CashRegisterPage }))
);
const CompaniesPage = lazy(() =>
  import("./views/protected/CompaniesPage").then((m) => ({ default: m.CompaniesPage }))
);
const DashboardPage = lazy(() =>
  import("./views/protected/DashboardPage").then((m) => ({ default: m.DashboardPage }))
);
const GuestsPage = lazy(() => import("./views/protected/GuestsPage").then((m) => ({ default: m.GuestsPage })));
const LaundryPage = lazy(() => import("./views/protected/LaundryPage").then((m) => ({ default: m.LaundryPage })));
const OccupancyPlanningPage = lazy(() =>
  import("./views/protected/OccupancyPlanningPage").then((m) => ({ default: m.OccupancyPlanningPage }))
);
const RateCalendarPage = lazy(() =>
  import("./views/protected/RateCalendarPage").then((m) => ({ default: m.RateCalendarPage }))
);
const PromotionsPage = lazy(() =>
  import("./views/protected/PromotionsPage").then((m) => ({ default: m.PromotionsPage }))
);
const ReservationsPage = lazy(() =>
  import("./views/protected/ReservationsPage").then((m) => ({ default: m.ReservationsPage }))
);
const ReportsPage = lazy(() => import("./views/protected/ReportsPage").then((m) => ({ default: m.ReportsPage })));
const RoomsPage = lazy(() => import("./views/protected/RoomsPage").then((m) => ({ default: m.RoomsPage })));
const SettingsAssistantPage = lazy(() => import("./views/protected/SettingsAssistantPage"));
const SettingsSubscriptionPage = lazy(() => import("./views/protected/SettingsSubscriptionPage"));
const SettingsConnectionsPage = lazy(() =>
  import("./views/protected/SettingsConnectionsPage").then((m) => ({ default: m.SettingsConnectionsPage }))
);
const SettingsHotelPage = lazy(() => import("./views/protected/SettingsHotelPage"));
const SettingsSecurityPage = lazy(() =>
  import("./views/protected/SettingsSecurityPage").then((m) => ({ default: m.SettingsSecurityPage }))
);
const SettingsTestsPage = lazy(() => import("./views/protected/SettingsTestsPage"));
const SettingsUsersPage = lazy(() =>
  import("./views/protected/SettingsUsersPage").then((m) => ({ default: m.SettingsUsersPage }))
);
const SettingsApiKeysPage = lazy(() =>
  import("./views/protected/SettingsApiKeysPage").then((m) => ({ default: m.SettingsApiKeysPage }))
);
const SettingsPermissionsPage = lazy(() =>
  import("./views/protected/SettingsPermissionsPage").then((m) => ({ default: m.SettingsPermissionsPage }))
);
const SettingsWhatsAppPage = lazy(() =>
  import("./views/protected/SettingsWhatsAppPage").then((m) => ({ default: m.SettingsWhatsAppPage }))
);
const StockPage = lazy(() => import("./views/protected/StockPage").then((m) => ({ default: m.StockPage })));
const WaitlistPage = lazy(() => import("./views/protected/WaitlistPage").then((m) => ({ default: m.WaitlistPage })));
const OnboardingWizard = lazy(() =>
  import("./views/onboarding/OnboardingWizard").then((m) => ({ default: m.OnboardingWizard }))
);

// Analytics pages all live in one file; Vite splits it into a single shared chunk
// loaded once on first visit to any /analytics/* route.
const AnalyticsHomePage = lazy(() =>
  import("./views/protected/analytics/AnalyticsPages").then((m) => ({ default: m.AnalyticsHomePage }))
);
const AnalyticsRoomsPage = lazy(() =>
  import("./views/protected/analytics/AnalyticsPages").then((m) => ({ default: m.AnalyticsRoomsPage }))
);
const AnalyticsRoomDetailPage = lazy(() =>
  import("./views/protected/analytics/AnalyticsPages").then((m) => ({ default: m.AnalyticsRoomDetailPage }))
);
const AnalyticsCategoryDetailPage = lazy(() =>
  import("./views/protected/analytics/AnalyticsPages").then((m) => ({ default: m.AnalyticsCategoryDetailPage }))
);
const AnalyticsSegmentsPage = lazy(() =>
  import("./views/protected/analytics/AnalyticsPages").then((m) => ({ default: m.AnalyticsSegmentsPage }))
);
const AnalyticsCompanyDetailPage = lazy(() =>
  import("./views/protected/analytics/AnalyticsPages").then((m) => ({ default: m.AnalyticsCompanyDetailPage }))
);
const AnalyticsChannelsPage = lazy(() =>
  import("./views/protected/analytics/AnalyticsPages").then((m) => ({ default: m.AnalyticsChannelsPage }))
);
const AnalyticsOperationsPage = lazy(() =>
  import("./views/protected/analytics/AnalyticsPages").then((m) => ({ default: m.AnalyticsOperationsPage }))
);
const AnalyticsAIChatPage = lazy(() =>
  import("./views/protected/analytics/AnalyticsPages").then((m) => ({ default: m.AnalyticsAIChatPage }))
);
const RoomStateEventsPage = lazy(() =>
  import("./views/protected/analytics/AnalyticsPages").then((m) => ({ default: m.RoomStateEventsPage }))
);

// Master admin pages.
const MasterAdminAuditPage = lazy(() =>
  import("./master_admin/pages/AuditPage").then((m) => ({ default: m.MasterAdminAuditPage }))
);
const MasterAdminBillingPage = lazy(() =>
  import("./master_admin/pages/BillingPage").then((m) => ({ default: m.MasterAdminBillingPage }))
);
const MasterAdminDashboardPage = lazy(() =>
  import("./master_admin/pages/DashboardPage").then((m) => ({ default: m.MasterAdminDashboardPage }))
);
const MasterAdminEmailPage = lazy(() =>
  import("./master_admin/pages/EmailPage").then((m) => ({ default: m.MasterAdminEmailPage }))
);
const MasterAdminLoginPage = lazy(() =>
  import("./master_admin/pages/LoginPage").then((m) => ({ default: m.MasterAdminLoginPage }))
);
const MasterAdminStripePage = lazy(() =>
  import("./master_admin/pages/StripePage").then((m) => ({ default: m.MasterAdminStripePage }))
);

const APP_HOST = isAppHostname();

function HostRedirect({ target }: { target: string }) {
  useEffect(() => {
    if (typeof window !== "undefined" && window.location.href !== target) {
      window.location.replace(target);
    }
  }, [target]);

  return null;
}

function MarketingRedirect({ children }: { children: ReactNode }) {
  const location = useLocation();

  if (APP_HOST) {
    return (
      <HostRedirect
        target={resolveSiteLocation(location.pathname, location.search, location.hash)}
      />
    );
  }
  return <>{children}</>;
}

function AppHostOnly({ children }: { children: ReactNode }) {
  const location = useLocation();

  if (!APP_HOST) {
    return (
      <HostRedirect
        target={resolveAppLocation(location.pathname, location.search, location.hash)}
      />
    );
  }

  return <>{children}</>;
}

function OnboardingGate() {
  const { session } = useSession();
  const { data, isFetching } = useOnboardingStatus({ enabled: Boolean(session.accessToken) });
  if (isFetching) return null;
  if (data?.completed) return <Navigate to="/dashboard" replace />;
  return <OnboardingWizard />;
}

const appRoutes = APP_HOST
  ? [
      {
        path: "/",
        element: <AppShell />,
        children: [
          { index: true, element: <Navigate to="/dashboard" replace /> },
          { path: "analytics", element: <PermissionGate roles={["owner", "co_owner"]}><AnalyticsHomePage /></PermissionGate> },
          { path: "analytics/rooms", element: <PermissionGate roles={["owner", "co_owner"]}><AnalyticsRoomsPage /></PermissionGate> },
          { path: "analytics/rooms/:roomId", element: <PermissionGate roles={["owner", "co_owner"]}><AnalyticsRoomDetailPage /></PermissionGate> },
          { path: "analytics/categories/:categoryId", element: <PermissionGate roles={["owner", "co_owner"]}><AnalyticsCategoryDetailPage /></PermissionGate> },
          { path: "analytics/segments", element: <PermissionGate roles={["owner", "co_owner"]}><AnalyticsSegmentsPage /></PermissionGate> },
          { path: "analytics/companies/:companyId", element: <PermissionGate roles={["owner", "co_owner"]}><AnalyticsCompanyDetailPage /></PermissionGate> },
          { path: "analytics/channels", element: <PermissionGate roles={["owner", "co_owner"]}><AnalyticsChannelsPage /></PermissionGate> },
          { path: "analytics/operations", element: <PermissionGate roles={["owner", "co_owner", "manager"]} anyPermission={["reports:operational:view"]}><AnalyticsOperationsPage /></PermissionGate> },
          { path: "analytics/ai-chat", element: <PermissionGate roles={["owner", "co_owner"]}><AnalyticsAIChatPage /></PermissionGate> },
          { path: "settings/companies", element: <PermissionGate roles={["owner", "co_owner"]} anyPermission={["company:manage"]}><CompaniesPage /></PermissionGate> },
          { path: "operacion/room-state-events", element: <PermissionGate roles={["owner", "co_owner", "manager"]} anyPermission={["reports:operational:view"]}><RoomStateEventsPage /></PermissionGate> },
          { path: "dashboard", element: <PermissionGate roles={["owner", "co_owner", "manager", "receptionist"]}><DashboardPage /></PermissionGate> },
          { path: "huespedes", element: <PermissionGate anyPermission={["guest:view"]}><GuestsPage /></PermissionGate> },
          { path: "reservas", element: <PermissionGate roles={["owner", "co_owner", "manager", "receptionist"]} anyPermission={["reservation:create", "checkin:perform"]}><ReservationsPage /></PermissionGate> },
          { path: "operacion/planilla", element: <PermissionGate roles={["owner", "co_owner", "manager", "receptionist"]}><OccupancyPlanningPage /></PermissionGate> },
          { path: "habitaciones", element: <RoomsPage /> },
          { path: "caja", element: <PermissionGate anyPermission={["cash:operate"]}><CashRegisterPage /></PermissionGate> },
          { path: "reportes", element: <PermissionGate anyPermission={["reports:operational:view"]}><ReportsPage /></PermissionGate> },
          { path: "operacion/lista-espera", element: <PermissionGate roles={["owner", "co_owner", "manager", "receptionist"]}><WaitlistPage /></PermissionGate> },
          { path: "operacion/lavanderia", element: <PermissionGate anyPermission={["laundry:operate_remitos", "laundry:manage_vendors"]}><LaundryPage /></PermissionGate> },
          { path: "operacion/stock", element: <PermissionGate anyPermission={["stock:operate"]}><StockPage /></PermissionGate> },
          { path: "operacion/tarifas", element: <PermissionGate roles={["owner", "co_owner", "manager"]}><RateCalendarPage /></PermissionGate> },
          { path: "operacion/promociones", element: <PermissionGate roles={["owner", "co_owner", "manager"]} anyPermission={["promotions:read"]}><PromotionsPage /></PermissionGate> },
          { path: "onboarding/*", element: <PermissionGate roles={["owner", "co_owner"]}><OnboardingGate /></PermissionGate> },
          { path: "settings", element: <PermissionGate roles={["owner", "co_owner"]}><Navigate to="/settings/users" replace /></PermissionGate> },
          { path: "settings/users", element: <PermissionGate roles={["owner", "co_owner"]}><SettingsUsersPage /></PermissionGate> },
          { path: "settings/api-keys", element: <PermissionGate roles={["owner", "co_owner"]} anyPermission={["apikey:manage"]}><SettingsApiKeysPage /></PermissionGate> },
          { path: "settings/permissions", element: <PermissionGate roles={["owner", "co_owner"]} anyPermission={["permissions:manage"]}><SettingsPermissionsPage /></PermissionGate> },
          { path: "settings/whatsapp", element: <PermissionGate roles={["owner", "co_owner"]}><SettingsWhatsAppPage /></PermissionGate> },
          { path: "settings/assistant", element: <PermissionGate roles={["owner", "co_owner", "manager"]}><SettingsAssistantPage /></PermissionGate> },
          { path: "settings/subscription", element: <PermissionGate roles={["owner", "co_owner"]}><SettingsSubscriptionPage /></PermissionGate> },
          { path: "settings/connections", element: <PermissionGate roles={["owner", "co_owner"]}><SettingsConnectionsPage /></PermissionGate> },
          { path: "settings/tests", element: <PermissionGate roles={["owner", "co_owner"]}><SettingsTestsPage /></PermissionGate> },
          { path: "settings/hotel", element: <PermissionGate roles={["owner", "co_owner"]}><SettingsHotelPage /></PermissionGate> },
          { path: "settings/security", element: <PermissionGate roles={["owner", "co_owner"]}><SettingsSecurityPage /></PermissionGate> }
        ]
      },
      {
        path: "/adminpmsmaster",
        element: <MasterAdminRoot />,
        children: [
          { index: true, element: <MasterAdminLoginPage /> },
          { path: "login", element: <MasterAdminLoginPage /> },
          {
            element: <MasterAdminProtectedShell />,
            children: [
              { path: "dashboard", element: <MasterAdminDashboardPage /> },
              { path: "billing", element: <MasterAdminBillingPage /> },
              { path: "email", element: <MasterAdminEmailPage /> },
              { path: "stripe", element: <MasterAdminStripePage /> },
              { path: "audit", element: <MasterAdminAuditPage /> }
            ]
          }
        ]
      }
    ]
  : [];

const publicRoutes = [
  ...(APP_HOST
    ? []
    : [
        {
          path: "/",
          element: <MarketingHomePage />
        }
      ]),
  {
    path: "/precios",
    element: (
      <MarketingRedirect>
      <PricingPageView />
      </MarketingRedirect>
    )
  },
  {
    path: "/funciones",
    element: (
      <MarketingRedirect>
        <FunctionsPage />
      </MarketingRedirect>
    )
  },
  {
    path: "/pms-hotelero",
    element: (
      <MarketingRedirect>
        <PmsHoteleroPage />
      </MarketingRedirect>
    )
  },
  {
    path: "/software-para-hoteles",
    element: (
      <MarketingRedirect>
        <SoftwareParaHotelesPage />
      </MarketingRedirect>
    )
  },
  {
    path: "/faq",
    element: (
      <MarketingRedirect>
        <FaqPage />
      </MarketingRedirect>
    )
  },
  {
    path: "/login",
    element: (
      <AppHostOnly>
        <LoginPage />
      </AppHostOnly>
    )
  },
  {
    path: "/register-owner",
    element: (
      <AppHostOnly>
        <RegisterOwnerPage />
      </AppHostOnly>
    )
  },
  {
    path: "/forgot-password",
    element: (
      <AppHostOnly>
        <ForgotPasswordPage />
      </AppHostOnly>
    )
  },
  {
    path: "/reset-password",
    element: (
      <AppHostOnly>
        <ResetPasswordPage />
      </AppHostOnly>
    )
  },
  {
    path: "/invitations/accept",
    element: (
      <AppHostOnly>
        <AcceptInvitationPage />
      </AppHostOnly>
    )
  },
  {
    path: "/accept-invitation",
    element: (
      <AppHostOnly>
        <AcceptInvitationPage />
      </AppHostOnly>
    )
  },
  {
    path: "/verify-email",
    element: (
      <AppHostOnly>
        <VerifyEmailPage />
      </AppHostOnly>
    )
  }
];

export const router = createBrowserRouter([
  ...appRoutes,
  ...(!APP_HOST
    ? [
        {
          path: "/dashboard",
          element: (
            <AppHostOnly>
              <Navigate to="/dashboard" replace />
            </AppHostOnly>
          )
        },
        {
          path: "/huespedes",
          element: (
            <AppHostOnly>
              <Navigate to="/huespedes" replace />
            </AppHostOnly>
          )
        },
        {
          path: "/reservas",
          element: (
            <AppHostOnly>
              <Navigate to="/reservas" replace />
            </AppHostOnly>
          )
        },
        {
          path: "/habitaciones",
          element: (
            <AppHostOnly>
              <Navigate to="/habitaciones" replace />
            </AppHostOnly>
          )
        },
        {
          path: "/caja",
          element: (
            <AppHostOnly>
              <Navigate to="/caja" replace />
            </AppHostOnly>
          )
        },
        {
          path: "/reportes",
          element: (
            <AppHostOnly>
              <Navigate to="/reportes" replace />
            </AppHostOnly>
          )
        },
        {
          path: "/operacion/tarifas",
          element: (
            <AppHostOnly>
              <Navigate to="/operacion/tarifas" replace />
            </AppHostOnly>
          )
        },
        {
          path: "/operacion/planilla",
          element: (
            <AppHostOnly>
              <Navigate to="/operacion/planilla" replace />
            </AppHostOnly>
          )
        },
        {
          path: "/operacion/lista-espera",
          element: (
            <AppHostOnly>
              <Navigate to="/operacion/lista-espera" replace />
            </AppHostOnly>
          )
        },
        {
          path: "/operacion/lavanderia",
          element: (
            <AppHostOnly>
              <Navigate to="/operacion/lavanderia" replace />
            </AppHostOnly>
          )
        },
        {
          path: "/operacion/stock",
          element: (
            <AppHostOnly>
              <Navigate to="/operacion/stock" replace />
            </AppHostOnly>
          )
        },
        {
          path: "/onboarding/*",
          element: (
            <AppHostOnly>
              <Navigate to="/onboarding" replace />
            </AppHostOnly>
          )
        },
        {
          path: "/settings/*",
          element: (
            <AppHostOnly>
              <Navigate to="/settings/users" replace />
            </AppHostOnly>
          )
        },
        {
          path: "/adminpmsmaster/*",
          element: (
            <AppHostOnly>
              <Navigate to="/adminpmsmaster" replace />
            </AppHostOnly>
          )
        },
        {
          path: "/accept-invitation",
          element: (
            <AppHostOnly>
              <Navigate to="/accept-invitation" replace />
            </AppHostOnly>
          )
        }
      ]
    : []),
  ...publicRoutes,
  { path: "*", element: APP_HOST ? <Navigate to="/dashboard" replace /> : <Navigate to="/" replace /> }
]);
