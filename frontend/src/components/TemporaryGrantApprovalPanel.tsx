import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, hasValidSession } from "../api/client";
import {
  approveTemporaryActionGrant,
  denyTemporaryActionGrant,
  fetchActiveTemporaryActionGrants,
  revokeTemporaryActionGrant
} from "../api/permissions";
import type { AuthUser } from "../api/auth";
import { useGuardedMutation } from "../hooks/useGuardedMutation";
import { useSession } from "../state/session";

type TemporaryGrantApprovalPanelProps = {
  users: AuthUser[];
};

type IssuedToken = {
  grantId: number;
  token: string;
  expiresAt: string | null;
};

const grantsQueryKey = (hotelId: number | null) => ["temporary-action-grants", hotelId] as const;
const errorText = (error: unknown) =>
  error instanceof ApiError ? error.message : error instanceof Error ? error.message : "No se pudo completar la operación.";

const dateTime = (value: string | null) => {
  if (!value) return "Sin fecha";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
};

export default function TemporaryGrantApprovalPanel({ users }: TemporaryGrantApprovalPanelProps) {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const enabled = hasValidSession(session) && (session.baseRole === "owner" || session.baseRole === "co_owner");
  const [totpCode, setTotpCode] = useState("");
  const [issuedToken, setIssuedToken] = useState<IssuedToken | null>(null);
  const [feedback, setFeedback] = useState<{ kind: "status" | "alert"; message: string } | null>(null);

  const grantsQuery = useQuery({
    queryKey: grantsQueryKey(session.hotelId),
    enabled,
    queryFn: () => fetchActiveTemporaryActionGrants(session)
  });
  const userById = useMemo(() => new Map(users.map((user) => [user.id, user])), [users]);

  const approveMutation = useGuardedMutation({
    mutationFn: ({ grantId, code }: { grantId: number; code: string }) =>
      approveTemporaryActionGrant(grantId, code ? { totp_code: code } : {}, session),
    onSuccess: async (result) => {
      setIssuedToken({
        grantId: result.grant.id,
        token: result.token,
        expiresAt: result.grant.expires_at
      });
      setTotpCode("");
      setFeedback({ kind: "status", message: "Autorización aprobada. El código se muestra una sola vez; compartilo manualmente con quien hizo la solicitud." });
      await queryClient.invalidateQueries({ queryKey: grantsQueryKey(session.hotelId) });
    },
    onError: (error) => setFeedback({ kind: "alert", message: errorText(error) })
  });

  const transitionMutation = useGuardedMutation({
    mutationFn: ({ grantId, action }: { grantId: number; action: "deny" | "revoke" }) =>
      action === "deny"
        ? denyTemporaryActionGrant(grantId, session)
        : revokeTemporaryActionGrant(grantId, session),
    onSuccess: async (grant) => {
      if (issuedToken?.grantId === grant.id) setIssuedToken(null);
      setFeedback({ kind: "status", message: grant.status === "denied" ? "Solicitud denegada." : "Autorización revocada." });
      await queryClient.invalidateQueries({ queryKey: grantsQueryKey(session.hotelId) });
    },
    onError: (error) => setFeedback({ kind: "alert", message: errorText(error) })
  });

  const copyToken = async () => {
    if (!issuedToken) return;
    try {
      await navigator.clipboard.writeText(issuedToken.token);
      setFeedback({ kind: "status", message: "Código copiado. Compartilo solo con la persona solicitante." });
    } catch {
      setFeedback({ kind: "alert", message: "No se pudo copiar. Seleccioná el código y copialo manualmente." });
    }
  };

  if (!enabled) return null;

  const grants = grantsQuery.data?.grants ?? [];
  const pending = grants.filter((grant) => grant.status === "pending");
  const approved = grants.filter((grant) => grant.status === "approved");

  return (
    <section className="space-y-4 rounded-xl border border-sky-200 bg-sky-50 p-4" aria-labelledby="temporary-grants-title" data-testid="temporary-grant-approvals">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 id="temporary-grants-title" className="text-base font-semibold text-sky-950">Autorizaciones temporales</h2>
          <p className="mt-1 max-w-3xl text-sm text-sky-900">
            Revisá cada pedido antes de aprobarlo. Hoy solo se permite cancelar una reserva concreta; el código vence a los 15 minutos y se consume una vez. No modifica el rol permanente.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void grantsQuery.refetch()}
          disabled={grantsQuery.isFetching}
          className="min-h-10 shrink-0 rounded-lg border border-sky-300 bg-white px-3 py-2 text-sm font-semibold text-sky-900 hover:bg-sky-100 disabled:opacity-50"
        >
          {grantsQuery.isFetching ? "Actualizando…" : "Actualizar solicitudes"}
        </button>
      </header>

      <div className="rounded-lg border border-sky-200 bg-white p-3 text-xs text-slate-700">
        Si tu cuenta tiene MFA activado, ingresá su código actual antes de aprobar. Si no tiene MFA, dejá el campo vacío.
        <label htmlFor="temporary-grant-totp" className="mt-2 block font-medium text-slate-800">Código MFA (solo si está activo)</label>
        <input
          id="temporary-grant-totp"
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          value={totpCode}
          onChange={(event) => setTotpCode(event.target.value)}
          maxLength={128}
          className="mt-1 min-h-10 w-full max-w-xs rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
          placeholder="Dejar vacío si MFA está desactivado"
        />
      </div>

      {grantsQuery.isLoading ? <p className="text-sm text-slate-700" role="status">Cargando solicitudes…</p> : null}
      {grantsQuery.isError ? <p className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">No se pudieron cargar las autorizaciones. {errorText(grantsQuery.error)}</p> : null}

      {pending.length > 0 ? (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-sky-950">Pendientes ({pending.length})</h3>
          {pending.map((grant) => {
            const requester = userById.get(grant.requester_user_id);
            return (
              <article key={grant.id} className="space-y-3 rounded-lg border border-slate-200 bg-white p-3" data-testid={`temporary-grant-${grant.id}`}>
                <div className="space-y-1 text-sm text-slate-800">
                  <p className="font-semibold">Solicitud #{grant.id} · reserva #{grant.resource_id}</p>
                  <p>Solicitante: {requester?.email ?? `usuario #${grant.requester_user_id}`}</p>
                  <p>Permiso: cancelar esta reserva · enviada {dateTime(grant.created_at)}</p>
                  <p className="rounded-md bg-slate-50 p-2 text-slate-700">Motivo: {grant.reason}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setFeedback(null);
                      void approveMutation.mutateAsync({ grantId: grant.id, code: totpCode.trim() }).catch(() => undefined);
                    }}
                    disabled={approveMutation.isPending || transitionMutation.isPending}
                    className="min-h-10 rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50"
                  >
                    {approveMutation.isPending ? "Aprobando…" : "Aprobar por 15 minutos"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setFeedback(null);
                      void transitionMutation.mutateAsync({ grantId: grant.id, action: "deny" }).catch(() => undefined);
                    }}
                    disabled={approveMutation.isPending || transitionMutation.isPending}
                    className="min-h-10 rounded-lg border border-rose-300 bg-white px-3 py-2 text-sm font-semibold text-rose-800 hover:bg-rose-50 disabled:opacity-50"
                  >
                    Denegar
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      ) : null}

      {approved.length > 0 ? (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-sky-950">Aprobadas y vigentes ({approved.length})</h3>
          {approved.map((grant) => {
            const requester = userById.get(grant.requester_user_id);
            return (
              <article key={grant.id} className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-1 text-sm text-slate-800">
                  <p className="font-semibold">Reserva #{grant.resource_id} · solicitud #{grant.id}</p>
                  <p>Solicitante: {requester?.email ?? `usuario #${grant.requester_user_id}`}</p>
                  <p>Vence: {dateTime(grant.expires_at)}</p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setFeedback(null);
                    void transitionMutation.mutateAsync({ grantId: grant.id, action: "revoke" }).catch(() => undefined);
                  }}
                  disabled={approveMutation.isPending || transitionMutation.isPending}
                  aria-label={`Revocar la autorización temporal para la reserva ${grant.resource_id}`}
                  className="min-h-10 rounded-lg border border-rose-300 bg-white px-3 py-2 text-sm font-semibold text-rose-800 hover:bg-rose-50 disabled:opacity-50"
                >
                  Revocar
                </button>
              </article>
            );
          })}
        </div>
      ) : null}

      {!grantsQuery.isLoading && !grantsQuery.isError && grants.length === 0 ? (
        <p className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-700" role="status">No hay solicitudes pendientes ni autorizaciones vigentes.</p>
      ) : null}

      {issuedToken ? (
        <div className="space-y-2 rounded-lg border border-emerald-300 bg-white p-3" data-testid="temporary-grant-issued-token">
          <h3 className="text-sm font-semibold text-emerald-950">Código de un solo uso · solicitud #{issuedToken.grantId}</h3>
          <p className="text-xs text-emerald-900">Compartilo manualmente con la persona solicitante. El sistema no lo envía por correo ni lo vuelve a mostrar después de salir de esta pantalla.</p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              type="text"
              readOnly
              aria-label="Código temporal aprobado"
              value={issuedToken.token}
              onFocus={(event) => event.currentTarget.select()}
              className="min-h-10 min-w-0 flex-1 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2 font-mono text-sm text-emerald-950"
            />
            <button
              type="button"
              onClick={() => void copyToken()}
              className="min-h-10 rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-800"
            >
              Copiar código
            </button>
          </div>
          <p className="text-xs text-slate-600">Vence: {dateTime(issuedToken.expiresAt)}</p>
        </div>
      ) : null}

      {feedback ? (
        <p
          className={`rounded-md px-3 py-2 text-sm ${feedback.kind === "alert" ? "bg-rose-100 text-rose-800" : "bg-emerald-100 text-emerald-900"}`}
          role={feedback.kind}
          aria-live={feedback.kind === "alert" ? "assertive" : "polite"}
        >
          {feedback.message}
        </p>
      ) : null}
    </section>
  );
}
