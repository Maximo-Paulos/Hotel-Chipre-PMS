import { useState } from "react";

type Props = {
  phase: "prompting" | "forbidden";
  onSubmit: (reason: string) => void;
  onCancel: () => void;
  isPending?: boolean;
};

// Shown when a reservation create/update or check-in request 409s with
// GUEST_PROHIBITED. "prompting" asks for a mandatory override reason and
// retries the same request with it attached; "forbidden" is the terminal
// state when the retry itself 403s because the actor lacks
// reservation:prohibition_override -- it never leaves the operator stuck on
// a spinner or a silently-failed request.
export function RestrictionOverrideModal({ phase, onSubmit, onCancel, isPending = false }: Props) {
  const [reason, setReason] = useState("");
  const trimmed = reason.trim();

  return (
    <div
      className="fixed inset-0 z-50 flex animate-fade-in items-center justify-center bg-slate-900/40 px-4 py-6"
      onClick={onCancel}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="restriction-override-title"
        className="w-full max-w-sm animate-scale-in rounded-xl border border-slate-200 bg-white p-5 shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        {phase === "prompting" ? (
          <>
            <h2 id="restriction-override-title" className="text-base font-semibold text-slate-900">
              Huésped con restricción activa
            </h2>
            <p className="mt-2 text-sm text-slate-600">
              Este huésped tiene una restricción de alojamiento activa. Para continuar igual, escribí el motivo de la
              excepción. Queda registrado en la auditoría.
            </p>
            <label className="mt-4 block text-sm">
              <span className="block text-xs uppercase tracking-wide text-slate-500">Motivo del override</span>
              <textarea
                autoFocus
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                rows={3}
                data-testid="restriction-override-reason"
                className="mt-1 w-full min-h-[44px] rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
                placeholder="Ej: autorizado por el manager en turno, huésped saldó la deuda anterior"
              />
            </label>
            <div className="mt-4 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                onClick={onCancel}
                className="min-h-11 rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50"
              >
                Cancelar
              </button>
              <button
                type="button"
                data-testid="restriction-override-submit"
                disabled={!trimmed || isPending}
                onClick={() => onSubmit(trimmed)}
                className="min-h-11 rounded-lg border border-red-200 bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Continuar con override
              </button>
            </div>
          </>
        ) : (
          <>
            <h2 id="restriction-override-title" className="text-base font-semibold text-slate-900">
              No tenés permiso para autorizar esta excepción
            </h2>
            <p className="mt-2 text-sm text-slate-600" role="alert">
              El huésped tiene una restricción activa. Pedile a un manager, owner o co-owner que autorice el override,
              o resolvé la restricción desde la ficha del huésped.
            </p>
            <div className="mt-4 flex justify-end">
              <button
                type="button"
                onClick={onCancel}
                className="min-h-11 rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50"
              >
                Entendido
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
