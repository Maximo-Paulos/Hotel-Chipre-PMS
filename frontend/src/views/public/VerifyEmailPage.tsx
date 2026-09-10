import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Seo } from "../../components/Seo";
import { requestVerification, verifyEmail } from "../../api/auth";
import { getOnboardingStatus, setOwner } from "../../api/onboarding";
import { clearPendingOwner, getPendingOwner } from "../../state/pendingOwner";
import { normalizeRole, useSession } from "../../state/session";

const AUTH_EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function VerifyEmailPage() {
  const navigate = useNavigate();
  const { session, login } = useSession();
  const pendingOwner = getPendingOwner();
  const [message, setMessage] = useState<string | null>(null);
  const [email, setEmail] = useState(session.email || session.userId || pendingOwner?.email || "");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    setError(null);
    setMessage(null);
    const normalizedEmail = email.trim();
    if (!AUTH_EMAIL_PATTERN.test(normalizedEmail)) {
      setError("Ingresá un email válido.");
      return;
    }
    setEmail(normalizedEmail);
    setLoading(true);
    try {
      await requestVerification(normalizedEmail);
      setMessage("Enviamos un código a tu correo.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo enviar el correo");
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    setError(null);
    setMessage(null);
    const normalizedEmail = email.trim();
    const normalizedCode = code.trim();
    if (!AUTH_EMAIL_PATTERN.test(normalizedEmail)) {
      setError("Ingresá un email válido.");
      return;
    }
    if (!normalizedCode) {
      setError("Ingresá el código de verificación.");
      return;
    }
    setEmail(normalizedEmail);
    setCode(normalizedCode);
    setLoading(true);
    try {
      const res = await verifyEmail(normalizedEmail, normalizedCode);
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
        permissions: res.permissions ?? res.user.permissions ?? null,
        accessToken: res.access_token,
        csrfToken: res.csrf_token,
        isVerified: true
      });
      const currentPendingOwner = getPendingOwner();
      if (currentPendingOwner && currentPendingOwner.email.trim().toLowerCase() === res.user.email.trim().toLowerCase()) {
        await setOwner(currentPendingOwner, {
          userId: res.user.email,
          hotelId: res.hotel_id,
          accessToken: res.access_token,
          csrfToken: res.csrf_token
        });
        clearPendingOwner();
      }
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
      <Seo title="Verificar email | Hotel Chipre PMS" description="Confirma tu correo para continuar con el onboarding." noindex />
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <div className="mb-6 space-y-3">
          <img
            src="/brand/logo-full.png"
            alt="Hotel Chipre PMS"
            className="h-20 w-auto max-w-full object-contain"
          />
          <h1 className="text-2xl font-semibold text-slate-900">Verificá tu email</h1>
          <p className="text-sm text-slate-600">
            Necesitamos validar tu correo para habilitar acciones y completar el onboarding.
          </p>
        </div>
        <div className="space-y-3 text-sm text-slate-700">
          <label htmlFor="verify-email" className="text-sm font-medium text-slate-700">
            Email
            <input
              id="verify-email"
              type="email"
              autoComplete="email"
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
              {loading ? "Enviando..." : "Enviar código"}
            </button>
            <button
              type="button"
              onClick={() => navigate("/onboarding", { replace: true })}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300"
            >
              Ir al onboarding
            </button>
          </div>
          <label htmlFor="verify-code" className="text-sm font-medium text-slate-700">
            Código
            <input
              id="verify-code"
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              placeholder="Ej.: 123456"
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
            Verificar código
          </button>
        </div>
        {message && <p role="status" className="mt-3 rounded-md bg-emerald-50 p-3 text-emerald-700">{message}</p>}
        {error && <p role="alert" className="mt-3 rounded-md bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
        <div className="mt-6 flex items-center justify-between text-sm">
          <Link to="/login" className="text-brand-700 hover:underline">
            Volver al login
          </Link>
        </div>
      </div>
    </div>
  );
}
