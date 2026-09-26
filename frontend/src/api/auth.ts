import { apiFetch, type AuthResponsePayload, type SessionLike } from "./client";

export type AuthUser = {
  id: number;
  email: string;
  role: string;
  is_verified: boolean;
  is_active: boolean;
  password_login_enabled: boolean;
  google_login_enabled?: boolean;
  permissions?: string[];
};

export type AuthResponse = Omit<AuthResponsePayload, "user"> & {
  user: AuthUser;
  token_type: string;
  code?: string;
};

export type MfaChallengeResponse = {
  requires_mfa: true;
  mfa_token: string;
  expires_in: number;
};

export type AuthResult = AuthResponse | MfaChallengeResponse;

export const isMfaChallenge = (result: AuthResult): result is MfaChallengeResponse =>
  "requires_mfa" in result && result.requires_mfa === true;

export type RegistrationResponse = {
  accepted: true;
  message: string;
};

export type AuthProvidersResponse = {
  google: {
    enabled: boolean;
    client_id: string | null;
    self_signup_enabled: boolean;
    allowed_domains: string[];
  };
};

export const getAuthProviders = () =>
  apiFetch<AuthProvidersResponse>("/api/auth/providers", { method: "GET" });

export const register = (email: string, password: string, role: string = "owner") =>
  apiFetch<RegistrationResponse>("/api/auth/register", {
    method: "POST",
    data: { email, password, role }
  });

export const login = (email: string, password: string) =>
  apiFetch<AuthResult>("/api/auth/login", {
    method: "POST",
    data: { email, password }
  });

export const loginWithGoogle = (idToken: string) =>
  apiFetch<AuthResult>("/api/auth/google", {
    method: "POST",
    data: { id_token: idToken }
  });

export const completeMfaLogin = (mfaToken: string, code: string) =>
  apiFetch<AuthResponse>("/api/auth/login/mfa", {
    method: "POST",
    data: { mfa_token: mfaToken, code }
  });

export const setPasswordWithGoogle = (idToken: string, newPassword: string) =>
  apiFetch<{ password_login_enabled: true }>("/api/auth/password/set", {
    method: "POST",
    data: { id_token: idToken, new_password: newPassword }
  });

export const linkGoogle = (idToken: string, password: string) =>
  apiFetch<{ linked: true }>("/api/auth/google/link", {
    method: "POST",
    data: { id_token: idToken, password }
  });

export const loginWithApple = (
  idToken: string,
  nonce?: string,
  user?: { name?: { firstName?: string; lastName?: string } }
) =>
  apiFetch<AuthResult>("/api/auth/apple", {
    method: "POST",
    data: { id_token: idToken, nonce, user }
  });

export const requestVerification = (email: string) =>
  apiFetch<{ sent: boolean; code?: string }>("/api/auth/request-verify", {
    method: "POST",
    data: { email }
  });

export const verifyEmail = (email: string, code: string) =>
  apiFetch<AuthResponse>("/api/auth/verify-email", {
    method: "POST",
    data: { email, code }
  });

export const requestPasswordReset = (email: string) =>
  apiFetch<{ sent: boolean; code?: string }>("/api/auth/request-reset", {
    method: "POST",
    data: { email }
  });

export const resetPassword = (email: string, code: string, newPassword: string) =>
  apiFetch<AuthResult>("/api/auth/reset-password", {
    method: "POST",
    data: { email, code, new_password: newPassword }
  });

// Invitation bearer tokens stay in JSON bodies so HTTP access logs only see static paths.
export const getInvitationInfo = (token: string) =>
  apiFetch<{ email: string; hotel_name?: string; inviter_email?: string }>("/api/invitations/preview", {
    method: "POST",
    data: { token }
  });

export const acceptInvitation = (
  token: string,
  email: string,
  credentials?: { password?: string; currentPassword?: string },
  session?: SessionLike
) =>
  apiFetch<AuthResult>("/api/invitations/accept", {
    method: "POST",
    data: {
      token,
      email,
      ...(credentials?.password ? { password: credentials.password } : {}),
      ...(credentials?.currentPassword ? { current_password: credentials.currentPassword } : {})
    },
    session
  });

export const completeMfaInvitationAcceptance = (token: string, mfaToken: string, code: string) =>
  apiFetch<AuthResponse>("/api/invitations/accept/mfa", {
    method: "POST",
    data: { token, mfa_token: mfaToken, code }
  });

export const acceptInvitationWithGoogle = (token: string, idToken: string) =>
  apiFetch<AuthResult>("/api/invitations/accept/google", {
    method: "POST",
    data: { token, id_token: idToken }
  });

export const currentUser = (session?: SessionLike) =>
  apiFetch<AuthUser>("/api/auth/me", {
    method: "GET",
    session
  });
