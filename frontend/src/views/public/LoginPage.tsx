import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import { getOnboardingStatus } from "../../api/onboarding";
import { safeHotelId, useSession } from "../../state/session";

export function LoginPage() {
  const navigate = useNavigate();
  const { login } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [hotelId, setHotelId] = useState("1");
  const [role, setRole] = useState<"owner" | "receptionist">("owner");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    const nextSession = { userId: email || "guest", email, hotelId: safeHotelId(hotelId), role };
    login(nextSession);

    try {
      const status = await getOnboardingStatus(nextSession);
      navigate(status.completed ? "/dashboard" : "/onboarding", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      navigate("/onboarding", { replace: true });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-slate-900">IngresÃ¡ a tu cuenta</h1>
          <p className="text-sm text-slate-600">
            UsÃ¡ tu email corporativo. Enviamos siempre los headers X-User-Id y X-Hotel-Id.
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
            <label className="text-sm font-medium text-slate-700">ContraseÃ±a</label>
            <input
              type="password"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              placeholder="â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Hotel ID (header X-Hotel-Id)</label>
            <input
              type="number"
              min={1}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              value={hotelId}
              onChange={(e) => setHotelId(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Rol</label>
            <select
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              value={role}
              onChange={(e) => setRole(e.target.value as "owner" | "receptionist")}
            >
              <option value="owner">Owner</option>
              <option value="receptionist">Recepcionista</option>
            </select>
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
            OlvidÃ© mi contraseÃ±a
          </Link>
          <Link to="/register-owner" className="text-brand-700 hover:underline">
            Crear cuenta de dueÃ±o
          </Link>
        </div>
      </div>
    </div>
  );
}
