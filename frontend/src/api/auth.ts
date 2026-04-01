import { apiFetch, type SessionLike } from "./client";

export type AuthUser = {
  id: number;
  email: string;
  role: string;
  is_verified: boolean;
  is_active: boolean;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: AuthUser;
  requires_verification?: boolean;
  code?: string;
};

export const register = (email: string, password: string, role: string = "owner") =>
  apiFetch<AuthResponse>("/api/auth/register", {
    method: "POST",
    data: { email, password, role }
  });

export const login = (email: string, password: string) =>
  apiFetch<AuthResponse>("/api/auth/login", {
    method: "POST",
    data: { email, password }
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
  apiFetch<AuthResponse>("/api/auth/reset-password", {
    method: "POST",
    data: { email, code, new_password: newPassword }
  });

export const currentUser = (session?: SessionLike) =>
  apiFetch<AuthUser>("/api/auth/me", {
    method: "GET",
    session
  });
