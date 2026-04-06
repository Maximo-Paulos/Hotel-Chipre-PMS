import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import { login as loginApi } from "../../api/auth";
import { getOnboardingStatus } from "../../api/onboarding";
import { useSession, type SessionState } from "../../state/session";

export function LoginPage() {
  const navigate = useNavigate();
  const { login } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await loginApi(email, password);
      const nextSession: Partial<SessionState> = {
        userId: res.user.email,
        email: res.user.email,
        hotelId: res.hotel_id ?? 1,
        hotelIds: res.hotel_ids ?? [res.hotel_id ?? 1],
        role: (res.user.role as SessionState["role"]) || "owner",
        baseRole: (res.user.role as SessionState["role"]) || "owner",
        accessToken: res.access_token,
        isVerified: res.user.is_verified
      };
      login(nextSession);

      if (res.requires_verification || !res.user.is_verified) {
        navigate("/verify-email", { replace: true });
        return;
      }

      const status = await getOnboardingStatus(nextSession);
      navigate(status.completed ? "/dashboard" : "/onboarding", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("No se pudo iniciar sesion");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-slate-900">Ingresa a tu cuenta</h1>
          <p className="text-sm text-slate-600">
            Usa tu email corporativo. Enviamos headers X-User-Id, X-Hotel-Id y Authorization.
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
            <input
              type="password"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && <p className="rounded-md bg-rose-50 p-2 text-sm text-rose-700">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-70"
            data-testid="login-submit"
          >
            {loading ? "Conectando..." : "Entrar"}
          </button>
        </form>
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
