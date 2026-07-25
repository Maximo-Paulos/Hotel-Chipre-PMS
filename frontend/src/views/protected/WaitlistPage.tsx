import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { listGuests } from "../../api/guests";
import { listRoomCategories, listRooms } from "../../api/rooms";
import {
  cancelWaitlistEntry,
  createWaitlistEntry,
  listWaitlistEntries,
  promoteWaitlistEntry,
  type WaitlistEntryCreate,
  type WaitlistStatus
} from "../../api/waitlist";
import { hasValidSession } from "../../api/client";
import { useSession } from "../../state/session";

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
  const [promoteRoomId, setPromoteRoomId] = useState("");
  const [promoteNotes, setPromoteNotes] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const enabled = hasValidSession(session);

  const waitlistQuery = useQuery({
    queryKey: ["waitlist", session.hotelId, statusFilter],
    queryFn: () => listWaitlistEntries(statusFilter, session),
    enabled,
    staleTime: 30 * 1000
  });
  const guestsQuery = useQuery({
    queryKey: ["guests", session.hotelId, "", "picker"],
    // A5: this feeds a guest picker, not the paginated GuestsPage list --
    // ask for a larger page than the 50 default so the dropdown isn't
    // silently missing hotels with >50 guests.
    queryFn: () => listGuests({ limit: 200 }, session),
    enabled,
    staleTime: 60 * 1000
  });
  const categoriesQuery = useQuery({
    queryKey: ["room-categories", session.hotelId],
    queryFn: () => listRoomCategories(session),
    enabled,
    staleTime: 60 * 1000
  });
  const roomsQuery = useQuery({
    queryKey: ["rooms", session.hotelId],
    queryFn: () => listRooms(session),
    enabled,
    staleTime: 15 * 1000
  });

  const invalidateWaitlist = () => {
    queryClient.invalidateQueries({ queryKey: ["waitlist", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["reservations", session.hotelId] });
  };

  const createMutation = useMutation({
    mutationFn: (payload: WaitlistEntryCreate) => createWaitlistEntry(payload, session),
    onSuccess: () => {
      invalidateWaitlist();
      setFormValues(emptyForm);
      setMessage("Entrada agregada a la lista de espera.");
    }
  });

  const promoteMutation = useMutation({
    mutationFn: ({ entryId, roomId, notes }: { entryId: number; roomId?: number | null; notes?: string | null }) =>
      promoteWaitlistEntry(entryId, { room_id: roomId, notes }, session),
    onSuccess: () => {
      invalidateWaitlist();
      setSelectedEntryId(null);
      setPromoteRoomId("");
      setPromoteNotes("");
      setMessage("Entrada promovida a reserva.");
    }
  });

  const cancelMutation = useMutation({
    mutationFn: (entryId: number) => cancelWaitlistEntry(entryId, session),
    onSuccess: () => {
      invalidateWaitlist();
      setMessage("Entrada cancelada.");
    }
  });

  const entries = useMemo(() => waitlistQuery.data ?? [], [waitlistQuery.data]);
  const guests = useMemo(() => guestsQuery.data ?? [], [guestsQuery.data]);
  const categories = useMemo(() => categoriesQuery.data ?? [], [categoriesQuery.data]);
  const rooms = useMemo(() => roomsQuery.data ?? [], [roomsQuery.data]);
  const guestsById = useMemo(() => new Map(guests.map((guest) => [guest.id, guest])), [guests]);
  const categoriesById = useMemo(() => new Map(categories.map((category) => [category.id, category])), [categories]);

  const selectedEntry = entries.find((entry) => entry.id === selectedEntryId) ?? null;
  const eligibleRooms = selectedEntry
    ? rooms.filter((room) => room.category_id === selectedEntry.category_id && room.is_active)
    : rooms;

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
    if (!selectedEntryId) return;
    setMessage(null);
    try {
      await promoteMutation.mutateAsync({
        entryId: selectedEntryId,
        roomId: promoteRoomId ? Number(promoteRoomId) : null,
        notes: promoteNotes || null
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo promover la entrada.");
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operacion</p>
          <h1 className="text-2xl font-semibold text-slate-900">Lista de espera</h1>
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

          <div className="mt-4 space-y-3">
            {entries.map((entry) => {
              const guest = guestsById.get(entry.guest_id);
              const category = categoriesById.get(entry.category_id);
              const isSelected = selectedEntryId === entry.id;
              return (
                <div key={entry.id} className={`rounded-xl border p-4 shadow-sm ${isSelected ? "border-brand-200 bg-brand-50" : "border-slate-200 bg-white"}`}>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-wide text-slate-500">Prioridad {entry.priority}</p>
                      <h3 className="text-base font-semibold text-slate-900">
                        {guest ? `${guest.first_name} ${guest.last_name}` : `Huesped #${entry.guest_id}`}
                      </h3>
                      <p className="text-xs text-slate-500">
                        {category?.name || `Categoria ${entry.category_id}`} - {entry.check_in_date} a {entry.check_out_date}
                      </p>
                    </div>
                    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${waitlistStatusColors[entry.status]}`}>
                      {waitlistStatusLabel[entry.status]}
                    </span>
                  </div>
                  <p className="mt-3 text-sm text-slate-700">{entry.notes || "Sin notas operativas."}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {entry.status === "waiting" ? (
                      <>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedEntryId(entry.id);
                            setPromoteRoomId("");
                            setPromoteNotes(entry.notes ?? "");
                          }}
                          className="rounded-lg border border-brand-200 bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700"
                        >
                          Promover
                        </button>
                        <button
                          type="button"
                          onClick={() => cancelMutation.mutate(entry.id)}
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
          </div>
        </section>

        <aside className="space-y-4">
          <form className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" onSubmit={handleSubmit}>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Nueva entrada</p>
              <h2 className="text-lg font-semibold text-slate-900">Agregar espera</h2>
            </div>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Huesped</span>
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
              <span className="text-slate-600">Categoria</span>
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
              <span className="text-slate-600">Telefono</span>
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
              disabled={createMutation.isPending}
              className="w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              Agregar a espera
            </button>
          </form>

          <form className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" onSubmit={handlePromote}>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Promocion</p>
              <h2 className="text-lg font-semibold text-slate-900">Crear reserva</h2>
              <p className="text-xs text-slate-500">{selectedEntry ? `Entrada #${selectedEntry.id}` : "Selecciona una entrada en espera."}</p>
            </div>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Habitacion</span>
              <select
                value={promoteRoomId}
                onChange={(event) => setPromoteRoomId(event.target.value)}
                disabled={!selectedEntry}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 disabled:bg-slate-50"
              >
                <option value="">Sin asignar</option>
                {eligibleRooms.map((room) => (
                  <option key={room.id} value={room.id}>
                    Hab. {room.room_number} - {room.status}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Notas de reserva</span>
              <textarea
                value={promoteNotes}
                onChange={(event) => setPromoteNotes(event.target.value)}
                rows={3}
                disabled={!selectedEntry}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 disabled:bg-slate-50"
              />
            </label>
            <button
              type="submit"
              disabled={!selectedEntry || promoteMutation.isPending}
              className="w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              Promover a reserva
            </button>
          </form>
        </aside>
      </div>
    </div>
  );
}
