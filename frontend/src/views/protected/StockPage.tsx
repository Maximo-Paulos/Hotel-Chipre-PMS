import { useMemo, useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createStockItem,
  createStockLocation,
  createStockMovement,
  getCurrentStock,
  listLowStockItems,
  listStockItems,
  listStockLocations,
  type StockMovementCreate,
  type StockMovementType
} from "../../api/stock";
import { hasValidSession } from "../../api/client";
import { useSession } from "../../state/session";

const movementLabel: Record<StockMovementType, string> = {
  in: "Ingreso",
  out: "Egreso",
  adjustment: "Ajuste"
};

const emptyItemForm = {
  name: "",
  sku: "",
  unit: "unidad",
  min_quantity: "",
  active: true
};

const emptyLocationForm = {
  name: ""
};

const emptyMovementForm = {
  item_id: "",
  location_id: "",
  movement_type: "in" as StockMovementType,
  quantity: "1",
  reason: "",
  reservation_id: ""
};

export function StockPage() {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const [itemForm, setItemForm] = useState(emptyItemForm);
  const [locationForm, setLocationForm] = useState(emptyLocationForm);
  const [movementForm, setMovementForm] = useState(emptyMovementForm);
  const [message, setMessage] = useState<string | null>(null);
  const enabled = hasValidSession(session);

  const itemsQuery = useQuery({
    queryKey: ["stock-items", session.hotelId],
    queryFn: () => listStockItems(session),
    enabled,
    staleTime: 30 * 1000
  });
  const locationsQuery = useQuery({
    queryKey: ["stock-locations", session.hotelId],
    queryFn: () => listStockLocations(session),
    enabled,
    staleTime: 60 * 1000
  });
  const lowStockQuery = useQuery({
    queryKey: ["stock-low", session.hotelId],
    queryFn: () => listLowStockItems(session),
    enabled,
    staleTime: 30 * 1000
  });

  const items = useMemo(() => itemsQuery.data ?? [], [itemsQuery.data]);
  const locations = useMemo(() => locationsQuery.data ?? [], [locationsQuery.data]);
  const lowStock = useMemo(() => lowStockQuery.data ?? [], [lowStockQuery.data]);

  const stockQueries = useQueries({
    queries: items.map((item) => ({
      queryKey: ["stock-current", session.hotelId, item.id],
      queryFn: () => getCurrentStock(item.id, session),
      enabled,
      staleTime: 15 * 1000
    }))
  });

  const currentByItemId = useMemo(() => {
    const map = new Map<number, string>();
    stockQueries.forEach((query, index) => {
      const item = items[index];
      if (item && query.data) map.set(item.id, String(query.data.quantity));
    });
    return map;
  }, [items, stockQueries]);

  const invalidateStock = () => {
    queryClient.invalidateQueries({ queryKey: ["stock-items", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["stock-locations", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["stock-low", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["stock-current", session.hotelId] });
  };

  const createItemMutation = useMutation({
    mutationFn: () =>
      createStockItem(
        {
          name: itemForm.name,
          sku: itemForm.sku || null,
          unit: itemForm.unit,
          min_quantity: itemForm.min_quantity || null,
          active: itemForm.active
        },
        session
      ),
    onSuccess: () => {
      invalidateStock();
      setItemForm(emptyItemForm);
      setMessage("Item de stock creado.");
    }
  });

  const createLocationMutation = useMutation({
    mutationFn: () => createStockLocation({ name: locationForm.name }, session),
    onSuccess: () => {
      invalidateStock();
      setLocationForm(emptyLocationForm);
      setMessage("Ubicacion creada.");
    }
  });

  const createMovementMutation = useMutation({
    mutationFn: (payload: StockMovementCreate) => createStockMovement(payload, session),
    onSuccess: () => {
      invalidateStock();
      setMovementForm(emptyMovementForm);
      setMessage("Movimiento registrado.");
    }
  });

  const handleCreateItem = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    try {
      await createItemMutation.mutateAsync();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo crear el item.");
    }
  };

  const handleCreateLocation = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    try {
      await createLocationMutation.mutateAsync();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo crear la ubicacion.");
    }
  };

  const handleCreateMovement = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    try {
      await createMovementMutation.mutateAsync({
        item_id: Number(movementForm.item_id),
        location_id: movementForm.location_id ? Number(movementForm.location_id) : null,
        movement_type: movementForm.movement_type,
        quantity: movementForm.quantity,
        reason: movementForm.reason || null,
        reservation_id: movementForm.reservation_id ? Number(movementForm.reservation_id) : null
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo registrar el movimiento.");
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operacion</p>
          <h1 className="text-2xl font-semibold text-slate-900">Stock</h1>
          <p className="text-sm text-slate-600">Inventario operativo con movimientos y alertas de bajo stock.</p>
        </div>
        {(itemsQuery.isFetching || lowStockQuery.isFetching) && <p className="text-xs text-slate-500">Actualizando...</p>}
      </header>

      {message ? <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">{message}</div> : null}

      <div className="grid gap-4 sm:grid-cols-3">
        <StatusBadge label="Items" value={items.length} className="bg-slate-100 text-slate-700" />
        <StatusBadge label="Ubicaciones" value={locations.length} className="bg-sky-100 text-sky-800" />
        <StatusBadge label="Bajo stock" value={lowStock.length} className="bg-rose-100 text-rose-800" />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Inventario</p>
            <h2 className="text-lg font-semibold text-slate-900">Items ({items.length})</h2>
            {itemsQuery.error && <p className="text-xs text-rose-700">No se pudo cargar: {(itemsQuery.error as Error).message}</p>}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {items.map((item) => {
              const current = currentByItemId.get(item.id) ?? "...";
              const isLow = lowStock.some((lowItem) => lowItem.id === item.id);
              return (
                <div key={item.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-wide text-slate-500">{item.sku || `Item #${item.id}`}</p>
                      <h3 className="text-base font-semibold text-slate-900">{item.name}</h3>
                      <p className="text-xs text-slate-500">
                        Minimo {item.min_quantity ?? "sin minimo"} {item.unit}
                      </p>
                    </div>
                    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${isLow ? "bg-rose-100 text-rose-800" : "bg-emerald-100 text-emerald-800"}`}>
                      {isLow ? "Bajo" : "OK"}
                    </span>
                  </div>
                  <div className="mt-4 rounded-lg bg-slate-50 px-3 py-2">
                    <p className="text-xs uppercase tracking-wide text-slate-500">Stock actual</p>
                    <p className="text-xl font-semibold text-slate-900">
                      {current} <span className="text-sm font-normal text-slate-500">{item.unit}</span>
                    </p>
                  </div>
                </div>
              );
            })}
            {!itemsQuery.isLoading && items.length === 0 && (
              <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
                No hay items de stock cargados.
              </div>
            )}
          </div>
        </section>

        <aside className="space-y-4">
          <form className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" onSubmit={handleCreateMovement}>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Movimiento</p>
              <h2 className="text-lg font-semibold text-slate-900">Registrar movimiento</h2>
            </div>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Item</span>
              <select
                value={movementForm.item_id}
                onChange={(event) => setMovementForm((current) => ({ ...current, item_id: event.target.value }))}
                required
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              >
                <option value="">Seleccionar</option>
                {items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Ubicacion</span>
              <select
                value={movementForm.location_id}
                onChange={(event) => setMovementForm((current) => ({ ...current, location_id: event.target.value }))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              >
                <option value="">Sin ubicacion</option>
                {locations.map((location) => (
                  <option key={location.id} value={location.id}>
                    {location.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Tipo</span>
                <select
                  value={movementForm.movement_type}
                  onChange={(event) =>
                    setMovementForm((current) => ({ ...current, movement_type: event.target.value as StockMovementType }))
                  }
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                >
                  <option value="in">Ingreso</option>
                  <option value="out">Egreso</option>
                  <option value="adjustment">Ajuste</option>
                </select>
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Cantidad</span>
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={movementForm.quantity}
                  onChange={(event) => setMovementForm((current) => ({ ...current, quantity: event.target.value }))}
                  required
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
            </div>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Motivo</span>
              <input
                value={movementForm.reason}
                onChange={(event) => setMovementForm((current) => ({ ...current, reason: event.target.value }))}
                placeholder="Compra, consumo, ajuste mensual"
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Reserva</span>
              <input
                type="number"
                min={1}
                value={movementForm.reservation_id}
                onChange={(event) => setMovementForm((current) => ({ ...current, reservation_id: event.target.value }))}
                placeholder="Opcional"
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              />
            </label>
            <button
              type="submit"
              disabled={createMovementMutation.isPending}
              className="w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              Registrar {movementLabel[movementForm.movement_type]}
            </button>
          </form>

          <form className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" onSubmit={handleCreateItem}>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Nuevo item</p>
              <h2 className="text-lg font-semibold text-slate-900">Alta de stock</h2>
            </div>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Nombre</span>
              <input
                value={itemForm.name}
                onChange={(event) => setItemForm((current) => ({ ...current, name: event.target.value }))}
                required
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">SKU</span>
                <input
                  value={itemForm.sku}
                  onChange={(event) => setItemForm((current) => ({ ...current, sku: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Unidad</span>
                <input
                  value={itemForm.unit}
                  onChange={(event) => setItemForm((current) => ({ ...current, unit: event.target.value }))}
                  required
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
            </div>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Minimo</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={itemForm.min_quantity}
                onChange={(event) => setItemForm((current) => ({ ...current, min_quantity: event.target.value }))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              />
            </label>
            <button
              type="submit"
              disabled={createItemMutation.isPending}
              className="w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              Crear item
            </button>
          </form>

          <form className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" onSubmit={handleCreateLocation}>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Ubicaciones</p>
              <h2 className="text-lg font-semibold text-slate-900">Nueva ubicacion</h2>
            </div>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Nombre</span>
              <input
                value={locationForm.name}
                onChange={(event) => setLocationForm({ name: event.target.value })}
                required
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              />
            </label>
            <button
              type="submit"
              disabled={createLocationMutation.isPending}
              className="w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              Crear ubicacion
            </button>
          </form>
        </aside>
      </div>
    </div>
  );
}

function StatusBadge({ label, value, className }: { label: string; value: number; className: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">{label}</p>
        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${className}`}>{value}</span>
      </div>
    </div>
  );
}
