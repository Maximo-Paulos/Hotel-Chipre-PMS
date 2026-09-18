import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Seo } from "../../components/Seo";
import { PasswordInput } from "../../components/PasswordInput";
import {
  completeMfaLogin,
  isMfaChallenge,
  requestPasswordReset,
  resetPassword,
  type AuthResponse,
  type MfaChallengeResponse
} from "../../api/auth";
import { normalizeRole, useSession } from "../../state/session";
import { BrandMark } from "../../components/brand/BrandMark";

type Step = 1 | 2 | 3 | 4;
const AUTH_EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const { login } = useSession();

  const [step, setStep] = useState<Step>(1);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [info, setInfo] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [mfaChallenge, setMfaChallenge] = useState<MfaChallengeResponse | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaError, setMfaError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const sendCode = async () => {
    setError(null);
    const normalizedEmail = email.trim();
    if (!AUTH_EMAIL_PATTERN.test(normalizedEmail)) {
      setError("Ingresá un email válido.");
      return;
    }
    setEmail(normalizedEmail);
    setLoading(true);
    try {
      await requestPasswordReset(normalizedEmail);
      setInfo("Enviamos el código si el correo existe.");
      setStep(2);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo enviar el código");
    } finally {
      setLoading(false);
    }
  };

  const validateCode = () => {
    setError(null);
    const normalizedCode = code.trim();
    if (!normalizedCode) {
      setError("Ingresá el código recibido por correo.");
      return;
    }
    setCode(normalizedCode);
    setStep(3);
  };

  const finishSignIn = (res: AuthResponse) => {
    if (!res.hotel_id) {
      throw new ApiError(500, "La respuesta de autenticación no devolvió un hotel válido.");
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
      isVerified: res.user.is_verified
    });
    setSaved(true);
    setTimeout(() => navigate("/login"), 1000);
  };

  const handleSave = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (!password || password !== confirm) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setLoading(true);
    try {
      const res = await resetPassword(email.trim(), code.trim(), password);
      if (isMfaChallenge(res)) {
        setMfaChallenge(res);
        setMfaCode("");
        setMfaError(null);
        setInfo("La contraseña quedó actualizada. Ahora verificá tu identidad para iniciar sesión.");
        setStep(4);
      } else {
        finishSignIn(res);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Código inválido o expirado");
    } finally {
      setLoading(false);
    }
  };

  const handleMfaSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!mfaChallenge) return;
    setMfaError(null);
    setLoading(true);
    try {
      const res = await completeMfaLogin(mfaChallenge.mfa_token, mfaCode.trim());
      setMfaChallenge(null);
      finishSignIn(res);
    } catch (err) {
      setMfaError(err instanceof ApiError ? err.message : "No se pudo verificar el código.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <Seo title="Restablecer contraseña | Hotels-PMS" description="Restablece tu contraseña de acceso." noindex />
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <div className="mb-6 space-y-3">
          <BrandMark />
          <h1 className="text-2xl font-semibold text-slate-900">Restablecer contraseña</h1>
          <p className="text-sm text-slate-600">Seguí los pasos para recuperar tu acceso.</p>
        </div>

        {step === 1 && (
          <div className="space-y-4">
            <label htmlFor="reset-email" className="text-sm font-medium text-slate-700">
              Email
              <input
                id="reset-email"
                type="email"
                autoComplete="email"
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
                placeholder="tu@hotel.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            <button
              onClick={sendCode}
              className="w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-60"
              disabled={loading}
            >
              {loading ? "Enviando..." : "Enviar código"}
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <label htmlFor="reset-code" className="text-sm font-medium text-slate-700">
              Código recibido
              <input
                id="reset-code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={64}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
                placeholder="Ej: 123456"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
              />
            </label>
            <div className="flex gap-2">
              <button
                onClick={validateCode}
                className="flex-1 rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-60"
                disabled={loading}
              >
                Continuar
              </button>
              <button
                onClick={sendCode}
                className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300 disabled:opacity-60"
                disabled={loading}
              >
                Reenviar código
              </button>
            </div>
          </div>
        )}

        {step === 3 && (
          <form className="space-y-4" onSubmit={handleSave}>
            <label className="text-sm font-medium text-slate-700">
              Nueva contraseña
              <PasswordInput
                value={password}
                onChange={setPassword}
                placeholder="Mínimo 12 caracteres"
                required
                autoComplete="new-password"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Confirmar contraseña
              <PasswordInput
                value={confirm}
                onChange={setConfirm}
                placeholder="Repite la nueva contraseña"
                required
                autoComplete="new-password"
              />
            </label>
            <button
              className="w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-60"
              disabled={loading}
            >
              {loading ? "Guardando..." : "Guardar nueva contraseña"}
            </button>
          </form>
        )}

        {step === 4 && mfaChallenge && (
          <form className="space-y-4" onSubmit={handleMfaSubmit}>
            <p className="rounded-lg border border-brand-100 bg-brand-50 p-3 text-sm text-brand-900" role="status">
              Esta cuenta tiene activada la verificación en dos pasos. Abrí la app autenticadora que vinculaste e ingresá su código temporal de 6 dígitos. También podés usar un código de recuperación guardado. No te llegará por email.
            </p>
            <label htmlFor="reset-mfa-code" className="block text-sm font-medium text-slate-700">
              Código de la app autenticadora o de recuperación
              <input
                id="reset-mfa-code"
                autoComplete="one-time-code"
                inputMode="numeric"
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                value={mfaCode}
                onChange={(event) => setMfaCode(event.target.value)}
                required
                autoFocus
              />
            </label>
            {mfaError && <p className="rounded-md bg-rose-50 p-2 text-sm text-rose-700" role="alert">{mfaError}</p>}
            <button
              type="submit"
              disabled={loading || !mfaCode.trim()}
              className="w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-60"
            >
              {loading ? "Verificando..." : "Verificar y continuar"}
            </button>
          </form>
        )}

        {info && <p role="status" className="mt-3 rounded-md bg-amber-50 p-3 text-sm text-amber-800">{info}</p>}
        {saved && (
          <p className="mt-3 rounded-md bg-emerald-50 p-3 text-sm text-emerald-700">
            Contraseña actualizada. Redirigiendo al login.
          </p>
        )}
        {error && <p role="alert" className="mt-3 rounded-md bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
        <div className="mt-4 text-sm">
          <Link to="/login" className="text-brand-700 hover:underline">
            Volver al login
          </Link>
        </div>
      </div>
    </div>
  );
}
