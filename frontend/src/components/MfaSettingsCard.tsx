import { useQuery, useQueryClient } from "@tanstack/react-query";
import { QRCodeSVG } from "qrcode.react";
import { useRef, useState, type FormEvent } from "react";

import {
  confirmMfaEnrollment,
  currentUser,
  disableMfa,
  enrollMfa,
  getMfaStatus,
  mfaStatusQueryKey,
  regenerateMfaRecoveryCodes,
  type MfaEnrollment
} from "../api/auth";
import { ApiError, hasValidSession, type SessionLike } from "../api/client";
import { useAuthProviders } from "../hooks/useAuthProviders";

import { GoogleSignInButton } from "./GoogleSignInButton";
import { PasswordInput } from "./PasswordInput";

type ManagementMode = "disable" | "recovery" | null;

type Props = {
  session: SessionLike;
  returnTo: string | null;
  onContinue: () => void;
};

const safeMfaError = (error: unknown, action: "enroll" | "confirm" | "disable" | "recovery") => {
  if (error instanceof ApiError && error.status === 429) {
    return "Hubo demasiados intentos. Esperá unos minutos antes de volver a probar.";
  }
  if (error instanceof ApiError && error.status === 401) {
    return action === "enroll"
      ? "La contraseña o la confirmación de identidad no es válida. Volvé a verificar tu identidad."
      : action === "confirm"
        ? "El código no es válido o venció. Revisá la hora de tu teléfono e intentá de nuevo."
        : "La contraseña, el código o la confirmación de identidad no es válida.";
  }
  if (error instanceof ApiError && error.status === 409 && action === "enroll") {
    return "La verificación en 2 pasos ya está activada. Actualizá el estado de seguridad.";
  }
  return "No se pudo completar esta operación. Revisá tu conexión e intentá de nuevo.";
};

