import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppShell } from "./ui/AppShell";
import { LoginPage } from "./views/public/LoginPage";
import { RegisterOwnerPage } from "./views/public/RegisterOwnerPage";
import { ForgotPasswordPage } from "./views/public/ForgotPasswordPage";
import { ResetPasswordPage } from "./views/public/ResetPasswordPage";
import { VerifyEmailPage } from "./views/public/VerifyEmailPage";
import { AcceptInvitationPage } from "./views/public/AcceptInvitationPage";
import { OnboardingWizard } from "./views/onboarding/OnboardingWizard";
import { DashboardPage } from "./views/protected/DashboardPage";
import { ReservationsPage } from "./views/protected/ReservationsPage";
import { RoomsPage } from "./views/protected/RoomsPage";
import PricingPage from "./views/public/PricingPage";
import { SettingsUsersPage } from "./views/protected/SettingsUsersPage";
import { SettingsHotelPage } from "./views/protected/SettingsHotelPage";
import { SettingsSecurityPage } from "./views/protected/SettingsSecurityPage";
import { SettingsConnectionsPage } from "./views/protected/SettingsConnectionsPage";
import { SettingsTestsPage } from "./views/protected/SettingsTestsPage";
import SettingsSubscriptionPage from "./views/protected/SettingsSubscriptionPage";
import { useOnboardingStatus } from "./hooks/useOnboardingStatus";
import { useSession } from "./state/session";

function OnboardingGate() {
  const { session } = useSession();
  const { data, isFetching } = useOnboardingStatus({ enabled: Boolean(session.accessToken) });
  if (isFetching) return null;
  if (data?.completed) return <Navigate to="/dashboard" replace />;
  return <OnboardingWizard />;
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", element: <DashboardPage /> },
      { path: "reservas", element: <ReservationsPage /> },
      { path: "habitaciones", element: <RoomsPage /> },
      { path: "onboarding/*", element: <OnboardingGate /> },
      { path: "settings", element: <Navigate to="/settings/users" replace /> },
      { path: "settings/users", element: <SettingsUsersPage /> },
      { path: "settings/subscription", element: <SettingsSubscriptionPage /> },
      { path: "settings/connections", element: <SettingsConnectionsPage /> },
      { path: "settings/tests", element: <SettingsTestsPage /> },
      { path: "settings/hotel", element: <SettingsHotelPage /> },
      { path: "settings/security", element: <SettingsSecurityPage /> }
    ]
  },
  {
    path: "/login",
    element: <LoginPage />
  },
  { path: "/register-owner", element: <RegisterOwnerPage /> },
  { path: "/forgot-password", element: <ForgotPasswordPage /> },
  { path: "/reset-password", element: <ResetPasswordPage /> },
  { path: "/invitations/accept", element: <AcceptInvitationPage /> },
  { path: "/verify-email", element: <VerifyEmailPage /> },
  { path: "/pricing", element: <PricingPage /> },
  { path: "*", element: <Navigate to="/dashboard" replace /> }
]);
