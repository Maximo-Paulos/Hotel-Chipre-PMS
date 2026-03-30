import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getOnboardingStatus } from "../../api/onboarding";
import { useSession } from "../../state/session";

export function VerifyEmailPage() {
  const navigate = useNavigate();
  const { session } = useSession();
  const [message, setMessage] = useState<string | null>(null);

  const refreshStatus = async () => {
    const status = await getOnboardingStatus(session);
    if (status.owner) {
      setMessage("Email verificado o owner creado. PodÃ©s continuar con el onboarding.");
    } else {
      setMessage("AÃºn no vemos un owner. ProbÃ¡ guardar los datos nuevamente.");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <h1 className="text-2xl font-semibold text-slate-900">VerificÃ¡ tu email</h1>
        <p className="mb-4 text-sm text-slate-600">
          Te enviamos un correo con un enlace de verificaciÃ³n. Sin email verificado no se habilitan acciones ni onboarding.
        </p>
        <div className="space-y-3 text-sm text-slate-700">
          <p>1. RevisÃ¡ tu bandeja de entrada y spam.</p>
          <p>2. Si expirÃ³, pedÃ­ reenviar el enlace.</p>
        </div>
        {message && <p className="mt-3 rounded-md bg-emerald-50 p-3 text-emerald-700">{message}</p>}
        <div className="mt-6 flex items-center justify-between text-sm">
          <Link to="/login" className="text-brand-700 hover:underline">
            Volver al login
          </Link>
          <div className="flex items-center gap-2">
            <button
              className="rounded-lg border border-slate-200 px-3 py-2 text-slate-700 shadow-sm hover:bg-slate-50"
              onClick={refreshStatus}
              type="button"
            >
              Reenviar/chequear
            </button>
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
