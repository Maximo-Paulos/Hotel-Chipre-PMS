import { useEffect, type ReactNode } from "react";
import { createBrowserRouter, Navigate, useLocation } from "react-router-dom";

import { isAppHostname, resolveAppLocation, resolveSiteLocation } from "./config/publicUrls";
import { useOnboardingStatus } from "./hooks/useOnboardingStatus";
import { useSession } from "./state/session";
import { AppShell } from "./ui/AppShell";
import { AcceptInvitationPage } from "./views/public/AcceptInvitationPage";
import { FaqPage } from "./views/public/FaqPage";
import { ForgotPasswordPage } from "./views/public/ForgotPasswordPage";
import { FunctionsPage } from "./views/public/FunctionsPage";
import { LoginPage } from "./views/public/LoginPage";
import { MarketingHomePage } from "./views/public/MarketingHomePage";
import { PmsHoteleroPage } from "./views/public/PmsHoteleroPage";
import { PricingPage as PricingPageView } from "./views/public/PricingPage";
import { RegisterOwnerPage } from "./views/public/RegisterOwnerPage";
import { ResetPasswordPage } from "./views/public/ResetPasswordPage";
import { SoftwareParaHotelesPage } from "./views/public/SoftwareParaHotelesPage";
import { VerifyEmailPage } from "./views/public/VerifyEmailPage";
import { DashboardPage } from "./views/protected/DashboardPage";
import { GuestsPage } from "./views/protected/GuestsPage";
import { ReservationsPage } from "./views/protected/ReservationsPage";
import { RoomsPage } from "./views/protected/RoomsPage";
import { SettingsAssistantPage } from "./views/protected/SettingsAssistantPage";
import SettingsSubscriptionPage from "./views/protected/SettingsSubscriptionPage";
import { SettingsConnectionsPage } from "./views/protected/SettingsConnectionsPage";
import { SettingsHotelPage } from "./views/protected/SettingsHotelPage";
import { SettingsSecurityPage } from "./views/protected/SettingsSecurityPage";
import { SettingsTestsPage } from "./views/protected/SettingsTestsPage";
import { SettingsUsersPage } from "./views/protected/SettingsUsersPage";
import { OnboardingWizard } from "./views/onboarding/OnboardingWizard";
import {
  MasterAdminProtectedShell,
  MasterAdminRoot
} from "./master_admin/layout";
import { MasterAdminAuditPage } from "./master_admin/pages/AuditPage";
import { MasterAdminBillingPage } from "./master_admin/pages/BillingPage";
import { MasterAdminDashboardPage } from "./master_admin/pages/DashboardPage";
import { MasterAdminEmailPage } from "./master_admin/pages/EmailPage";
import { MasterAdminLoginPage } from "./master_admin/pages/LoginPage";
import { MasterAdminStripePage } from "./master_admin/pages/StripePage";

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
          { path: "dashboard", element: <DashboardPage /> },
          { path: "huespedes", element: <GuestsPage /> },
          { path: "reservas", element: <ReservationsPage /> },
          { path: "habitaciones", element: <RoomsPage /> },
          { path: "onboarding/*", element: <OnboardingGate /> },
          { path: "settings", element: <Navigate to="/settings/users" replace /> },
          { path: "settings/users", element: <SettingsUsersPage /> },
          { path: "settings/assistant", element: <SettingsAssistantPage /> },
          { path: "settings/subscription", element: <SettingsSubscriptionPage /> },
          { path: "settings/connections", element: <SettingsConnectionsPage /> },
          { path: "settings/tests", element: <SettingsTestsPage /> },
          { path: "settings/hotel", element: <SettingsHotelPage /> },
          { path: "settings/security", element: <SettingsSecurityPage /> }
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
