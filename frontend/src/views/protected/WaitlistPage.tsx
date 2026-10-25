import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { listGuests } from "../../api/guests";
import {
  cancelWaitlistEntry,
  createWaitlistEntry,
  getWaitlistPromotionSuggestions,
  listWaitlistEntries,
  promoteWaitlistEntry,
  type WaitlistEntryCreate,
  type WaitlistStatus
} from "../../api/waitlist";
import { ApiError, hasValidSession } from "../../api/client";
import { useSession } from "../../state/session";
import { useRooms } from "../../hooks/useRooms";
import { useEffectivePermissions } from "../../hooks/usePermissions";
import { refreshReservationState } from "../../api/queryInvalidation";
import { useGuardedMutation } from "../../hooks/useGuardedMutation";

const waitlistStatusLabel: Record<WaitlistStatus, string> = {
  waiting: "En espera",
  promoted: "Promovida",
  cancelled: "Cancelada",
  expired: "Vencida"
};

const waitlistStatusColors: Record<WaitlistStatus, string> = {
  waiting: "bg-amber-100 text-amber-800",
  promoted: "bg-emerald-100 text-emerald-800",
  cancelled: "bg-slate-200 text-slate-700",
  expired: "bg-rose-100 text-rose-800"
};

const emptyForm = {
  guest_id: "",
  category_id: "",
  check_in_date: "",
  check_out_date: "",
  num_adults: "1",
  num_children: "0",
  priority: "100",
  contact_phone: "",
  notes: ""
};

