import { useState, type FormEvent } from "react";

import { ApiError } from "../api/client";
import { requestTemporaryActionGrant } from "../api/permissions";
import { useGuardedMutation } from "../hooks/useGuardedMutation";
import { useSession } from "../state/session";

type TemporaryCancelPermissionRequestProps = {
  reservationId: number;
  isCancelling: boolean;
  limitationMessage?: string | null;
  onCancelWithToken: (token: string) => Promise<boolean>;
};

const errorText = (error: unknown) =>
  error instanceof ApiError ? error.message : error instanceof Error ? error.message : "No se pudo completar la solicitud.";

export default function TemporaryCancelPermissionRequest({
  reservationId,
  isCancelling,
  limitationMessage,
  onCancelWithToken
}: TemporaryCancelPermissionRequestProps) {
  const { session } = useSession();
  const [reason, setReason] = useState("");
  const [grantId, setGrantId] = useState<number | null>(null);
  const [token, setToken] = useState("");
  const [feedback, setFeedback] = useState<{ kind: "status" | "alert"; message: string } | null>(null);

  const requestMutation = useGuardedMutation({
    mutationFn: () => requestTemporaryActionGrant({
      permission_code: "reservation:cancel",
      resource_type: "reservation",
      resource_id: reservationId,
      reason: reason.trim()
    }, session),
    onSuccess: (grant) => {
      setGrantId(grant.id);
      setFeedback({ kind: "status", message: "Solicitud enviada. El owner o co-owner debe revisarla en Configuración → Permisos." });
    },
    onError: (error) => setFeedback({ kind: "alert", message: errorText(error) })
  });

  const submitRequest = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFeedback(null);
    void requestMutation.mutateAsync().catch(() => undefined);
  };

  const submitCancellation = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalizedToken = token.trim();
    if (!normalizedToken) {
      setFeedback({ kind: "alert", message: "Pegá el código de un solo uso aprobado por el owner o co-owner." });
      return;
    }
    setFeedback(null);
    if (await onCancelWithToken(normalizedToken)) {
      setToken("");
      setFeedback({ kind: "status", message: "La cancelación se completó y el código de un solo uso quedó consumido." });
    }
  };

  return (
    <section className="mt-3 space-y-3 rounded-lg border border-amber-200 bg-amber-50 p-3" aria-labelledby="temporary-cancel-title">
      <div>
        <h3 id="temporary-cancel-title" className="text-sm font-semibold text-amber-950">Autorización temporal para cancelar</h3>
        <p className="mt-1 text-xs text-amber-900">
          Esta solicitud es solo para la reserva #{reservationId}. Si se aprueba, el código sirve una vez durante 15 minutos y no cambia tu rol.
        </p>
        {limitationMessage ? <p className="mt-2 text-xs text-amber-950">{limitationMessage}</p> : null}
      </div>

      {grantId === null ? (
        <form className="space-y-2" onSubmit={submitRequest}>
          <label htmlFor={`temporary-cancel-reason-${reservationId}`} className="block text-xs font-medium text-slate-800">
            Motivo de la solicitud
          </label>
          <textarea
            id={`temporary-cancel-reason-${reservationId}`}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            maxLength={2000}
            rows={2}
            required
            className="min-h-20 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
            placeholder="Explicá brevemente por qué necesitás cancelar esta reserva."
          />
          <button
            type="submit"
            disabled={!reason.trim() || requestMutation.isPending}
            className="min-h-10 rounded-lg bg-amber-800 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-900 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {requestMutation.isPending ? "Enviando solicitud…" : "Solicitar autorización"}
          </button>
        </form>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-amber-950" role="status">
            Solicitud #{grantId} enviada. Coordiná la aprobación con el owner o co-owner; la pantalla no envía correos.
          </p>
          <form className="space-y-2" onSubmit={(event) => void submitCancellation(event)}>
            <label htmlFor={`temporary-cancel-token-${reservationId}`} className="block text-xs font-medium text-slate-800">
              Código aprobado de un solo uso
            </label>
            <input
              id={`temporary-cancel-token-${reservationId}`}
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={token}
              onChange={(event) => setToken(event.target.value)}
              maxLength={512}
              className="min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
              placeholder="Pegá aquí el código que te compartió el owner"
            />
            <button
              type="submit"
              disabled={!token.trim() || isCancelling}
              className="min-h-10 rounded-lg border border-rose-300 bg-white px-3 py-2 text-sm font-semibold text-rose-800 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isCancelling ? "Cancelando…" : "Cancelar con autorización"}
            </button>
          </form>
        </div>
      )}

      {feedback ? (
        <p
          className={`rounded-md px-3 py-2 text-xs ${feedback.kind === "alert" ? "bg-rose-100 text-rose-800" : "bg-emerald-100 text-emerald-900"}`}
          role={feedback.kind}
          aria-live={feedback.kind === "alert" ? "assertive" : "polite"}
        >
          {feedback.message}
        </p>
      ) : null}
    </section>
  );
}
