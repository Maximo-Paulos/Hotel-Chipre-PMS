import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import { useMasterAdminSession } from "../session";

export function MasterAdminLoginPage() {
  const { status, login, completeMfaLogin, enrollMfa, confirmMfa, refresh } = useMasterAdminSession();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pin, setPin] = useState("");
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [enrollment, setEnrollment] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [setupComplete, setSetupComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (status === "authenticated") {
    const redirectTo = (location.state as { from?: string } | null)?.from || "/adminpmsmaster/dashboard";
    return <Navigate to={redirectTo} replace />;
  }

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      if (mfaToken) {
        await completeMfaLogin(mfaToken, mfaCode);
        navigate("/adminpmsmaster/dashboard", { replace: true });
      } else if (status === "mfa_setup_required") {
        if (setupComplete) {
          await refresh();
          navigate("/adminpmsmaster/dashboard", { replace: true });
        } else if (!enrollment) {
          const nextEnrollment = await enrollMfa(password);
          setEnrollment(nextEnrollment);
        } else {
          const result = await confirmMfa(mfaCode);
          setRecoveryCodes(result.recovery_codes);
          setSetupComplete(true);
        }
      } else {
        const result = await login(email, password, pin);
        if ("requires_mfa" in result) {
          setMfaToken(result.mfa_token);
        } else if (!("requires_mfa_setup" in result)) {
          navigate("/adminpmsmaster/dashboard", { replace: true });
        }
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("No se pudo iniciar sesión en el panel master");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(251,191,36,0.16),_transparent_35%),linear-gradient(180deg,#020617_0%,#0f172a_55%,#111827_100%)] px-4 text-slate-100">
      <div className="w-full max-w-md rounded-[2rem] border border-white/10 bg-slate-950/80 p-8 shadow-2xl shadow-black/30 backdrop-blur">
        <p className="text-xs uppercase tracking-[0.35em] text-amber-300/80">Hotel Chipre</p>
        <h1 className="mt-3 text-3xl font-semibold text-white">Owner Master Panel</h1>
        <p className="mt-2 text-sm text-slate-300">
          Sesión separada del PMS normal. Requiere usuario platform_admin, contraseña, PIN y MFA TOTP.
        </p>

        <form className="mt-8 space-y-4" onSubmit={onSubmit}>
          {!mfaToken && status !== "mfa_setup_required" && <label className="block text-sm">
            <span className="mb-1 block text-slate-300">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition placeholder:text-slate-500 focus:border-amber-300/60"
              placeholder="platform-admin@hotelchipre.com"
            />
          </label>}
          {!mfaToken && status !== "mfa_setup_required" && <label className="block text-sm">
            <span className="mb-1 block text-slate-300">Contraseña</span>
            <input
              type="password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition placeholder:text-slate-500 focus:border-amber-300/60"
              placeholder="••••••••"
            />
          </label>}
          {!mfaToken && status !== "mfa_setup_required" && <label className="block text-sm">
            <span className="mb-1 block text-slate-300">PIN del panel</span>
            <input
              inputMode="numeric"
              required
              minLength={6}
              value={pin}
              onChange={(event) => setPin(event.target.value)}
              className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition placeholder:text-slate-500 focus:border-amber-300/60"
              placeholder="000000"
            />
          </label>}
          {mfaToken && <label className="block text-sm">
            <span className="mb-1 block text-slate-300">Código MFA</span>
            <input
              inputMode="numeric"
              required
              autoFocus
              value={mfaCode}
              onChange={(event) => setMfaCode(event.target.value)}
              className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-amber-300/60"
            />
          </label>}
          {status === "mfa_setup_required" && <>
            <div className="rounded-2xl border border-amber-300/30 bg-amber-300/10 px-4 py-3 text-sm text-amber-100">
              Este Master Admin no puede operar todavía. Configurá TOTP para continuar.
            </div>
            <label className="block text-sm">
              <span className="mb-1 block text-slate-300">Contraseña para reautenticar</span>
              <input
                type="password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-amber-300/60"
              />
            </label>
            {enrollment && <>
              <p className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
                Agregá este secreto a tu app autenticadora: <code className="break-all text-amber-200">{enrollment.secret}</code>
              </p>
              <label className="block text-sm">
                <span className="mb-1 block text-slate-300">Código TOTP de confirmación</span>
                <input
                  inputMode="numeric"
                  required
                  value={mfaCode}
                  onChange={(event) => setMfaCode(event.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-amber-300/60"
                />
              </label>
            </>}
            {recoveryCodes.length > 0 && <p className="rounded-2xl border border-emerald-300/30 bg-emerald-300/10 px-4 py-3 text-sm text-emerald-100">
              Guardá tus recovery codes: {recoveryCodes.join(", ")}
            </p>}
          </>}
          {error && <div className="rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">{error}</div>}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-2xl bg-amber-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {loading ? "Procesando..." : mfaToken ? "Verificar MFA" : status === "mfa_setup_required" ? (setupComplete ? "Continuar al panel" : enrollment ? "Confirmar TOTP" : "Configurar TOTP") : "Entrar al panel"}
          </button>
        </form>
      </div>
    </div>
  );
}