export function WaitlistPage() {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("");
  const [formValues, setFormValues] = useState(emptyForm);
  const [selectedEntryId, setSelectedEntryId] = useState<number | null>(null);
  const [promoteNotes, setPromoteNotes] = useState("");
  const [checkingPromotion, setCheckingPromotion] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const enabled = hasValidSession(session);
  const { hasPermission } = useEffectivePermissions();
  const canReadWaitlist = hasPermission("reservation:create") && hasPermission("waitlist:view");
  const canCreateReservation = hasPermission("reservation:create");
  const { categoriesQuery } = useRooms({ includeCategories: true });

  const waitlistQuery = useQuery({
    queryKey: ["waitlist", session.hotelId, statusFilter],
    queryFn: () => listWaitlistEntries(statusFilter, session),
    enabled: enabled && canReadWaitlist,
    staleTime: 30 * 1000
  });
  const suggestionsQuery = useQuery({
    queryKey: ["waitlist", "suggestions", session.hotelId],
    queryFn: () => getWaitlistPromotionSuggestions(session),
    enabled: enabled && canReadWaitlist && (statusFilter === "" || statusFilter === "waiting"),
    staleTime: 0,
    retry: false
  });
  const guestsQuery = useQuery({
    queryKey: ["guests", session.hotelId, "", "picker"],
    // A5: this feeds a guest picker, not the paginated GuestsPage list --
    // ask for a larger page than the 50 default so the dropdown isn't
    // silently missing hotels with >50 guests.
    queryFn: () => listGuests({ limit: 200 }, session),
    enabled: enabled && canCreateReservation,
    staleTime: 60 * 1000
  });

  const invalidateWaitlist = async () => {
    await Promise.all([
      refreshReservationState(queryClient, session.hotelId),
      queryClient.invalidateQueries({ queryKey: ["waitlist", session.hotelId] }),
      queryClient.invalidateQueries({ queryKey: ["waitlist", "suggestions", session.hotelId] })
    ]);
  };

  const createMutation = useGuardedMutation({
    mutationFn: (payload: WaitlistEntryCreate) => createWaitlistEntry(payload, session),
    onSuccess: async () => {
      await invalidateWaitlist();
      setFormValues(emptyForm);
      setMessage("Entrada agregada a la lista de espera.");
    }
  });

  const promoteMutation = useGuardedMutation({
    mutationFn: ({ entryId, roomId, notes, expectedEntryFingerprint }: {
      entryId: number;
      roomId: number;
      notes?: string | null;
      expectedEntryFingerprint: string;
    }) => promoteWaitlistEntry(entryId, {
      room_id: roomId,
      expected_entry_fingerprint: expectedEntryFingerprint,
      notes
    }, session),
    onSuccess: async () => {
      await invalidateWaitlist();
      setSelectedEntryId(null);
      setPromoteNotes("");
      setMessage("Entrada promovida a reserva.");
    }
  });

  const cancelMutation = useGuardedMutation({
    mutationFn: (entryId: number) => cancelWaitlistEntry(entryId, session),
    onSuccess: async () => {
      await invalidateWaitlist();
      setMessage("Entrada cancelada.");
    }
  });

  const entries = useMemo(() => waitlistQuery.data ?? [], [waitlistQuery.data]);
  const guests = useMemo(() => guestsQuery.data ?? [], [guestsQuery.data]);
  const categories = useMemo(() => categoriesQuery.data ?? [], [categoriesQuery.data]);
  const guestsById = useMemo(() => new Map(guests.map((guest) => [guest.id, guest])), [guests]);
  const categoriesById = useMemo(() => new Map(categories.map((category) => [category.id, category])), [categories]);
  const suggestionsByEntryId = useMemo(
    () => new Map((suggestionsQuery.data ?? []).map((suggestion) => [suggestion.entry_id, suggestion])),
    [suggestionsQuery.data]
  );

  const selectedEntry = entries.find((entry) => entry.id === selectedEntryId) ?? null;
  const selectedSuggestion = selectedEntry ? suggestionsByEntryId.get(selectedEntry.id) ?? null : null;
  const selectedSuggestionIsCurrent = Boolean(
    selectedSuggestion
    && selectedSuggestion.expected_entry_fingerprint
    && suggestionsQuery.isSuccess
    && !suggestionsQuery.isFetching
    && !suggestionsQuery.isError
  );

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    try {
      await createMutation.mutateAsync({
        guest_id: Number(formValues.guest_id),
        category_id: Number(formValues.category_id),
        check_in_date: formValues.check_in_date,
        check_out_date: formValues.check_out_date,
        num_adults: Number(formValues.num_adults || 1),
        num_children: Number(formValues.num_children || 0),
        priority: Number(formValues.priority || 100),
        contact_phone: formValues.contact_phone || null,
        notes: formValues.notes || null
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo agregar la entrada.");
    }
  };

  const handlePromote = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedEntryId || !selectedEntry || !selectedSuggestion || !selectedSuggestionIsCurrent || checkingPromotion) return;
    setMessage(null);
    setCheckingPromotion(true);
    try {
      // The operator must confirm the exact room and stay that were shown for
      // review. Recheck both the waitlist entry and the engine suggestion
      // immediately before promotion; availability is still enforced by the
      // server inside the promotion transaction.
      const [currentEntries, refreshedSuggestions] = await Promise.all([
        listWaitlistEntries("waiting", session),
        suggestionsQuery.refetch()
      ]);
      const currentEntry = currentEntries.find((entry) => entry.id === selectedEntryId);
      if (!currentEntry || currentEntry.status !== "waiting") {
        setSelectedEntryId(null);
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ["waitlist", session.hotelId] }),
          queryClient.invalidateQueries({ queryKey: ["waitlist", "suggestions", session.hotelId] })
        ]);
        setMessage("La entrada cambió o ya no está en espera. Actualicé la lista; revisala antes de continuar.");
        return;
      }
      const entryStillMatchesReview = currentEntry.guest_id === selectedEntry.guest_id
        && currentEntry.category_id === selectedEntry.category_id
        && currentEntry.check_in_date === selectedEntry.check_in_date
        && currentEntry.check_out_date === selectedEntry.check_out_date
        && currentEntry.num_adults === selectedEntry.num_adults
        && currentEntry.num_children === selectedEntry.num_children;
      if (!entryStillMatchesReview) {
        setSelectedEntryId(null);
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ["waitlist", session.hotelId] }),
          queryClient.invalidateQueries({ queryKey: ["waitlist", "suggestions", session.hotelId] })
        ]);
        setMessage("Cambió el huésped, la categoría, las fechas o la ocupación solicitada. Seleccioná de nuevo la entrada para revisar la propuesta actualizada.");
        return;
      }
      if (refreshedSuggestions.isError) {
        setMessage("No se pudo actualizar la propuesta del motor. No se creó la reserva; intentá actualizarla otra vez.");
        return;
      }
      const latestSuggestion = refreshedSuggestions.data?.find((suggestion) => suggestion.entry_id === selectedEntryId);
      if (!latestSuggestion) {
        setMessage("El motor ya no devolvió una propuesta para esta entrada. No se creó la reserva; revisá disponibilidad y actualizá la propuesta.");
        return;
      }
      const suggestionStillMatchesReview = latestSuggestion.guest_id === selectedSuggestion.guest_id
        && latestSuggestion.category_id === selectedSuggestion.category_id
        && latestSuggestion.check_in_date === selectedSuggestion.check_in_date
        && latestSuggestion.check_out_date === selectedSuggestion.check_out_date
        && latestSuggestion.suggested_room_id === selectedSuggestion.suggested_room_id
        && latestSuggestion.expected_entry_fingerprint === selectedSuggestion.expected_entry_fingerprint;
      if (!suggestionStillMatchesReview) {
        setMessage(`La propuesta cambió o quedó desactualizada: ahora sugiere la habitación ${latestSuggestion.suggested_room_number}. Revisá la asignación actual y confirmala de nuevo.`);
        return;
      }
      await promoteMutation.mutateAsync({
        entryId: selectedEntryId,
        roomId: latestSuggestion.suggested_room_id,
        expectedEntryFingerprint: latestSuggestion.expected_entry_fingerprint,
        notes: promoteNotes || null
      });
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ["waitlist", session.hotelId] }),
          queryClient.invalidateQueries({ queryKey: ["waitlist", "suggestions", session.hotelId] })
        ]);
        setMessage("La entrada o la propuesta cambió antes de confirmar, o la habitación dejó de estar disponible. No se creó la reserva; actualizá y revisá la propuesta antes de intentar otra vez.");
        return;
      }
      setMessage(error instanceof Error ? error.message : "No se pudo promover la entrada.");
    } finally {
      setCheckingPromotion(false);
    }
  };

  const handleCancel = async (entryId: number) => {
    setMessage(null);
    try {
      await cancelMutation.mutateAsync(entryId);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo cancelar la entrada.");
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
          <h1 className="text-balance text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">Lista de espera</h1>
          <p className="text-sm text-slate-600">Solicitudes pendientes cuando no hay disponibilidad inmediata.</p>
        </div>
        <select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm sm:w-56"
        >
          <option value="">Todos los estados</option>
          <option value="waiting">En espera</option>
          <option value="promoted">Promovidas</option>
          <option value="cancelled">Canceladas</option>
          <option value="expired">Vencidas</option>
        </select>
      </header>

      {message ? <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">{message}</div> : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Solicitudes</p>
              <h2 className="text-lg font-semibold text-slate-900">Entradas ({entries.length})</h2>
              {waitlistQuery.error && <p className="text-xs text-rose-700">No se pudo cargar: {(waitlistQuery.error as Error).message}</p>}
            </div>
            {waitlistQuery.isFetching && <p className="text-xs text-slate-500">Actualizando...</p>}
          </div>
          {suggestionsQuery.isError && (statusFilter === "" || statusFilter === "waiting") && (
            <p role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
              No se pudieron calcular propuestas del motor: {(suggestionsQuery.error as Error).message}
            </p>
          )}

          <div className="mt-4 space-y-3">
            {entries.map((entry) => {
              const guest = guestsById.get(entry.guest_id);
              const category = categoriesById.get(entry.category_id);
              const isSelected = selectedEntryId === entry.id;
              const suggestion = suggestionsByEntryId.get(entry.id);
              return (
                <div key={entry.id} className={`rounded-xl border p-4 shadow-sm ${isSelected ? "border-brand-200 bg-brand-50" : "border-slate-200 bg-white"}`}>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-wide text-slate-500">Prioridad {entry.priority}</p>
                      <h3 className="text-base font-semibold text-slate-900">
                        {guest ? `${guest.first_name} ${guest.last_name}` : `Huésped #${entry.guest_id}`}
                      </h3>
                      <p className="text-xs text-slate-500">
                        {category?.name || "Información no disponible"} - {entry.check_in_date} a {entry.check_out_date}
                      </p>
                    </div>
                    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${waitlistStatusColors[entry.status]}`}>
                      {waitlistStatusLabel[entry.status]}
                    </span>
                  </div>
                  {entry.status === "waiting" && (
                    <div className="mt-3 rounded-lg border border-indigo-100 bg-indigo-50 px-3 py-2 text-sm text-indigo-950">
              {suggestionsQuery.isError ? (
                        <p>La última propuesta no se pudo actualizar. Volvé a calcularla antes de promover esta entrada.</p>
                      ) : suggestionsQuery.isFetching ? (
                        <p>El motor está revisando disponibilidad para estas fechas…</p>
                      ) : suggestion ? (
                        <>
                          <p className="font-semibold">Propuesta del motor: habitación {suggestion.suggested_room_number}</p>
                          <p className="mt-1">{suggestion.reason}</p>
                        </>
                      ) : (
                        <p>El motor no devolvió una propuesta para esta entrada en la consulta actual. Revisá la disponibilidad y volvé a actualizar antes de promoverla.</p>
                      )}
                    </div>
                  )}
                  <p className="mt-3 text-sm text-slate-700">{entry.notes || "Sin notas operativas."}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {entry.status === "waiting" ? (
                      <>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedEntryId(entry.id);
                            setPromoteNotes(entry.notes ?? "");
                          }}
                          disabled={!suggestion || !suggestionsQuery.isSuccess || suggestionsQuery.isFetching || suggestionsQuery.isError}
                          className="rounded-lg border border-brand-200 bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700"
                        >
                          Revisar propuesta
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleCancel(entry.id)}
                          disabled={cancelMutation.isPending}
                          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                        >
                          Cancelar
                        </button>
                      </>
                    ) : (
                      <p className="text-xs text-slate-500">Sin acciones pendientes.</p>
                    )}
                  </div>
                </div>
              );
            })}
            {!waitlistQuery.isLoading && entries.length === 0 && (
              <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
                No hay entradas para el filtro seleccionado.
              </div>
            )}
            {!canReadWaitlist && (
              <div role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                Tu rol necesita los permisos de lista de espera y creación de reservas para consultar propuestas y confirmar una promoción.
              </div>
            )}
          </div>
        </section>

        <aside className="space-y-4">
          <form className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" onSubmit={handleSubmit}>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Nueva entrada</p>
              <h2 className="text-lg font-semibold text-slate-900">Agregar espera</h2>
            </div>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Huésped</span>
              <select
                value={formValues.guest_id}
                onChange={(event) => setFormValues((current) => ({ ...current, guest_id: event.target.value }))}
                required
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              >
                <option value="">Seleccionar</option>
                {guests.map((guest) => (
                  <option key={guest.id} value={guest.id}>
                    {guest.first_name} {guest.last_name}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Categoría</span>
              <select
                value={formValues.category_id}
                onChange={(event) => setFormValues((current) => ({ ...current, category_id: event.target.value }))}
                required
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              >
                <option value="">Seleccionar</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Check-in</span>
                <input
                  type="date"
                  value={formValues.check_in_date}
                  onChange={(event) => setFormValues((current) => ({ ...current, check_in_date: event.target.value }))}
                  required
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Check-out</span>
                <input
                  type="date"
                  value={formValues.check_out_date}
                  onChange={(event) => setFormValues((current) => ({ ...current, check_out_date: event.target.value }))}
                  required
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Adultos</span>
                <input
                  type="number"
                  min={1}
                  value={formValues.num_adults}
                  onChange={(event) => setFormValues((current) => ({ ...current, num_adults: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Menores</span>
                <input
                  type="number"
                  min={0}
                  value={formValues.num_children}
                  onChange={(event) => setFormValues((current) => ({ ...current, num_children: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Prioridad</span>
                <input
                  type="number"
                  min={0}
                  value={formValues.priority}
                  onChange={(event) => setFormValues((current) => ({ ...current, priority: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
            </div>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Teléfono</span>
              <input
                value={formValues.contact_phone}
                onChange={(event) => setFormValues((current) => ({ ...current, contact_phone: event.target.value }))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Notas</span>
              <textarea
                value={formValues.notes}
                onChange={(event) => setFormValues((current) => ({ ...current, notes: event.target.value }))}
                rows={3}
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              />
            </label>
            <button
              type="submit"
              disabled={!canCreateReservation || createMutation.isPending}
              className="w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              Agregar a espera
            </button>
          </form>

          <form className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" onSubmit={handlePromote}>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Promoción</p>
              <h2 className="text-lg font-semibold text-slate-900">Revisar propuesta y confirmar</h2>
              <p className="text-xs text-slate-500">{selectedEntry ? `Entrada #${selectedEntry.id}` : "Selecciona una entrada en espera."}</p>
            </div>
            {selectedEntry && selectedSuggestion && selectedSuggestionIsCurrent ? (
              <div className="space-y-2 rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-950">
                <p className="font-semibold">{selectedSuggestion.guest_name}: habitación {selectedSuggestion.suggested_room_number}</p>
                <p>{selectedSuggestion.check_in_date} a {selectedSuggestion.check_out_date}</p>
                <p>{selectedSuggestion.reason}</p>
                {selectedSuggestion.allocation_basis === "feasibility_only_no_price_snapshot" && (
                  <p className="text-xs">Esta entrada no tiene una tarifa guardada; el motor comprueba disponibilidad y encaje, no compara ingresos.</p>
                )}
                <p className="text-xs font-medium">La propuesta todavía no crea una reserva. Recepción debe confirmarla.</p>
              </div>
            ) : (
              <p role={suggestionsQuery.isError ? "alert" : suggestionsQuery.isFetching ? "status" : undefined} className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
                {selectedEntry && suggestionsQuery.isError
                  ? "La propuesta anterior no se puede confirmar porque no fue posible actualizarla. Volvé a calcular antes de continuar."
                  : selectedEntry && suggestionsQuery.isFetching
                    ? "El motor está actualizando la propuesta. La confirmación queda deshabilitada hasta que termine."
                    : selectedEntry
                  ? "No hay una propuesta válida para esta entrada. Actualizá las propuestas antes de promoverla."
                  : "Seleccioná una entrada que tenga una propuesta válida del motor."}
              </p>
            )}
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Notas de reserva</span>
              <textarea
                value={promoteNotes}
                onChange={(event) => setPromoteNotes(event.target.value)}
                rows={3}
                disabled={!selectedEntry || !selectedSuggestionIsCurrent}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 disabled:bg-slate-50"
              />
            </label>
            <button
              type="submit"
              disabled={!canCreateReservation || !selectedEntry || !selectedSuggestionIsCurrent || checkingPromotion || promoteMutation.isPending}
              className="w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              {checkingPromotion
                ? "Verificando disponibilidad y propuesta…"
                : selectedSuggestionIsCurrent && selectedSuggestion
                ? `Confirmar reserva en Hab. ${selectedSuggestion.suggested_room_number}`
                : suggestionsQuery.isFetching
                  ? "Actualizando propuesta…"
                  : "Sin propuesta válida para confirmar"}
            </button>
            <div className="space-y-2">
              <button
                type="button"
                onClick={() => void suggestionsQuery.refetch()}
                disabled={!canReadWaitlist || suggestionsQuery.isFetching}
                className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
              >
                {suggestionsQuery.isFetching ? "Calculando propuestas…" : "Actualizar propuestas del motor"}
              </button>
              {suggestionsQuery.isError && (
                <p role="alert" className="text-xs text-rose-700">No se pudieron calcular propuestas: {(suggestionsQuery.error as Error).message}</p>
              )}
            </div>
          </form>
        </aside>
      </div>
    </div>
  );
}
