import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { ApiError } from "../../api/client";
import { Seo } from "../../components/Seo";
import { GoogleSignInButton } from "../../components/GoogleSignInButton";
import { AppleSignInButton } from "../../components/AppleSignInButton";
import { PasswordInput } from "../../components/PasswordInput";
import {
  completeMfaLogin,
  isMfaChallenge,
  login as loginApi,
  loginWithApple,
  loginWithGoogle,
  type AuthResponse,
  type AuthResult
} from "../../api/auth";
import { getOnboardingStatus } from "../../api/onboarding";
import { defaultPathForRole, normalizeRole, useSession, type SessionState } from "../../state/session";
import { BrandMark } from "../../components/brand/BrandMark";

const safeInvitationReturnPath = (candidate: string | null): string | null => {
  if (!candidate) return null;
  try {
    const url = new URL(candidate, window.location.origin);
    const token = url.searchParams.get("token");
    if (url.origin !== window.location.origin || url.pathname !== "/invitations/accept" || !token) return null;
    return `/invitations/accept#token=${encodeURIComponent(token)}`;
  } catch {
    return null;
  }
};

const safeInvitationHashReturnPath = (hash: string): string | null => {
  const token = new URLSearchParams(hash.replace(/^#/, "")).get("invitation");
  if (!token || token.length > 512) return null;
  return `/invitations/accept#token=${encodeURIComponent(token)}`;
};

export function LoginPage() {
  const { t } = useTranslation("auth");
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const invitationReturnPath = safeInvitationReturnPath(searchParams.get("returnTo"))
    || safeInvitationHashReturnPath(location.hash);
  const { login, session, isInitializing, restoredSession } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [slowLogin, setSlowLogin] = useState(false);
  const [showPasswordHelp, setShowPasswordHelp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mfaChallenge, setMfaChallenge] = useState<{ mfa_token: string; expires_in: number } | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaError, setMfaError] = useState<string | null>(null);
  const [mfaLoading, setMfaLoading] = useState(false);

  useEffect(() => {
    if (!loading) {
      setSlowLogin(false);
      return;
    }

    const timeout = window.setTimeout(() => setSlowLogin(true), 5_000);
    return () => window.clearTimeout(timeout);
  }, [loading]);

  useEffect(() => {
    if (isInitializing || !restoredSession || !session.accessToken) return;
    if (!session.isVerified) {
      navigate("/verify-email", { replace: true });
      return;
    }
    if (invitationReturnPath) {
      navigate(invitationReturnPath, { replace: true });
      return;
    }
    navigate(defaultPathForRole(session.baseRole ?? session.role), { replace: true });
  }, [invitationReturnPath, isInitializing, navigate, restoredSession, session.accessToken, session.baseRole, session.isVerified, session.role]);

  const completeAuth = async (res: AuthResponse) => {
    if (!res.hotel_id) {
      throw new ApiError(500, t("login.errors.invalidHotel"));
    }
    const authenticatedRole = normalizeRole(res.user.role);
    const nextSession: Partial<SessionState> = {
      userId: res.user.email,
      email: res.user.email,
      hotelId: res.hotel_id,
      hotelIds: res.hotel_ids?.length ? res.hotel_ids : [res.hotel_id],
      role: authenticatedRole,
      baseRole: authenticatedRole,
      permissions: res.permissions ?? res.user.permissions ?? null,
      accessToken: res.access_token,
      csrfToken: res.csrf_token,
      isVerified: res.user.is_verified
    };
    login(nextSession);

    if (res.requires_verification || !res.user.is_verified) {
      navigate("/verify-email", { replace: true });
      return;
    }

    if (invitationReturnPath) {
      navigate(invitationReturnPath, { replace: true });
      return;
    }

    if (authenticatedRole === "owner" || authenticatedRole === "co_owner") {
      const status = await getOnboardingStatus(nextSession);
      navigate(status.completed ? defaultPathForRole(authenticatedRole) : "/onboarding", { replace: true });
      return;
    }

    // Onboarding contains hotel configuration and is owner/co-owner-only.
    // Operational users must not fetch it merely to decide their landing page.
    navigate(defaultPathForRole(authenticatedRole), { replace: true });
  };

  const handleAuthResult = async (result: AuthResult) => {
    if (isMfaChallenge(result)) {
      setMfaChallenge({ mfa_token: result.mfa_token, expires_in: result.expires_in });
      setMfaCode("");
      setMfaError(null);
      setError(null);
      return;
    }
    setMfaChallenge(null);
    await completeAuth(result);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await loginApi(email, password);
      await handleAuthResult(res);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
        setShowPasswordHelp(err.status === 401);
      } else {
        setError(t("login.errors.signIn"));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleCredential = async (idToken: string) => {
    setLoading(true);
    setError(null);
    setShowPasswordHelp(false);
    try {
      const res = await loginWithGoogle(idToken);
      await handleAuthResult(res);
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError(t("login.errors.signInGoogle"));
    } finally {
      setLoading(false);
    }
  };

  const handleAppleCredential = async (
    idToken: string,
    nonce: string,
    user?: { name?: { firstName?: string; lastName?: string } }
  ) => {
    setLoading(true);
    setError(null);
    setShowPasswordHelp(false);
    try {
      const res = await loginWithApple(idToken, nonce, user);
      await handleAuthResult(res);
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError(t("login.errors.signInApple"));
    } finally {
      setLoading(false);
    }
  };

  const handleMfaSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!mfaChallenge) return;
    setMfaLoading(true);
    setMfaError(null);
    try {
      const res = await completeMfaLogin(mfaChallenge.mfa_token, mfaCode.trim());
      setMfaChallenge(null);
      await completeAuth(res);
    } catch (err) {
      setMfaError(err instanceof ApiError ? err.message : t("login.errors.mfa"));
    } finally {
      setMfaLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <Seo title={t("seo.loginTitle")} description={t("seo.loginDescription")} noindex />
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <div className="mb-6 flex flex-col items-start gap-4">
          <BrandMark />
          <h1 className="text-2xl font-semibold text-slate-900">{t("login.title")}</h1>
          <p className="text-sm text-slate-600">{t("login.description")}</p>
        </div>
        {mfaChallenge ? (
          <form className="space-y-4" onSubmit={handleMfaSubmit}>
            <div className="rounded-lg border border-brand-100 bg-brand-50 p-3 text-sm text-brand-900" role="status">
              {t("login.mfaDescription", { seconds: mfaChallenge.expires_in })}
            </div>
            <label htmlFor="login-mfa-code" className="block text-sm font-medium text-slate-700">
              {t("login.mfaCodeLabel")}
              <input
                id="login-mfa-code"
                autoComplete="one-time-code"
                inputMode="numeric"
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                value={mfaCode}
                onChange={(event) => setMfaCode(event.target.value)}
                required
                autoFocus
              />
            </label>
            {mfaError && <p role="alert" className="rounded-md bg-rose-50 p-2 text-sm text-rose-700">{mfaError}</p>}
            <button
              type="submit"
              disabled={mfaLoading || !mfaCode.trim()}
              className="w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-70"
            >
              {mfaLoading ? t("login.mfaVerifying") : t("login.mfaSubmit")}
            </button>
            <button
              type="button"
              className="w-full rounded-lg px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
              onClick={() => {
                setMfaChallenge(null);
                setMfaCode("");
                setMfaError(null);
              }}
            >
              {t("login.mfaCancel")}
            </button>
          </form>
        ) : (
        <div>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div>
            <label htmlFor="login-email" className="text-sm font-medium text-slate-700">{t("login.emailLabel")}</label>
            <input
              id="login-email"
              required
              type="email"
              autoComplete="email"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              placeholder={t("login.emailPlaceholder")}
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                setShowPasswordHelp(false);
              }}
            />
          </div>
          <div>
            <label htmlFor="login-password" className="text-sm font-medium text-slate-700">{t("login.passwordLabel")}</label>
            <PasswordInput
              id="login-password"
              value={password}
              onChange={(value) => {
                setPassword(value);
                setShowPasswordHelp(false);
              }}
              placeholder={t("login.passwordPlaceholder")}
              required
              autoComplete="current-password"
            />
          </div>
          {error && <p id="login-error" role="alert" className="rounded-md bg-rose-50 p-2 text-sm text-rose-700">{error}</p>}
          {showPasswordHelp && (
            <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-900" role="note">
              {t("login.passwordHelp")} {" "}
              <Link to="/reset-password" className="font-semibold underline">
                {t("login.resetHotelPassword")}
              </Link>
            </p>
          )}
          {loading && slowLogin && (
            <p className="rounded-md bg-amber-50 p-2 text-sm text-amber-800" data-testid="login-slow-hint" role="status">
              {t("login.slowHint")}
            </p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-70"
            data-testid="login-submit"
          >
            {loading ? t("login.connecting") : t("login.submit")}
          </button>
        </form>
        <div className="mt-4">
          <div className="relative flex items-center py-2">
            <div className="flex-grow border-t border-slate-200" />
            <span className="mx-3 text-xs uppercase text-slate-400">{t("login.socialSeparator")}</span>
            <div className="flex-grow border-t border-slate-200" />
          </div>
          <GoogleSignInButton onCredential={handleGoogleCredential} />
          <div className="mt-3">
            <AppleSignInButton disabled={loading} onCredential={handleAppleCredential} />
          </div>
        </div>
        </div>
        )}
        <div className="mt-4 flex items-center justify-between text-sm">
          <Link to="/forgot-password" className="text-brand-700 hover:underline">
            {t("login.forgotPassword")}
          </Link>
          <Link to="/register-owner" className="text-brand-700 hover:underline">
            {t("login.createOwnerAccount")}
          </Link>
        </div>
      </div>
    </div>
  );
}
