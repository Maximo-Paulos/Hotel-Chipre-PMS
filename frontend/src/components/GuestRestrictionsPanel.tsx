import { useState, type FormEvent } from "react";

import { useGuestActiveRestrictions, useGuestRestrictionMutations } from "../hooks/useGuestRestrictions";
import { useEffectivePermissions } from "../hooks/usePermissions";

type Props = {
  guestId: number;
};

const emptyCreateForm = { reason: "", detail: "" };

// Create/resolve UI for the formal GuestRestriction entity (distinct from
// the legacy "prohibido_alojar" GuestTag). Only rendered for actors with
// guest:prohibition_manage -- guest:prohibition_read alone only sees the
// GuestRestrictionBadge indicator, never reason/detail or these actions.
export function GuestRestrictionsPanel({ guestId }: Props) {
  const { hasPermission } = useEffectivePermissions();
  const canManage = hasPermission("guest:prohibition_manage");
  const restrictionsQuery = useGuestActiveRestrictions(guestId, true);
  const { createMutation, resolveMutation } = useGuestRestrictionMutations(guestId);
  const [createForm, setCreateForm] = useState(emptyCreateForm);
  const [message, setMessage] = useState<string | null>(null);
  const [resolvingId, setResolvingId] = useState<number | null>(null);
  const [resolutionNote, setResolutionNote] = useState("");

  if (!canManage) return null;

  const restrictions = restrictionsQuery.data ?? [];

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!createForm.reason.trim()) {
      setMessage("El motivo es obligatorio.");
      return;
    }
    setMessage(null);
    try {
      await createMutation.mutateAsync({
        reason: createForm.reason.trim(),
        detail: createForm.detail.trim() || undefined
      });
      setCreateForm(emptyCreateForm);
      setMessage("Restricción creada.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo crear la restricción.");
    }
  };

  const handleResolve = async (restrictionId: number) => {
    setMessage(null);
    try {
      await resolveMutation.mutateAsync({
        restrictionId,
        payload: { resolution_note: resolutionNote.trim() || undefined }
      });
      setResolvingId(null);
      setResolutionNote("");
      setMessage("Restricción resuelta.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo resolver la restricción.");
    }
  };

  return (
    <section className="space-y-4 border-t border-slate-200 pt-4" data-testid="guest-restrictions-panel">
      <div>
        <p className="text-xs uppercase tracking-wide text-slate-500">Restricciones</p>
        <h3 className="text-base font-semibold text-slate-900">Prohibición de alojamiento</h3>
      </div>

      <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
        {restrictionsQuery.isLoading ? (
          <p className="text-sm text-slate-500">Cargando restricciones...</p>
        ) : restrictions.length > 0 ? (
          <div className="space-y-3">
            {restrictions.map((restriction) => (
              <div
                key={restriction.id}
                className="rounded-md bg-white px-3 py-2 text-sm shadow-sm"
                data-testid={`guest-restriction-${restriction.id}`}
              >
                <p className="font-semibold text-red-800">{restriction.reason}</p>
                {restriction.detail ? <p className="text-xs text-slate-600">{restriction.detail}</p> : null}
                <p className="text-xs text-slate-400">
                  Desde {new Date(restriction.created_at).toLocaleDateString("es-AR")}
                  {restriction.valid_until
                    ? ` · Vence ${new Date(restriction.valid_until).toLocaleDateString("es-AR")}`
                    : ""}
                </p>
                {resolvingId === restriction.id ? (
                  <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                    <input
                      value={resolutionNote}
                      onChange={(event) => setResolutionNote(event.target.value)}
                      placeholder="Nota de resolución (opcional)"
                      className="min-h-11 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    />
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => handleResolve(restriction.id)}
                        disabled={resolveMutation.isPending}
                        className="min-h-11 rounded-lg border border-emerald-200 bg-emerald-600 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
                      >
                        Confirmar resolución
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setResolvingId(null);
                          setResolutionNote("");
                        }}
                        className="min-h-11 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                      >
                        Cancelar
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setResolvingId(restriction.id)}
                    data-testid={`guest-restriction-resolve-${restriction.id}`}
                    className="mt-2 min-h-11 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                  >
                    Resolver
                  </button>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">Sin restricciones activas.</p>
        )}
      </div>

      <form className="grid gap-3 sm:grid-cols-2" onSubmit={handleCreate}>
        <label className="space-y-1 text-sm sm:col-span-2">
          <span className="text-slate-600">Motivo (obligatorio)</span>
          <input
            value={createForm.reason}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, reason: event.target.value }))}
            className="w-full min-h-11 rounded-lg border border-slate-300 px-3 py-2"
            data-testid="guest-restriction-reason-input"
          />
        </label>
        <label className="space-y-1 text-sm sm:col-span-2">
          <span className="text-slate-600">Detalle (opcional)</span>
          <textarea
            value={createForm.detail}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, detail: event.target.value }))}
            rows={2}
            className="w-full rounded-lg border border-slate-300 px-3 py-2"
          />
        </label>
        <div className="flex justify-end sm:col-span-2">
          <button
            type="submit"
            disabled={createMutation.isPending}
            data-testid="guest-restriction-create-submit"
            className="min-h-11 rounded-lg border border-red-200 bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-60"
          >
            Crear restricción
          </button>
        </div>
      </form>

      {message ? (
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">{message}</div>
      ) : null}
    </section>
  );
}
