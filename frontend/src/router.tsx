import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppShell } from "./ui/AppShell";
import { LoginPage } from "./views/public/LoginPage";
import { RegisterOwnerPage } from "./views/public/RegisterOwnerPage";
import { ForgotPasswordPage } from "./views/public/ForgotPasswordPage";
import { ResetPasswordPage } from "./views/public/ResetPasswordPage";
import { VerifyEmailPage } from "./views/public/VerifyEmailPage";
import { OnboardingWizard } from "./views/onboarding/OnboardingWizard";
import { DashboardPage } from "./views/protected/DashboardPage";
import { SettingsUsersPage } from "./views/protected/SettingsUsersPage";
import { SettingsHotelPage } from "./views/protected/SettingsHotelPage";
import { SettingsSecurityPage } from "./views/protected/SettingsSecurityPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", element: <DashboardPage /> },
      { path: "onboarding/*", element: <OnboardingWizard /> },
      { path: "settings/users", element: <SettingsUsersPage /> },
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
  { path: "/verify-email", element: <VerifyEmailPage /> }
]);
