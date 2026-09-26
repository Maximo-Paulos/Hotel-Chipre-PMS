import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import {
  acceptInvitation,
  acceptInvitationWithGoogle,
  completeMfaInvitationAcceptance,
  getInvitationInfo,
  isMfaChallenge,
  type AuthResponse
} from "../../api/auth";
import { GoogleSignInButton } from "../../components/GoogleSignInButton";
import { PasswordInput } from "../../components/PasswordInput";
import { Seo } from "../../components/Seo";
import { defaultPathForRole, normalizeRole, useSession } from "../../state/session";

type InvitationInfo = {
  email: string;
  hotel_name?: string;
  inviter_email?: string;
};

const sessionFromAuthResponse = (response: AuthResponse) => {
  const role = normalizeRole(response.user.role);
  return {
    userId: response.user.email,
    email: response.user.email,
    hotelId: response.hotel_id,
    hotelIds: response.hotel_ids?.length ? response.hotel_ids : [response.hotel_id],
    role,
    baseRole: role,
    permissions: response.permissions ?? response.user.permissions ?? null,
    accessToken: response.access_token,
    csrfToken: response.csrf_token,
    isVerified: response.user.is_verified
  };
};

export function AcceptInvitationPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryToken = new URLSearchParams(location.search).get("token") || "";
  const token = queryToken || new URLSearchParams(location.hash.slice(1)).get("token") || "";
  const { login, logout, session, isInitializing } = useSession();
  const attemptedSessionAccept = useRef<string | null>(null);

  useEffect(() => {
    // Keep compatibility with already-sent query-string invitation links,
    // but immediately remove the capability from the request-visible URL.
    if (queryToken) {
      navigate(
        { pathname: location.pathname, search: "", hash: `#token=${encodeURIComponent(token)}` },
        { replace: true }
      );
    }
  }, [location.pathname, navigate, queryToken, token]);

  const [invitation, setInvitation] = useState<InvitationInfo | null>(null);
  const [isLoadingInfo, setIsLoadingInfo] = useState(true);
  const [currentPassword, setCurrentPassword] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    setIsLoadingInfo(true);
    setInvitation(null);
    setError(null);
    setInfo(null);
    setMfaToken(null);
    attemptedSessionAccept.current = null;

    if (!token) {
      setError("Token de invitación inválido.");
      setIsLoadingInfo(false);
      return () => {
        active = false;
      };
    }

    getInvitationInfo(token)
      .then((data) => {
        if (active) setInvitation(data);
      })
      .catch((err) => {
        if (active) setError(err instanceof ApiError ? err.message : "Invitación inválida o expirada");
      })
      .finally(() => {
        if (active) setIsLoadingInfo(false);
      });

    return () => {
      active = false;
    };
  }, [token]);

  const finishAcceptance = useCallback(async (response: AuthResponse) => {
    if (!response.hotel_id) {
      throw new ApiError(500, "La respuesta de invitación no devolvió un hotel válido.");
    }
    attemptedSessionAccept.current = token;
    const role = normalizeRole(response.user.role);
    login(sessionFromAuthResponse(response));
    setInfo("Invitación aceptada. Redirigiendo...");
    navigate(defaultPathForRole(role), { replace: true });
  }, [login, navigate, token]);

  const acceptForCurrentSession = useCallback(async () => {
    if (!token || !invitation?.email) return;
    setLoading(true);
    setError(null);
    setInfo(null);
    try {
      const result = await acceptInvitation(token, invitation.email, undefined, session);
      if (isMfaChallenge(result)) {
        setMfaToken(result.mfa_token);
        setMfaCode("");
        setInfo("La invitación seguirá pendiente hasta que confirmes tu código de seguridad.");
        return;
      }
      await finishAcceptance(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo aceptar la invitación");
    } finally {
      setLoading(false);
    }
  }, [finishAcceptance, invitation?.email, session, token]);

  useEffect(() => {
    if (isInitializing || !session.accessToken || !invitation?.email || !token) return;
    if (session.email?.trim().toLowerCase() !== invitation.email.trim().toLowerCase()) return;
    if (attemptedSessionAccept.current === token) return;
    attemptedSessionAccept.current = token;
    void acceptForCurrentSession();
  }, [acceptForCurrentSession, invitation?.email, isInitializing, session.accessToken, session.email, token]);

  const handleGoogleCredential = async (idToken: string) => {
    if (!token) return;
    setLoading(true);
    setError(null);
    setInfo(null);
    setMfaToken(null);
    try {
      const result = await acceptInvitationWithGoogle(token, idToken);
      if (isMfaChallenge(result)) {
        setMfaToken(result.mfa_token);
        setMfaCode("");
        setInfo("La invitación seguirá pendiente hasta que confirmes tu código de seguridad.");
        return;
      }
      await finishAcceptance(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo aceptar con Google");
    } finally {
      setLoading(false);
    }
  };

  const handleMfaSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!mfaToken || !token || !invitation?.email) return;
    setLoading(true);
    setError(null);
    setInfo(null);
    try {
      const authenticated = await completeMfaInvitationAcceptance(token, mfaToken, mfaCode.trim());
      // The signed MFA challenge is bound to the pending invitation, which is
      // consumed by the backend only after this second factor succeeds.
      await finishAcceptance(authenticated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo verificar el código");
    } finally {
      setLoading(false);
    }
  };

  const submitCurrentPassword = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setInfo(null);
    if (!token || !invitation?.email) {
      setError("Token de invitación inválido.");
      return;
    }
    if (!currentPassword) {
      setError("Ingresá la contraseña actual de tu cuenta.");
      return;
    }
    setLoading(true);
    try {
      const result = await acceptInvitation(token, invitation.email, { currentPassword });
      if (isMfaChallenge(result)) {
        setMfaToken(result.mfa_token);
        setMfaCode("");
        setInfo("La invitación seguirá pendiente hasta que confirmes tu código de seguridad.");
        return;
      }
      await finishAcceptance(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo verificar tu contraseña");
    } finally {
      setLoading(false);
    }
  };

  const submitPassword = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setInfo(null);
    if (!token || !invitation?.email) {
      setError("Token de invitación inválido.");
      return;
    }
    if (password.length < 12) {
      setError("La contraseña nueva debe tener al menos 12 caracteres.");
      return;
    }
    if (password !== confirm) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setLoading(true);
    try {
      const result = await acceptInvitation(token, invitation.email, { password });
      if (isMfaChallenge(result)) {
        setMfaToken(result.mfa_token);
        setMfaCode("");
        setInfo("La invitación seguirá pendiente hasta que confirmes tu código de seguridad.");
        return;
      }
      await finishAcceptance(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo aceptar la invitación");
    } finally {
      setLoading(false);
    }
  };

  const signInUrl = `/login#invitation=${encodeURIComponent(token)}`;
  const hasSession = Boolean(session.accessToken);
  const sessionEmailMatches = Boolean(
    invitation?.email && session.email?.trim().toLowerCase() === invitation.email.trim().toLowerCase()
  );

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-8">
      <Seo title="Aceptar invitación | Hotels-PMS" description="Activa tu acceso al hotel invitado." noindex />
      <main className="w-full max-w-md rounded-2xl bg-white p-6 shadow-lg ring-1 ring-slate-100 sm:p-8">
        <h1 className="text-balance text-2xl font-semibold tracking-tight text-slate-900">Aceptar invitación</h1>
        <p className="mt-2 text-sm text-slate-600">Ingresá con Google, verificá tu cuenta existente o creá una nueva contraseña si es tu primer acceso.</p>

        {isLoadingInfo ? (
          <p className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600" role="status">
            Cargando invitación...
          </p>
        ) : invitation ? (
          <>
            <div className="mt-5 space-y-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700">
              {invitation.hotel_name && <p><strong>Hotel:</strong> {invitation.hotel_name}</p>}
              {invitation.inviter_email && <p><strong>Invitado por:</strong> {invitation.inviter_email}</p>}
              <p><strong>Email invitado:</strong> <span className="break-all text-slate-900">{invitation.email}</span></p>
            </div>

            {hasSession && sessionEmailMatches && !loading && !mfaToken && !error && (
              <p className="mt-4 rounded-lg border border-brand-100 bg-brand-50 p-3 text-sm text-brand-900" role="status">
                Tu sesión coincide con el email invitado. Estamos activando el acceso.
              </p>
            )}
            {hasSession && sessionEmailMatches && error && !mfaToken && (
              <button
                type="button"
                onClick={() => void acceptForCurrentSession()}
                disabled={loading}
                className="mt-4 w-full rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-sm font-semibold text-brand-800 hover:bg-brand-100 disabled:opacity-60"
              >
                Reintentar aceptación
              </button>
            )}

            {hasSession && !sessionEmailMatches && (
              <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900" role="status">
                <p>La sesión actual usa otro email. Cerrala para entrar con la dirección de esta invitación.</p>
                <button
                  type="button"
                  onClick={() => {
                    logout();
                    attemptedSessionAccept.current = null;
                    setInfo(null);
                    setError(null);
                  }}
                  className="mt-2 rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm font-semibold text-amber-900 hover:bg-amber-100"
                >
                  Cerrar esta sesión
                </button>
              </div>
            )}

            {mfaToken ? (
              <form className="mt-5 space-y-4" onSubmit={handleMfaSubmit}>
                <p className="rounded-lg border border-brand-100 bg-brand-50 p-3 text-sm text-brand-900" role="status">
                  Esta cuenta tiene activada la verificación en dos pasos. Ingresá el código temporal de 6 dígitos de la app autenticadora que vinculaste, o un código de recuperación guardado. No te llegará por email. La invitación seguirá pendiente hasta verificarlo.
                </p>
                <label className="block text-sm font-medium text-slate-700" htmlFor="invitation-mfa-code">
                  Código de la app autenticadora o de recuperación
                  <input
                    id="invitation-mfa-code"
                    autoComplete="one-time-code"
                    inputMode="numeric"
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    value={mfaCode}
                    onChange={(event) => setMfaCode(event.target.value)}
                    required
                    autoFocus
                  />
                </label>
                <button
                  type="submit"
                  disabled={loading || !mfaCode.trim()}
                  className="w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                >
                  {loading ? "Verificando..." : "Verificar y aceptar invitación"}
                </button>
              </form>
            ) : !sessionEmailMatches && (
              <>
                <div className="mt-5 rounded-lg border border-slate-200 p-3">
                  <p className="mb-3 text-sm font-medium text-slate-700">Usar Google con el email de la invitación</p>
                  <div aria-disabled={loading} className={loading ? "pointer-events-none opacity-60" : undefined}>
                    <GoogleSignInButton onCredential={handleGoogleCredential} />
                  </div>
                  {loading && <p className="mt-2 text-center text-xs text-slate-500" role="status">Verificando con Google...</p>}
                </div>

                {!hasSession && (
                  <>
                    <section className="mt-5 rounded-lg border border-slate-200 p-3">
                      <h2 className="text-sm font-semibold text-slate-800">Ya tenés una cuenta</h2>
                      <p className="mt-1 text-xs text-slate-600">Ingresá tu contraseña actual; no se modifica.</p>
                      <form className="mt-3 space-y-3" onSubmit={submitCurrentPassword}>
                        <label className="block text-sm font-medium text-slate-700" htmlFor="invitation-current-password">
                          Contraseña actual
                        </label>
                        <PasswordInput
                          id="invitation-current-password"
                          value={currentPassword}
                          onChange={setCurrentPassword}
                          placeholder="Tu contraseña actual"
                          required
                          autoComplete="current-password"
                        />
                        <button
                          className="w-full rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-sm font-semibold text-brand-800 hover:bg-brand-100 disabled:opacity-60"
                          disabled={loading || !token}
                          type="submit"
                        >
                          {loading ? "Verificando..." : "Verificar y aceptar"}
                        </button>
                      </form>
                    </section>

                    <div className="relative my-4 flex items-center">
                      <div className="flex-grow border-t border-slate-200" />
                      <span className="mx-3 text-xs uppercase text-slate-400">primer acceso</span>
                      <div className="flex-grow border-t border-slate-200" />
                    </div>
                    <form className="space-y-4" onSubmit={submitPassword}>
                      <label className="block text-sm font-medium text-slate-700" htmlFor="invitation-password">
                        Contraseña nueva
                      </label>
                      <PasswordInput
                        id="invitation-password"
                        value={password}
                        onChange={setPassword}
                        placeholder="Mínimo 12 caracteres"
                        required
                        autoComplete="new-password"
                      />
                      <label className="block text-sm font-medium text-slate-700" htmlFor="invitation-password-confirm">
                        Confirmar contraseña
                        <input
                          id="invitation-password-confirm"
                          type="password"
                          autoComplete="new-password"
                          className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                          placeholder="Repetí tu contraseña"
                          minLength={12}
                          value={confirm}
                          onChange={(event) => setConfirm(event.target.value)}
                          required
                        />
                      </label>
                      <button
                        className="w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-60"
                        disabled={loading || !token}
                        type="submit"
                      >
                        {loading ? "Verificando..." : "Continuar y aceptar"}
                      </button>
                    </form>
                  </>
                )}

                <p className="mt-5 text-center text-sm text-slate-600">
                  ¿Ya tenés una cuenta? <Link to={signInUrl} className="font-semibold text-brand-700 hover:underline">Ingresá y aceptá</Link>
                </p>
              </>
            )}
          </>
        ) : null}

        {info && <p className="mt-4 rounded-md bg-emerald-50 p-3 text-sm text-emerald-800" role="status">{info}</p>}
        {error && <p className="mt-4 rounded-md bg-rose-50 p-3 text-sm text-rose-700" role="alert">{error}</p>}

        {loading && !mfaToken && (
          <p className="mt-4 text-center text-sm text-slate-500" role="status">Procesando la invitación...</p>
        )}
        <div className="mt-5 text-center text-sm">
          <Link to={signInUrl} className="text-brand-700 hover:underline">Volver al ingreso</Link>
        </div>
      </main>
    </div>
  );
}
