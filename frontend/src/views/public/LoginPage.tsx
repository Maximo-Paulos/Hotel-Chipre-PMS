import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Seo } from "../../components/Seo";
import { GoogleSignInButton } from "../../components/GoogleSignInButton";
import { PasswordInput } from "../../components/PasswordInput";
import { login as loginApi, loginWithGoogle, type AuthResponse } from "../../api/auth";
import { getOnboardingStatus } from "../../api/onboarding";
import { defaultPathForRole, normalizeRole, useSession, type SessionState } from "../../state/session";

export function LoginPage() {
  const navigate = useNavigate();
  const { login } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [slowLogin, setSlowLogin] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading) {
      setSlowLogin(false);
      return;
    }

    const timeout = window.setTimeout(() => setSlowLogin(true), 5_000);
    return () => window.clearTimeout(timeout);
  }, [loading]);

  const completeAuth = async (res: AuthResponse) => {
    if (!res.hotel_id) {
      throw new ApiError(500, "La respuesta de autenticación no devolvió un hotel válido.");
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
      isVerified: res.user.is_verified
    };
    login(nextSession);

    if (res.requires_verification || !res.user.is_verified) {
      navigate("/verify-email", { replace: true });
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

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await loginApi(email, password);
      await completeAuth(res);
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("No se pudo iniciar sesion");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleCredential = async (idToken: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await loginWithGoogle(idToken);
      await completeAuth(res);
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("No se pudo iniciar sesion con Google");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <Seo title="Ingresar | Hotel Chipre PMS" description="Accede al sistema de gestión hotelera Hotel Chipre PMS." noindex />
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <div className="mb-6 flex flex-col items-start gap-4">
          <img
            src="/brand/logo-full.png"
            alt="Hotel Chipre PMS"
            className="h-20 w-auto max-w-full object-contain"
          />
          <h1 className="text-2xl font-semibold text-slate-900">Ingresa a tu cuenta</h1>
          <p className="text-sm text-slate-600">
            Ingresá con tus credenciales. El sistema sólo envía contexto de hotel cuando la sesión es válida.
          </p>
        </div>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="text-sm font-medium text-slate-700">Email</label>
            <input
              required
              type="email"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              placeholder="owner@hotel.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Contraseña</label>
            <PasswordInput
              value={password}
              onChange={setPassword}
              placeholder="••••••••"
              required
              autoComplete="current-password"
            />
          </div>
          {error && <p className="rounded-md bg-rose-50 p-2 text-sm text-rose-700">{error}</p>}
          {loading && slowLogin && (
            <p className="rounded-md bg-amber-50 p-2 text-sm text-amber-800" data-testid="login-slow-hint" role="status">
              La conexión está demorando más de lo habitual. Estamos intentando ingresar sin perder tus datos.
            </p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-70"
            data-testid="login-submit"
          >
            {loading ? "Conectando..." : "Entrar"}
          </button>
        </form>
        <div className="mt-4">
          <div className="relative flex items-center py-2">
            <div className="flex-grow border-t border-slate-200" />
            <span className="mx-3 text-xs uppercase text-slate-400">o</span>
            <div className="flex-grow border-t border-slate-200" />
          </div>
          <GoogleSignInButton onCredential={handleGoogleCredential} />
        </div>
        <div className="mt-4 flex items-center justify-between text-sm">
          <Link to="/forgot-password" className="text-brand-700 hover:underline">
            Olvidé mi contraseña
          </Link>
          <Link to="/register-owner" className="text-brand-700 hover:underline">
            Crear cuenta de dueño
          </Link>
        </div>
      </div>
    </div>
  );
}
