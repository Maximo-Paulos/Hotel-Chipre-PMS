import { apiFetch, type SessionLike } from "./client";

export type EmailSendResponse = { sent: boolean };
export type EmailVerifyResponse = { valid: boolean };
export type SmtpStatus = { configured: boolean; from: string; host: string };

export const sendVerificationEmail = (to: string, session?: SessionLike) =>
  apiFetch<EmailSendResponse>("/api/email/verify", {
    method: "POST",
    data: { to },
    session
  });

export const sendResetEmail = (to: string, session?: SessionLike) =>
  apiFetch<EmailSendResponse>("/api/email/reset", {
    method: "POST",
    data: { to },
    session
  });

export const verifyEmailCode = (email: string, code: string, session?: SessionLike) =>
  apiFetch<EmailVerifyResponse>("/api/email/verify-code", {
    method: "POST",
    data: { email, code },
    session
  });

export const getSmtpStatus = (session?: SessionLike) => apiFetch<SmtpStatus>("/api/config/smtp", { session });
