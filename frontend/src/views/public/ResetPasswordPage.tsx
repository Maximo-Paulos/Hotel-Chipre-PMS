import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import { requestPasswordReset, resetPassword } from "../../api/auth";
import { normalizeRole, useSession } from "../../state/session";

type Step = 1 | 2 | 3;

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
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const sendCode = async () => {
    setError(null);
    if (!email.trim()) {
      setError("Ingresá tu correo.");
      return;
    }
    setLoading(true);
    try {
      const resp = await requestPasswordReset(email.trim());
      setInfo(resp.code ? `Código demo: ${resp.code}` : "Enviamos el código si el correo existe.");
      setStep(2);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo enviar el código");
    } finally {
      setLoading(false);
    }
  };

  const validateCode = () => {
    setError(null);
    if (!code.trim()) {
      setError("Ingresá el código recibido por correo.");
      return;
    }
    setStep(3);
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
      if (!res.hotel_id) {
        throw new ApiError(500, "La respuesta de recuperación no devolvió un hotel válido.");
      }
      login({
        userId: res.user.email,
        email: res.user.email,
        hotelId: res.hotel_id,
        hotelIds: res.hotel_ids?.length ? res.hotel_ids : [res.hotel_id],
        role: normalizeRole(res.user.role),
        baseRole: normalizeRole(res.user.role),
        accessToken: res.access_token,
        isVerified: res.user.is_verified
      });
      setSaved(true);
      setTimeout(() => navigate("/login"), 1000);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Código inválido o expirado");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <h1 className="text-2xl font-semibold text-slate-900">Restablecer contraseña</h1>
        <p className="mb-4 text-sm text-slate-600">Seguí los pasos para recuperar tu acceso.</p>

        {step === 1 && (
          <div className="space-y-4">
            <label className="text-sm font-medium text-slate-700">
              Email
              <input
                type="email"
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
            <label className="text-sm font-medium text-slate-700">
              Código recibido
              <input
                type="text"
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
              <input
                type="password"
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
                placeholder="Mínimo 6 caracteres"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Confirmar contraseña
              <input
                type="password"
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
                placeholder="Repite la nueva contraseña"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
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

        {info && <p className="mt-3 rounded-md bg-amber-50 p-3 text-sm text-amber-800">{info}</p>}
        {saved && (
          <p className="mt-3 rounded-md bg-emerald-50 p-3 text-sm text-emerald-700">
            Contraseña actualizada. Redirigiendo al login.
          </p>
        )}
        {error && <p className="mt-3 rounded-md bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
        <div className="mt-4 text-sm">
          <Link to="/login" className="text-brand-700 hover:underline">
            Volver al login
          </Link>
        </div>
      </div>
    </div>
  );
}
