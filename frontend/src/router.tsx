import type { ReactNode } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";

import { isAppHostname, PUBLIC_SITE_URL } from "./config/publicUrls";
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

function MarketingRedirect({ children }: { children: ReactNode }) {
  if (APP_HOST && PUBLIC_SITE_URL) {
    return <Navigate to={`${PUBLIC_SITE_URL}${window.location.pathname}${window.location.search}${window.location.hash}`} replace />;
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
  { path: "/login", element: <LoginPage /> },
  { path: "/register-owner", element: <RegisterOwnerPage /> },
  { path: "/forgot-password", element: <ForgotPasswordPage /> },
  { path: "/reset-password", element: <ResetPasswordPage /> },
  { path: "/invitations/accept", element: <AcceptInvitationPage /> },
  { path: "/verify-email", element: <VerifyEmailPage /> }
];

export const router = createBrowserRouter([
  ...appRoutes,
  ...publicRoutes,
  { path: "*", element: APP_HOST ? <Navigate to="/dashboard" replace /> : <Navigate to="/" replace /> }
]);
