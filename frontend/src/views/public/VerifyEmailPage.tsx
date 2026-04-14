import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import { requestVerification, verifyEmail } from "../../api/auth";
import { getOnboardingStatus } from "../../api/onboarding";
import { normalizeRole, useSession } from "../../state/session";

export function VerifyEmailPage() {
  const navigate = useNavigate();
  const { session, login } = useSession();
  const [message, setMessage] = useState<string | null>(null);
  const [email, setEmail] = useState(session.email || session.userId || "");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sentCode, setSentCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    setError(null);
    setMessage(null);
    setLoading(true);
    try {
      const resp = await requestVerification(email);
      if (resp.code) {
        setSentCode(resp.code);
        setMessage(`Codigo demo: ${resp.code}`);
      } else {
        setMessage("Enviamos un codigo a tu correo.");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo enviar el correo");
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    setError(null);
    setMessage(null);
    setLoading(true);
    try {
      const res = await verifyEmail(email, code);
      if (!res.hotel_id) {
        throw new ApiError(500, "La respuesta de verificación no devolvió un hotel válido.");
      }
      login({
        userId: res.user.email,
        email: res.user.email,
        hotelId: res.hotel_id,
        hotelIds: res.hotel_ids?.length ? res.hotel_ids : [res.hotel_id],
        role: normalizeRole(res.user.role),
        baseRole: normalizeRole(res.user.role),
        accessToken: res.access_token,
        isVerified: true
      });
      setMessage("Codigo correcto. Email verificado.");
      const status = await getOnboardingStatus({
        hotelId: res.hotel_id,
        userId: res.user.email,
        accessToken: res.access_token
      });
      navigate(status.completed ? "/dashboard" : "/onboarding", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Codigo invalido o expirado");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <h1 className="text-2xl font-semibold text-slate-900">Verifica tu email</h1>
        <p className="mb-4 text-sm text-slate-600">
          Necesitamos validar tu correo para habilitar acciones y completar el onboarding.
        </p>
        <div className="space-y-3 text-sm text-slate-700">
          <label className="text-sm font-medium text-slate-700">
            Email
            <input
              value={email}
              placeholder="tu@correo.com"
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:ring-brand-500"
            />
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleSend}
              disabled={loading}
              className="rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-60"
            >
              {loading ? "Enviando..." : "Enviar codigo"}
            </button>
            <button
              type="button"
              onClick={() => navigate("/onboarding", { replace: true })}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300"
            >
              Ir al onboarding
            </button>
          </div>
          <label className="text-sm font-medium text-slate-700">
            Codigo
            <input
              value={code}
              placeholder="Ej: 123456"
              onChange={(e) => setCode(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:ring-brand-500"
            />
          </label>
          <button
            type="button"
            onClick={handleVerify}
            disabled={loading}
            className="w-full rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-800 hover:border-emerald-300 disabled:opacity-60"
          >
            Verificar codigo
          </button>
        </div>
        {message && <p className="mt-3 rounded-md bg-emerald-50 p-3 text-emerald-700">{message}</p>}
        {sentCode && <p className="mt-1 text-xs text-amber-700">Codigo demo: {sentCode}</p>}
        {error && <p className="mt-3 rounded-md bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
        <div className="mt-6 flex items-center justify-between text-sm">
          <Link to="/login" className="text-brand-700 hover:underline">
            Volver al login
          </Link>
        </div>
      </div>
    </div>
  );
}
