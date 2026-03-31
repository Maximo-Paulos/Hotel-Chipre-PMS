import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getOnboardingStatus } from "../../api/onboarding";
import { sendVerificationEmail, verifyEmailCode } from "../../api/email";
import { useSession } from "../../state/session";

export function VerifyEmailPage() {
  const navigate = useNavigate();
  const { session } = useSession();
  const [message, setMessage] = useState<string | null>(null);
  const [email, setEmail] = useState(session.email || session.userId || "");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  const refreshStatus = async () => {
    const status = await getOnboardingStatus(session);
    if (status.owner) {
      setMessage("Email verificado o owner creado. Podés continuar con el onboarding.");
    } else {
      setMessage("Aún no vemos un owner. Probá guardar los datos nuevamente.");
    }
  };

  const handleSend = async () => {
    setError(null);
    setLoading(true);
    try {
      await sendVerificationEmail(email, session);
      setSent(true);
      setMessage("Enviamos un código a tu correo.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo enviar el correo");
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    setError(null);
    setLoading(true);
    try {
      await verifyEmailCode(email, code, session);
      setMessage("Código correcto. Email verificado.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Código inválido o expirado");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <h1 className="text-2xl font-semibold text-slate-900">Verificá tu email</h1>
        <p className="mb-4 text-sm text-slate-600">
          Te enviamos un correo con un código de verificación. Sin email verificado no se habilitan acciones ni onboarding.
        </p>
        <div className="space-y-3 text-sm text-slate-700">
          <label className="text-sm font-medium text-slate-700">
            Email
            <input
              value={email}
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
              onClick={refreshStatus}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300"
            >
              Chequear estado
            </button>
          </div>
          <label className="text-sm font-medium text-slate-700">
            Código
            <input
              value={code}
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
        {message && <p className="mt-3 rounded-md bg-emerald-50 p-3 text-emerald-700">{message}</p>}
        {sent && <p className="mt-1 text-xs text-slate-500">Código enviado.</p>}
        {error && <p className="mt-3 rounded-md bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
        <div className="mt-6 flex items-center justify-between text-sm">
          <Link to="/login" className="text-brand-700 hover:underline">
            Volver al login
          </Link>
          <div className="flex items-center gap-2">
            <button
              className="rounded-lg bg-brand-600 px-3 py-2 text-white shadow-sm hover:bg-brand-700"
              onClick={() => navigate("/onboarding")}
              type="button"
            >
              Ir al onboarding
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
