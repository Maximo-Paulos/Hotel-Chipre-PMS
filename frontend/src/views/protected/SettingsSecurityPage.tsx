import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useRef, useState } from "react";

import { hasValidSession } from "../../api/client";
import { currentUser, linkGoogle, setPasswordWithGoogle } from "../../api/auth";
import { getSecurityEvents, getSecurityOverview, revokeAllSessions } from "../../api/security";
import { useSession } from "../../state/session";
import { useGuardedMutation } from "../../hooks/useGuardedMutation";
import { GoogleSignInButton } from "../../components/GoogleSignInButton";
import { PasswordInput } from "../../components/PasswordInput";

const formatEventAction = (action: string) => action.replace(/_/g, " ").replace(/:/g, " · ");

export function SettingsSecurityPage() {
  const navigate = useNavigate();
  const { session, logout } = useSession();
  const enabled = hasValidSession(session);
  const userQuery = useQuery({
    queryKey: ["auth-user", session.hotelId, session.userId],
    queryFn: () => currentUser(session),
    enabled,
    staleTime: 15 * 1000
  });
  const googleIdTokenRef = useRef<string | null>(null);
  const googleLinkIdTokenRef = useRef<string | null>(null);
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [showGoogleLinkForm, setShowGoogleLinkForm] = useState(false);
  const [googleLinkPassword, setGoogleLinkPassword] = useState("");
  const [googleLinkError, setGoogleLinkError] = useState<string | null>(null);
  const [googleLinkSuccess, setGoogleLinkSuccess] = useState(false);
  const [googleLinkSaving, setGoogleLinkSaving] = useState(false);
  const overviewQuery = useQuery({
    queryKey: ["settings-security", "overview", session.hotelId],
    queryFn: () => getSecurityOverview(session),
    enabled,
    staleTime: 15 * 1000
  });
  const eventsQuery = useQuery({
    queryKey: ["settings-security", "events", session.hotelId],
    queryFn: () => getSecurityEvents(20, session),
    enabled,
    staleTime: 15 * 1000
  });
  const revokeMutation = useGuardedMutation({
    mutationFn: () => revokeAllSessions(session),
    onSuccess: () => {
      logout();
      navigate("/login?sessions=revoked", { replace: true });
    }
  });

  const handleRevokeAll = async () => {
    const confirmed = window.confirm(
      "¿Cerrar todas tus sesiones? Tendrás que volver a iniciar sesión en este y en los demás dispositivos."
    );
    if (!confirmed) return;
    try {
      await revokeMutation.mutateAsync();
    } catch {
      // The mutation state renders the safe backend error below.
    }
  };

  const handleGoogleConfirmation = (idToken: string) => {
    googleIdTokenRef.current = idToken;
    setPasswordError(null);
    setPasswordSuccess(false);
    setShowPasswordForm(true);
  };

  const handleGoogleLinkConfirmation = (idToken: string) => {
    googleLinkIdTokenRef.current = idToken;
    setGoogleLinkError(null);
    setGoogleLinkSuccess(false);
    setShowGoogleLinkForm(true);
  };

  const handleSetPassword = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPasswordError(null);
    if (password.length < 12) {
      setPasswordError("La contraseña debe tener al menos 12 caracteres.");
      return;
    }
    if (password !== passwordConfirm) {
      setPasswordError("Las contraseñas no coinciden.");
      return;
    }
    const idToken = googleIdTokenRef.current;
    if (!idToken) {
      setPasswordError("Volvé a confirmar tu identidad con Google.");
      setShowPasswordForm(false);
      return;
    }
    setPasswordSaving(true);
    try {
      await setPasswordWithGoogle(idToken, password);
      googleIdTokenRef.current = null;
      setPassword("");
      setPasswordConfirm("");
      setPasswordSuccess(true);
      setShowPasswordForm(false);
      await userQuery.refetch();
    } catch (err) {
      googleIdTokenRef.current = null;
      setShowPasswordForm(false);
      setPasswordError((err as Error).message || "No se pudo crear la contraseña. Confirmá tu identidad con Google e intentá de nuevo.");
    } finally {
      setPasswordSaving(false);
    }
  };

  const handleLinkGoogle = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setGoogleLinkError(null);
    const idToken = googleLinkIdTokenRef.current;
    if (!idToken) {
      setGoogleLinkError("Volvé a confirmar tu identidad con Google.");
      setShowGoogleLinkForm(false);
      return;
    }
    if (!googleLinkPassword) {
      setGoogleLinkError("Ingresá tu contraseña actual de Hotels-PMS.");
      return;
    }
    setGoogleLinkSaving(true);
    try {
      await linkGoogle(idToken, googleLinkPassword);
      googleLinkIdTokenRef.current = null;
      setGoogleLinkPassword("");
      setGoogleLinkSuccess(true);
      setShowGoogleLinkForm(false);
      await userQuery.refetch();
    } catch (err) {
      googleLinkIdTokenRef.current = null;
      setShowGoogleLinkForm(false);
      setGoogleLinkPassword("");
      setGoogleLinkError((err as Error).message || "No se pudo vincular Google. Confirmá tus datos e intentá de nuevo.");
    } finally {
      setGoogleLinkSaving(false);
    }
  };

  const overview = overviewQuery.data;
  const events = eventsQuery.data?.events ?? [];

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Configuración</p>
        <h1 className="text-balance text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">Seguridad</h1>
        <p className="text-sm text-slate-600">Resumen de acceso, eventos recientes y control de tus sesiones.</p>
      </header>

      {(overviewQuery.isError || eventsQuery.isError) && (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          No se pudo cargar todo el estado de seguridad.
          <button
            type="button"
            onClick={() => {
              void overviewQuery.refetch();
              void eventsQuery.refetch();
            }}
            className="ml-2 font-semibold underline"
          >
            Reintentar
          </button>
        </div>
      )}

      {overviewQuery.isLoading ? (
        <p className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500 shadow-sm" role="status">
          Cargando resumen de seguridad...
        </p>
      ) : overview ? (
        <>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5" aria-label="Resumen de seguridad">
            <SecurityMetric label="Miembros activos" value={overview.active_members} />
            <SecurityMetric label="Invitaciones pendientes" value={overview.pending_invitations} />
            <SecurityMetric label="Eventos en 24 h" value={overview.security_events_24h} />
            <SecurityMetric label="Permisos denegados en 24 h" value={overview.permission_denials_24h} />
            <SecurityMetric label="Timeout de sesión" value={`${overview.session_timeout_minutes} min`} />
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Tu acceso</p>
                <h2 className="text-lg font-semibold text-slate-900">{overview.current_user.email}</h2>
                <p className="text-sm text-slate-600">
                  Rol {overview.current_user.role} · versión de sesión {overview.current_user.token_version}
                </p>
                <p className="text-xs text-slate-500">
                  Último ingreso: {overview.current_user.last_login ? new Date(overview.current_user.last_login).toLocaleString("es-AR") : "sin registro"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void handleRevokeAll()}
                disabled={revokeMutation.isPending}
                className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-800 hover:bg-rose-100 disabled:opacity-60"
                data-testid="security-revoke-all"
              >
                {revokeMutation.isPending ? "Cerrando sesiones..." : "Cerrar todas mis sesiones"}
              </button>
            </div>
            {userQuery.isError && (
              <p role="alert" className="mt-3 text-sm text-rose-700">No se pudo verificar si tu cuenta tiene una contraseña configurada.</p>
            )}
            {userQuery.data?.password_login_enabled === false && !passwordSuccess && (
              <div className="mt-4 rounded-lg border border-brand-100 bg-brand-50 p-4">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">Agregá una contraseña de Hotels-PMS</h3>
                  <p className="mt-1 text-sm text-slate-700">Esta cuenta no tiene habilitado el ingreso con contraseña. Podés seguir usando Google y elegir una contraseña nueva acá; no es la contraseña de Google.</p>
                </div>
                {!showPasswordForm ? (
                  <div className="mt-3">
                    <GoogleSignInButton onCredential={handleGoogleConfirmation} />
                    <p className="mt-2 text-center text-xs text-slate-500">Confirmá con la misma cuenta de Google vinculada a este usuario.</p>
                  </div>
                ) : (
                  <form className="mt-4 space-y-3" onSubmit={handleSetPassword}>
                    <PasswordInput
                      id="security-new-password"
                      value={password}
                      onChange={setPassword}
                      placeholder="Mínimo 12 caracteres"
                      required
                      autoComplete="new-password"
                    />
                    <label htmlFor="security-new-password-confirm" className="block text-sm font-medium text-slate-700">
                      Confirmar contraseña
                      <input
                        id="security-new-password-confirm"
                        type="password"
                        autoComplete="new-password"
                        minLength={12}
                        required
                        value={passwordConfirm}
                        onChange={(event) => setPasswordConfirm(event.target.value)}
                        className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                        placeholder="Repetí tu contraseña"
                      />
                    </label>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="submit"
                        disabled={passwordSaving || password.length < 12 || password !== passwordConfirm}
                        className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                      >
                        {passwordSaving ? "Guardando..." : "Crear contraseña"}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          googleIdTokenRef.current = null;
                          setShowPasswordForm(false);
                          setPassword("");
                          setPasswordConfirm("");
                        }}
                        disabled={passwordSaving}
                        className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                      >
                        Cancelar
                      </button>
                    </div>
                  </form>
                )}
                {passwordError && <p className="mt-3 text-sm text-rose-700" role="alert">{passwordError}</p>}
              </div>
            )}
            {userQuery.data?.password_login_enabled === true && userQuery.data.google_login_enabled === false && (
              <div className="mt-4 rounded-lg border border-brand-100 bg-brand-50 p-4" data-testid="google-link-card">
                <h3 className="text-sm font-semibold text-slate-900">Vinculá Google a esta cuenta</h3>
                <p className="mt-1 text-sm text-slate-700">
                  Confirmá tu cuenta de Google y tu contraseña actual de Hotels-PMS. La contraseña no se reemplaza: después vas a poder entrar de las dos formas.
                </p>
                {!showGoogleLinkForm ? (
                  <div className="mt-3">
                    <GoogleSignInButton onCredential={handleGoogleLinkConfirmation} />
                    <p className="mt-2 text-center text-xs text-slate-500">Usá el mismo email que figura en esta cuenta.</p>
                    {googleLinkError && <p className="mt-3 text-sm text-rose-700" role="alert">{googleLinkError}</p>}
                  </div>
                ) : (
                  <form className="mt-4 space-y-3" onSubmit={handleLinkGoogle}>
                    <label htmlFor="google-link-password" className="block text-sm font-medium text-slate-700">
                      Contraseña actual de Hotels-PMS
                      <PasswordInput
                        id="google-link-password"
                        value={googleLinkPassword}
                        onChange={setGoogleLinkPassword}
                        placeholder="Tu contraseña actual"
                        required
                        autoComplete="current-password"
                      />
                    </label>
                    {googleLinkError && <p className="text-sm text-rose-700" role="alert">{googleLinkError}</p>}
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="submit"
                        disabled={googleLinkSaving || !googleLinkPassword}
                        className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                        data-testid="google-link-submit"
                      >
                        {googleLinkSaving ? "Vinculando..." : "Vincular Google"}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          googleLinkIdTokenRef.current = null;
                          setShowGoogleLinkForm(false);
                          setGoogleLinkPassword("");
                          setGoogleLinkError(null);
                        }}
                        disabled={googleLinkSaving}
                        className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                      >
                        Cancelar
                      </button>
                    </div>
                  </form>
                )}
              </div>
            )}
            {userQuery.data?.password_login_enabled === true && userQuery.data.google_login_enabled === true && (
              <p className="mt-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800" role="status">
                Esta cuenta permite ingresar con Google o con tu contraseña de Hotels-PMS.
              </p>
            )}
            {googleLinkSuccess && (
              <p className="mt-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800" role="status">
                Google quedó vinculado. Tu contraseña de Hotels-PMS sigue activa.
              </p>
            )}
            {passwordSuccess && (
              <p className="mt-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800" role="status">
                Contraseña creada. Ya podés ingresar con Google o con email y contraseña.
              </p>
            )}
            {revokeMutation.isError && (
              <p role="alert" className="mt-3 text-sm text-rose-700">No se pudieron cerrar las sesiones. Reintentá.</p>
            )}
          </section>
        </>
      ) : null}

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Auditoría</p>
            <h2 className="text-lg font-semibold text-slate-900">Eventos recientes</h2>
          </div>
          {eventsQuery.isFetching && <span className="text-xs text-slate-500">Actualizando...</span>}
        </div>
        {events.length ? (
          <ul className="mt-4 divide-y divide-slate-200" data-testid="security-events">
            {events.map((event) => (
              <li key={event.id} className="grid gap-1 py-3 text-sm sm:grid-cols-[minmax(0,1fr)_auto]">
                <div>
                  <p className="font-semibold capitalize text-slate-900">{formatEventAction(event.action)}</p>
                  <p className="text-xs text-slate-500">
                    {event.resource_type || "seguridad"}
                    {event.resource_id !== null && event.resource_id !== undefined ? ` #${event.resource_id}` : ""}
                    {event.actor_user_id ? ` · actor #${event.actor_user_id}` : ""}
                  </p>
                </div>
                <time className="text-xs text-slate-500" dateTime={event.created_at}>
                  {new Date(event.created_at).toLocaleString("es-AR")}
                </time>
              </li>
            ))}
          </ul>
        ) : !eventsQuery.isLoading ? (
          <p className="mt-4 text-sm text-slate-500">No hay eventos recientes para mostrar.</p>
        ) : (
          <p className="mt-4 text-sm text-slate-500" role="status">Cargando eventos...</p>
        )}
      </section>
    </div>
  );
}

function SecurityMetric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}