export function MfaSettingsCard({ session, returnTo, onContinue }: Props) {
  const queryClient = useQueryClient();
  const googleProofRef = useRef<string | null>(null);
  const authProvidersQuery = useAuthProviders();
  const statusQuery = useQuery({
    queryKey: mfaStatusQueryKey(session.userId ?? null),
    queryFn: () => getMfaStatus(session),
    enabled: hasValidSession(session),
    staleTime: 0,
    retry: false
  });
  const userQuery = useQuery({
    queryKey: ["auth-user", session.hotelId, session.userId],
    queryFn: () => currentUser(session),
    enabled: hasValidSession(session),
    staleTime: 15_000
  });

  const [enrollment, setEnrollment] = useState<MfaEnrollment | null>(null);
  const [enrollmentOpen, setEnrollmentOpen] = useState(false);
  const [enrollmentPassword, setEnrollmentPassword] = useState("");
  const [confirmationCode, setConfirmationCode] = useState("");
  const [managementMode, setManagementMode] = useState<ManagementMode>(null);
  const [managementCode, setManagementCode] = useState("");
  const [managementPassword, setManagementPassword] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const [copyMessage, setCopyMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const passwordLoginEnabled = userQuery.data?.password_login_enabled === true;
  const googleLoginAvailable = authProvidersQuery.data?.google?.enabled === true
    && userQuery.data?.google_login_enabled === true;
  const userCanReauthenticate = passwordLoginEnabled || googleLoginAvailable;

  const clearEnrollment = () => {
    googleProofRef.current = null;
    setEnrollment(null);
    setEnrollmentOpen(false);
    setEnrollmentPassword("");
    setConfirmationCode("");
    setErrorMessage("");
  };

  const completeEnrollment = async (proof: { currentPassword?: string; googleIdToken?: string }) => {
    if (isSaving) return;
    setIsSaving(true);
    setErrorMessage("");
    try {
      const pending = await enrollMfa(proof, session);
      googleProofRef.current = null;
      setEnrollmentPassword("");
      setEnrollment(pending);
      setEnrollmentOpen(false);
    } catch (error) {
      googleProofRef.current = null;
      setErrorMessage(safeMfaError(error, "enroll"));
    } finally {
      setIsSaving(false);
    }
  };

  const handleEnrollmentSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!enrollmentPassword) return;
    await completeEnrollment({ currentPassword: enrollmentPassword });
  };

  const handleGoogleEnrollmentProof = (idToken: string) => {
    googleProofRef.current = idToken;
    void completeEnrollment({ googleIdToken: idToken });
  };

  const handleConfirmEnrollment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const code = confirmationCode.trim();
    if (!enrollment || !/^\d{6}$/.test(code) || isSaving) return;
    setIsSaving(true);
    setErrorMessage("");
    try {
      const result = await confirmMfaEnrollment(code, session);
      setRecoveryCodes(result.recovery_codes);
      setEnrollment(null);
      setConfirmationCode("");
      await queryClient.invalidateQueries({ queryKey: mfaStatusQueryKey(session.userId ?? null) });
    } catch (error) {
      setErrorMessage(safeMfaError(error, "confirm"));
    } finally {
      setIsSaving(false);
    }
  };

  const handleRegenerateCodes = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const code = managementCode.trim();
    if (!code || isSaving) return;
    setIsSaving(true);
    setErrorMessage("");
    try {
      const result = await regenerateMfaRecoveryCodes(code, session);
      setRecoveryCodes(result.recovery_codes);
      setManagementMode(null);
      setManagementCode("");
      await queryClient.invalidateQueries({ queryKey: mfaStatusQueryKey(session.userId ?? null) });
    } catch (error) {
      setErrorMessage(safeMfaError(error, "recovery"));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDisable = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!managementCode.trim() || isSaving) return;
    if (!window.confirm("¿Desactivar la verificación en 2 pasos? Las acciones sensibles dejarán de pedir este factor.")) return;
    setIsSaving(true);
    setErrorMessage("");
    try {
      await disableMfa(
        {
          code: managementCode.trim(),
          ...(passwordLoginEnabled ? { password: managementPassword } : {}),
          ...(!passwordLoginEnabled && googleProofRef.current ? { googleIdToken: googleProofRef.current } : {})
        },
        session
      );
      googleProofRef.current = null;
      setManagementMode(null);
      setManagementCode("");
      setManagementPassword("");
      setErrorMessage("");
      await queryClient.invalidateQueries({ queryKey: mfaStatusQueryKey(session.userId ?? null) });
    } catch (error) {
      googleProofRef.current = null;
      setErrorMessage(safeMfaError(error, "disable"));
    } finally {
      setIsSaving(false);
    }
  };

  const copyRecoveryCodes = async () => {
    if (!recoveryCodes) return;
    try {
      await navigator.clipboard.writeText(recoveryCodes.join("\n"));
      setCopyMessage("Códigos copiados. Guardalos fuera de este dispositivo.");
    } catch {
      setCopyMessage("No se pudieron copiar. Anotalos en un lugar seguro antes de continuar.");
    }
  };

  const finishRecoveryCodes = () => {
    setRecoveryCodes(null);
    setCopyMessage("");
    if (returnTo) onContinue();
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="mfa-settings-title" data-testid="mfa-settings-card">
      <div className="max-w-3xl">
        <h2 id="mfa-settings-title" className="text-lg font-semibold text-slate-900">Verificación en 2 pasos</h2>
        <p className="mt-1 text-sm text-slate-600">
          Protegé permisos y operaciones sensibles con una app autenticadora y códigos de recuperación.
        </p>
      </div>

      {statusQuery.isPending ? (
        <p className="mt-4 text-sm text-slate-500" role="status">Consultando el estado del autenticador...</p>
      ) : statusQuery.isError ? (
        <div className="mt-4" role="alert">
          <p className="text-sm text-rose-700">No se pudo consultar el estado de la verificación en 2 pasos.</p>
          <button type="button" className="mt-2 text-sm font-semibold text-brand-700 underline" onClick={() => void statusQuery.refetch()}>
            Reintentar
          </button>
        </div>
      ) : recoveryCodes ? (
        <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 p-4" data-testid="mfa-recovery-codes">
          <h3 className="font-semibold text-amber-950">Guardá estos códigos de recuperación</h3>
          <p className="mt-1 text-sm text-amber-900">Se muestran una sola vez. Cada código sirve para una sola verificación. No los compartas ni los guardes en esta app.</p>
          <ol className="mt-4 grid gap-2 font-mono text-sm sm:grid-cols-2" aria-label="Códigos de recuperación">
            {recoveryCodes.map((code) => <li key={code} className="rounded border border-amber-200 bg-white px-3 py-2">{code}</li>)}
          </ol>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button type="button" onClick={() => void copyRecoveryCodes()} className="rounded-lg border border-amber-500 bg-white px-4 py-2 text-sm font-semibold text-amber-950 hover:bg-amber-100" data-testid="mfa-copy-recovery-codes">
              Copiar códigos
            </button>
            <button type="button" onClick={finishRecoveryCodes} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700" data-testid="mfa-finish-recovery-codes">
              {returnTo ? "Ya los guardé, volver a la acción" : "Ya los guardé"}
            </button>
            {copyMessage && <p role="status" className="text-sm text-amber-950">{copyMessage}</p>}
          </div>
        </div>
      ) : enrollment ? (
        <div className="mt-4 grid gap-5 rounded-lg border border-slate-200 bg-slate-50 p-4 sm:grid-cols-[240px_minmax(0,1fr)] sm:items-center">
          <div className="mx-auto rounded-lg bg-white p-3" data-testid="mfa-enrollment-qr">
            <QRCodeSVG value={enrollment.otpauth_uri} size={216} title="Código QR para registrar el autenticador" includeMargin />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900">1. Registrá esta cuenta en tu app autenticadora</h3>
            <p className="mt-1 text-sm text-slate-600">Escaneá el QR. Si no podés escanearlo, ingresá esta clave manualmente:</p>
            <code className="mt-3 block break-all rounded border border-slate-200 bg-white p-3 font-mono text-sm text-slate-900" data-testid="mfa-enrollment-secret">
              {enrollment.secret}
            </code>
            <p className="mt-4 text-sm font-semibold text-slate-800">2. Ingresá el código de 6 dígitos de la app para confirmar</p>
            <form className="mt-2 space-y-3" onSubmit={handleConfirmEnrollment}>
              <label htmlFor="mfa-enrollment-code" className="block text-sm font-medium text-slate-700">
                Código temporal
                <input
                  id="mfa-enrollment-code"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  value={confirmationCode}
                  onChange={(event) => setConfirmationCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                  className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  required
                />
              </label>
              {errorMessage && <p role="alert" className="text-sm text-rose-700">{errorMessage}</p>}
              <div className="flex flex-wrap gap-2">
                <button type="submit" disabled={isSaving || confirmationCode.length !== 6} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60" data-testid="mfa-confirm-enrollment">
                  {isSaving ? "Verificando..." : "Confirmar y activar"}
                </button>
                <button type="button" onClick={clearEnrollment} disabled={isSaving} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : statusQuery.data?.enabled ? (
        <>
          <p className="mt-4 inline-flex rounded-md bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-800" role="status" data-testid="mfa-enabled-status">
            Verificación en 2 pasos activada
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" onClick={() => { setManagementMode("recovery"); setErrorMessage(""); }} disabled={isSaving} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50" data-testid="mfa-regenerate-codes">
              Regenerar códigos de recuperación
            </button>
            <button type="button" onClick={() => { setManagementMode("disable"); setErrorMessage(""); }} disabled={isSaving} className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-800 hover:bg-rose-100" data-testid="mfa-start-disable">
              Desactivar
            </button>
          </div>
          {managementMode === "recovery" && (
            <form className="mt-4 max-w-xl space-y-3 rounded-lg border border-slate-200 p-4" onSubmit={handleRegenerateCodes}>
              <p className="text-sm text-slate-700">Ingresá un código de tu app o un código de recuperación. Los códigos anteriores dejarán de funcionar.</p>
              <label htmlFor="mfa-regenerate-code" className="block text-sm font-medium text-slate-700">
                Código actual
                <input id="mfa-regenerate-code" type="text" autoComplete="one-time-code" value={managementCode} onChange={(event) => setManagementCode(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900" required />
              </label>
              {errorMessage && <p role="alert" className="text-sm text-rose-700">{errorMessage}</p>}
              <div className="flex gap-2">
                <button type="submit" disabled={isSaving || !managementCode.trim()} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">{isSaving ? "Regenerando..." : "Confirmar regeneración"}</button>
                <button type="button" onClick={() => { setManagementMode(null); setManagementCode(""); setErrorMessage(""); }} disabled={isSaving} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700">Cancelar</button>
              </div>
            </form>
          )}
          {managementMode === "disable" && (
            <form className="mt-4 max-w-xl space-y-3 rounded-lg border border-rose-200 bg-rose-50 p-4" onSubmit={handleDisable}>
              <p className="text-sm text-rose-900">Para desactivar, confirmá tu identidad y usá un código actual o de recuperación.</p>
              {passwordLoginEnabled ? (
                <label htmlFor="mfa-disable-password" className="block text-sm font-medium text-slate-700">
                  Contraseña actual
                  <PasswordInput id="mfa-disable-password" value={managementPassword} onChange={setManagementPassword} autoComplete="current-password" required />
                </label>
              ) : googleLoginAvailable ? (
                <div>
                  <GoogleSignInButton onCredential={(token) => { googleProofRef.current = token; setErrorMessage(""); }} />
                  <p className="mt-2 text-xs text-slate-600">Volvé a confirmar la cuenta de Google vinculada a este usuario.</p>
                </div>
              ) : <p className="text-sm text-rose-800">No hay un método de reautenticación disponible para esta cuenta.</p>}
              <label htmlFor="mfa-disable-code" className="block text-sm font-medium text-slate-700">
                Código actual o de recuperación
                <input id="mfa-disable-code" type="text" autoComplete="one-time-code" value={managementCode} onChange={(event) => setManagementCode(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900" required />
              </label>
              {errorMessage && <p role="alert" className="text-sm text-rose-700">{errorMessage}</p>}
              <div className="flex gap-2">
                <button type="submit" disabled={isSaving || !userCanReauthenticate || !managementCode.trim() || (passwordLoginEnabled && !managementPassword) || (!passwordLoginEnabled && !googleProofRef.current)} className="rounded-lg bg-rose-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" data-testid="mfa-confirm-disable">{isSaving ? "Desactivando..." : "Desactivar verificación"}</button>
                <button type="button" onClick={() => { googleProofRef.current = null; setManagementMode(null); setManagementCode(""); setManagementPassword(""); setErrorMessage(""); }} disabled={isSaving} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700">Cancelar</button>
              </div>
            </form>
          )}
        </>
      ) : (
        <div className="mt-4">
          <p className="text-sm text-slate-700">Todavía no configuraste un autenticador. Activá la verificación para usar permisos y operaciones que requieren un segundo factor.</p>
          {!userQuery.isLoading && !authProvidersQuery.isLoading && !userCanReauthenticate && (
            <p role="alert" className="mt-2 text-sm text-rose-700">
              {authProvidersQuery.data?.google?.enabled === true
                ? "Tu cuenta no tiene un método de reautenticación compatible. Configurá una contraseña o vinculá una cuenta compatible antes de activar MFA."
                : "Tu cuenta no tiene un método de reautenticación habilitado. Contactá al responsable del hotel antes de activar MFA."}
            </p>
          )}
          {!enrollmentOpen ? (
            <button type="button" onClick={() => { setEnrollmentOpen(true); setErrorMessage(""); }} disabled={userQuery.isLoading || authProvidersQuery.isLoading || !userCanReauthenticate || isSaving} className="mt-3 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60" data-testid="mfa-start-enrollment">
              Activar verificación en 2 pasos
            </button>
          ) : (
            <div className="mt-4 max-w-xl rounded-lg border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-700">Confirmá tu identidad con el método de acceso que ya está vinculado a esta cuenta.</p>
              {passwordLoginEnabled ? (
                <form className="mt-3 space-y-3" onSubmit={handleEnrollmentSubmit}>
                  <label htmlFor="mfa-enrollment-password" className="block text-sm font-medium text-slate-700">
                    Contraseña actual
                    <PasswordInput id="mfa-enrollment-password" value={enrollmentPassword} onChange={setEnrollmentPassword} autoComplete="current-password" required />
                  </label>
                  {errorMessage && <p role="alert" className="text-sm text-rose-700">{errorMessage}</p>}
                  <div className="flex gap-2">
                    <button type="submit" disabled={isSaving || !enrollmentPassword} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" data-testid="mfa-submit-enrollment-proof">{isSaving ? "Verificando..." : "Continuar"}</button>
                    <button type="button" onClick={clearEnrollment} disabled={isSaving} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700">Cancelar</button>
                  </div>
                </form>
              ) : googleLoginAvailable ? (
                <div className="mt-3 space-y-3">
                  <GoogleSignInButton onCredential={handleGoogleEnrollmentProof} />
                  {errorMessage && <p role="alert" className="text-sm text-rose-700">{errorMessage}</p>}
                  <button type="button" onClick={clearEnrollment} disabled={isSaving} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700">Cancelar</button>
                </div>
              ) : null}
            </div>
          )}
          {errorMessage && !enrollmentOpen && <p role="alert" className="mt-3 text-sm text-rose-700">{errorMessage}</p>}
        </div>
      )}
    </section>
  );
}
