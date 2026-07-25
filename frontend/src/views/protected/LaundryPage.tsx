import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addLaundryItem,
  createLaundryBatch,
  listLaundryBatches,
  updateLaundryStatus,
  type LaundryItemCreate,
  type LaundryStatus
} from "../../api/laundry";
import { listRooms } from "../../api/rooms";
import { hasValidSession } from "../../api/client";
import { useSession } from "../../state/session";

const statusLabel: Record<LaundryStatus, string> = {
  collected: "Recolectado",
  sent: "Enviado",
  received: "Recibido",
  closed: "Cerrado"
};

const statusColor: Record<LaundryStatus, string> = {
  collected: "bg-amber-100 text-amber-800",
  sent: "bg-sky-100 text-sky-800",
  received: "bg-emerald-100 text-emerald-800",
  closed: "bg-slate-200 text-slate-700"
};

const nextStatus: Partial<Record<LaundryStatus, LaundryStatus>> = {
  collected: "sent",
  sent: "received",
  received: "closed"
};

const emptyItemForm = {
  item_type: "",
  quantity: "1",
  room_id: ""
};

export function LaundryPage() {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("");
  const [batchCode, setBatchCode] = useState("");
  const [notes, setNotes] = useState("");
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);
  const [itemForm, setItemForm] = useState(emptyItemForm);
  const [message, setMessage] = useState<string | null>(null);
  const enabled = hasValidSession(session);
  // POST /api/laundry/batches requires owner/co_owner/manager; housekeeping can
  // only list batches, add items and change status on existing ones.
  const canCreateBatch = ["owner", "co_owner", "manager"].includes(session.role ?? "");

  const batchesQuery = useQuery({
    queryKey: ["laundry-batches", session.hotelId, statusFilter, batchCode],
    queryFn: () => listLaundryBatches({ statusFilter, batchCode }, session),
    enabled,
    staleTime: 30 * 1000
  });
  const roomsQuery = useQuery({
    queryKey: ["rooms", session.hotelId],
    queryFn: () => listRooms(session),
    enabled,
    staleTime: 15 * 1000
  });

  const invalidateLaundry = () => {
    queryClient.invalidateQueries({ queryKey: ["laundry-batches", session.hotelId] });
  };

  const createBatchMutation = useMutation({
    mutationFn: () => createLaundryBatch({ notes: notes || null }, session),
    onSuccess: (batch) => {
      invalidateLaundry();
      setNotes("");
      setSelectedBatchId(batch.id);
      setMessage("Lote de lavanderia creado.");
    }
  });

  const addItemMutation = useMutation({
    mutationFn: ({ batchId, payload }: { batchId: number; payload: LaundryItemCreate }) =>
      addLaundryItem(batchId, payload, session),
    onSuccess: () => {
      invalidateLaundry();
      setItemForm(emptyItemForm);
      setMessage("Item agregado al lote.");
    }
  });

  const statusMutation = useMutation({
    mutationFn: ({ batchId, status }: { batchId: number; status: LaundryStatus }) =>
      updateLaundryStatus(batchId, status, session),
    onSuccess: () => {
      invalidateLaundry();
      setMessage("Estado de lavanderia actualizado.");
    }
  });

  const batches = useMemo(() => batchesQuery.data ?? [], [batchesQuery.data]);
  const rooms = useMemo(() => roomsQuery.data ?? [], [roomsQuery.data]);
  const selectedBatch = batches.find((batch) => batch.id === selectedBatchId) ?? batches[0] ?? null;

  const handleAddItem = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedBatch) return;
    setMessage(null);
    try {
      await addItemMutation.mutateAsync({
        batchId: selectedBatch.id,
        payload: {
          item_type: itemForm.item_type,
          quantity: Number(itemForm.quantity || 1),
          room_id: itemForm.room_id ? Number(itemForm.room_id) : null
        }
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo agregar el item.");
    }
  };

  const handleCreateBatch = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    try {
      await createBatchMutation.mutateAsync();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo crear el lote.");
    }
  };

  const transitionBatch = async (batchId: number, status: LaundryStatus) => {
    setMessage(null);
    try {
      await statusMutation.mutateAsync({ batchId, status });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo cambiar el estado.");
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operacion</p>
          <h1 className="text-2xl font-semibold text-slate-900">Lavanderia</h1>
          <p className="text-sm text-slate-600">Control de lotes desde recoleccion hasta cierre operativo.</p>
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          <input
            value={batchCode}
            onChange={(event) => setBatchCode(event.target.value)}
            placeholder="Codigo de lote"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">Todos</option>
            <option value="collected">Recolectado</option>
            <option value="sent">Enviado</option>
            <option value="received">Recibido</option>
            <option value="closed">Cerrado</option>
          </select>
        </div>
      </header>

      {message ? <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">{message}</div> : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Lotes</p>
              <h2 className="text-lg font-semibold text-slate-900">Lavanderia ({batches.length})</h2>
              {batchesQuery.error && <p className="text-xs text-rose-700">No se pudo cargar: {(batchesQuery.error as Error).message}</p>}
            </div>
            {batchesQuery.isFetching && <p className="text-xs text-slate-500">Actualizando...</p>}
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {batches.map((batch) => {
              const next = nextStatus[batch.status];
              return (
                <button
                  key={batch.id}
                  type="button"
                  onClick={() => setSelectedBatchId(batch.id)}
                  className={`rounded-xl border p-4 text-left shadow-sm hover:bg-slate-50 ${
                    selectedBatch?.id === batch.id ? "border-brand-200 bg-brand-50" : "border-slate-200 bg-white"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-wide text-slate-500">{batch.batch_code}</p>
                      <h3 className="text-base font-semibold text-slate-900">{batch.items.length} items</h3>
                      <p className="text-xs text-slate-500">
                        Creado {new Date(batch.created_at).toLocaleString("es-AR")}
                      </p>
                    </div>
                    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusColor[batch.status]}`}>
                      {statusLabel[batch.status]}
                    </span>
                  </div>
                  <p className="mt-3 text-sm text-slate-700">{batch.notes || "Sin notas."}</p>
                  {next ? (
                    <span
                      className="mt-4 inline-flex rounded-lg border border-brand-200 bg-brand-600 px-3 py-2 text-sm font-semibold text-white"
                      onClick={(event) => {
                        event.stopPropagation();
                        transitionBatch(batch.id, next);
                      }}
                    >
                      Marcar {statusLabel[next]}
                    </span>
                  ) : (
                    <span className="mt-4 inline-flex text-xs text-slate-500">Lote cerrado</span>
                  )}
                </button>
              );
            })}
            {!batchesQuery.isLoading && batches.length === 0 && (
              <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
                No hay lotes de lavanderia para el filtro actual.
              </div>
            )}
          </div>
        </section>

        <aside className="space-y-4">
          {canCreateBatch && (
          <form className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" onSubmit={handleCreateBatch}>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Nuevo lote</p>
              <h2 className="text-lg font-semibold text-slate-900">Crear lote</h2>
            </div>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Notas</span>
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                rows={3}
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              />
            </label>
            <button
              type="submit"
              disabled={createBatchMutation.isPending}
              className="w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              Crear lote
            </button>
          </form>
          )}

          <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Detalle</p>
              <h2 className="text-lg font-semibold text-slate-900">
                {selectedBatch ? selectedBatch.batch_code : "Sin lote seleccionado"}
              </h2>
            </div>
            {selectedBatch ? (
              <>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  {selectedBatch.items.length > 0 ? (
                    <div className="space-y-2">
                      {selectedBatch.items.map((item) => (
                        <div key={item.id} className="rounded-md bg-white px-3 py-2 text-sm shadow-sm">
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-semibold text-slate-900">{item.item_type}</p>
                            <span className="text-xs text-slate-500">x{item.quantity}</span>
                          </div>
                          <p className="text-xs text-slate-500">{item.room_id ? `Hab. ${rooms.find((room) => room.id === item.room_id)?.room_number ?? item.room_id}` : "Sin habitacion"}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">Todavia no hay items registrados.</p>
                  )}
                </div>

                <form className="space-y-3" onSubmit={handleAddItem}>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Tipo de item</span>
                    <input
                      value={itemForm.item_type}
                      onChange={(event) => setItemForm((current) => ({ ...current, item_type: event.target.value }))}
                      required
                      placeholder="Sabanas, toallas, acolchados"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Cantidad</span>
                    <input
                      type="number"
                      min={1}
                      value={itemForm.quantity}
                      onChange={(event) => setItemForm((current) => ({ ...current, quantity: event.target.value }))}
                      required
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Habitacion</span>
                    <select
                      value={itemForm.room_id}
                      onChange={(event) => setItemForm((current) => ({ ...current, room_id: event.target.value }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    >
                      <option value="">Sin habitacion</option>
                      {rooms.map((room) => (
                        <option key={room.id} value={room.id}>
                          Hab. {room.room_number}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="submit"
                    disabled={addItemMutation.isPending}
                    className="w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                  >
                    Agregar item
                  </button>
                </form>
              </>
            ) : (
              <p className="text-sm text-slate-500">Selecciona o crea un lote para cargar items.</p>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
