import { useMemo, useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createStockItem,
  createStockLocation,
  createStockMovement,
  getCurrentStock,
  listLowStockItems,
  listStockMovements,
  listStockItems,
  listStockLocations,
  type StockMovement,
  type StockMovementCreate,
  type StockMovementType
} from "../../api/stock";
import { listReservations, type Reservation } from "../../api/reservations";
import { hasValidSession } from "../../api/client";
import { useSession } from "../../state/session";

// Used for the movement-mode buttons/heading, where "Ajuste" covers both
// directions (the direction toggle underneath clarifies which one).
const movementLabel: Record<StockMovementType, string> = {
  in: "Ingreso",
  out: "Egreso",
  adjustment: "Ajuste",
  adjustment_out: "Ajuste"
};

// Used for the movement history, where each row must show the recorded
// direction so an audit reviewer can tell an increase from a decrease.
const movementHistoryLabel: Record<StockMovementType, string> = {
  in: "Ingreso",
  out: "Egreso",
  adjustment: "Ajuste (alta)",
  adjustment_out: "Ajuste (baja)"
};

const movementModeOptions: Array<{ type: StockMovementType; title: string; description: string }> = [
  { type: "in", title: "Ingreso", description: "Compra, reposición o devolución" },
  { type: "out", title: "Egreso", description: "Consumo, merma o entrega" },
  { type: "adjustment", title: "Ajuste", description: "Corrección autorizada de inventario" }
];

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
  // PERMISSION_STOCK_ADJUST is owner/co_owner only (see
  // _ensure_adjustment_permission in app/api/stock.py); manager only has
  // PERMISSION_STOCK_OPERATE (in/out movements).
  const canAdjustStock = ["owner", "co_owner"].includes(session.role ?? "");
  const availableMovementModeOptions = useMemo(
    () => (canAdjustStock ? movementModeOptions : movementModeOptions.filter((option) => option.type !== "adjustment")),
    [canAdjustStock]
  );
  const queryClient = useQueryClient();
  const [itemForm, setItemForm] = useState(emptyItemForm);
  const [locationForm, setLocationForm] = useState(emptyLocationForm);
  const [movementForm, setMovementForm] = useState(emptyMovementForm);
  const [adjustmentDirection, setAdjustmentDirection] = useState<"increase" | "decrease">("increase");
  const [reservationSearch, setReservationSearch] = useState("");
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
  const reservationsQuery = useQuery({
    queryKey: ["stock-reservations", session.hotelId],
    queryFn: () => listReservations({ status: "all" }, session),
    enabled,
    staleTime: 15 * 1000
  });

  const items = useMemo(() => itemsQuery.data ?? [], [itemsQuery.data]);
  const locations = useMemo(() => locationsQuery.data ?? [], [locationsQuery.data]);
  const lowStock = useMemo(() => lowStockQuery.data ?? [], [lowStockQuery.data]);
  const reservations = useMemo(() => reservationsQuery.data ?? [], [reservationsQuery.data]);

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

  const selectedItem = useMemo(
    () => items.find((item) => String(item.id) === movementForm.item_id),
    [items, movementForm.item_id]
  );
  const selectedCurrentStock = selectedItem ? currentByItemId.get(selectedItem.id) : null;
  const historyItemId = movementForm.item_id ? Number(movementForm.item_id) : undefined;
  const movementHistoryQuery = useQuery({
    queryKey: ["stock-movements", session.hotelId, historyItemId],
    queryFn: () => listStockMovements({ itemId: historyItemId }, session),
    enabled,
    staleTime: 15 * 1000
  });
  const movementHistory = useMemo(() => movementHistoryQuery.data ?? [], [movementHistoryQuery.data]);
  const itemById = useMemo(() => new Map(items.map((item) => [item.id, item])), [items]);
  const locationById = useMemo(() => new Map(locations.map((location) => [location.id, location])), [locations]);
  const reservationById = useMemo(() => new Map(reservations.map((reservation) => [reservation.id, reservation])), [reservations]);
  const requestedQuantity = Number(movementForm.quantity);
  const currentQuantity = selectedCurrentStock ? Number(selectedCurrentStock) : null;
  // "Ajuste" (adjustment) is bidirectional: an owner correcting a physical
  // count can find more units (increase, sent as "adjustment") or fewer
  // (decrease, sent as "adjustment_out"). Both need the same negative-stock
  // guard as a regular "Egreso".
  const isDecreasingMovement =
    movementForm.movement_type === "out" ||
    (movementForm.movement_type === "adjustment" && adjustmentDirection === "decrease");
  const apiMovementType: StockMovementType =
    movementForm.movement_type === "adjustment" && adjustmentDirection === "decrease"
      ? "adjustment_out"
      : movementForm.movement_type;
  const willGoNegative =
    isDecreasingMovement &&
    currentQuantity !== null &&
    Number.isFinite(currentQuantity) &&
    Number.isFinite(requestedQuantity) &&
    requestedQuantity > currentQuantity;
  const projectedQuantity =
    currentQuantity !== null && Number.isFinite(currentQuantity) && Number.isFinite(requestedQuantity)
      ? isDecreasingMovement
        ? currentQuantity - requestedQuantity
        : currentQuantity + requestedQuantity
      : null;
  const filteredReservations = useMemo(() => {
    const search = reservationSearch.trim().toLocaleLowerCase();
    const activeReservations = reservations.filter((reservation) => reservation.status !== "cancelled");
    if (!search) return activeReservations.slice(0, 30);
    return activeReservations
      .filter((reservation) => reservationSearchText(reservation).includes(search))
      .slice(0, 30);
  }, [reservationSearch, reservations]);

  const selectMovement = (itemId: number, movementType: StockMovementType) => {
    setMovementForm((currentForm) => ({ ...currentForm, item_id: String(itemId), movement_type: movementType }));
    setAdjustmentDirection("increase");
    document.getElementById("stock-movement-form")?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const invalidateStock = () => {
    queryClient.invalidateQueries({ queryKey: ["stock-items", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["stock-locations", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["stock-low", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["stock-current", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["stock-movements", session.hotelId] });
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
      setMovementForm((current) => ({
        ...emptyMovementForm,
        item_id: current.item_id,
        location_id: current.location_id,
        movement_type: current.movement_type
      }));
      setAdjustmentDirection("increase");
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
        movement_type: apiMovementType,
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
                    <div className="min-w-0">
                      <p className="text-xs uppercase tracking-wide text-slate-500">{item.sku || `Item #${item.id}`}</p>
                      <h3 className="break-words text-base font-semibold text-slate-900">{item.name}</h3>
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
                  <div className="mt-3 flex gap-2">
                    <button
                      type="button"
                      className="min-h-11 flex-1 rounded-lg border border-brand-200 px-3 py-2 text-xs font-semibold text-brand-700 hover:bg-brand-50"
                      onClick={() => selectMovement(item.id, "in")}
                      aria-label={`Registrar ingreso de ${item.name}`}
                    >
                      Registrar ingreso
                    </button>
                    <button
                      type="button"
                      aria-label={`Registrar egreso de ${item.name}`}
                      className="min-h-11 flex-1 rounded-lg border border-rose-200 px-3 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-50"
                      onClick={() => selectMovement(item.id, "out")}
                    >
                      Registrar egreso
                    </button>
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
          <form id="stock-movement-form" className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" onSubmit={handleCreateMovement}>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Movimiento</p>
              <h2 className="text-lg font-semibold text-slate-900">Registrar {movementLabel[movementForm.movement_type]}</h2>
              <p className="mt-1 text-xs text-slate-500">Elegí una acción, revisá el resultado previsto y confirmá con un motivo.</p>
            </div>
            <div className="grid gap-2" role="group" aria-label="Acción de inventario">
              {availableMovementModeOptions.map((option) => {
                const selected = movementForm.movement_type === option.type;
                return (
                  <button
                    key={option.type}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => {
                      setMovementForm((current) => ({ ...current, movement_type: option.type }));
                      setAdjustmentDirection("increase");
                    }}
                    className={`min-h-11 rounded-lg border px-3 py-2 text-left text-sm ${
                      selected ? "border-brand-300 bg-brand-50 text-brand-800" : "border-slate-200 bg-white text-slate-700"
                    }`}
                  >
                    <span className="block font-semibold">{option.title}</span>
                    <span className="block text-xs text-slate-500">{option.description}</span>
                  </button>
                );
              })}
            </div>
            {movementForm.movement_type === "adjustment" && (
              <div className="grid grid-cols-2 gap-2" role="group" aria-label="Sentido del ajuste">
                <button
                  type="button"
                  aria-pressed={adjustmentDirection === "increase"}
                  onClick={() => setAdjustmentDirection("increase")}
                  className={`min-h-11 rounded-lg border px-3 py-2 text-xs font-semibold ${
                    adjustmentDirection === "increase"
                      ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                      : "border-slate-200 bg-white text-slate-700"
                  }`}
                >
                  Encontré más stock
                </button>
                <button
                  type="button"
                  aria-pressed={adjustmentDirection === "decrease"}
                  onClick={() => setAdjustmentDirection("decrease")}
                  className={`min-h-11 rounded-lg border px-3 py-2 text-xs font-semibold ${
                    adjustmentDirection === "decrease"
                      ? "border-rose-300 bg-rose-50 text-rose-800"
                      : "border-slate-200 bg-white text-slate-700"
                  }`}
                >
                  Encontré menos stock
                </button>
              </div>
            )}
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
            {selectedItem && (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                <span className="text-slate-500">Stock actual: </span>
                <span className="font-semibold text-slate-900">
                  {selectedCurrentStock ?? "..."} {selectedItem.unit}
                </span>
                {willGoNegative && (
                  <p className="mt-1 text-xs font-medium text-rose-700" role="alert">
                    Este movimiento dejará el stock en negativo. Verificá la cantidad antes de confirmar.
                  </p>
                )}
                {projectedQuantity !== null && !willGoNegative && (
                  <p className="mt-1 text-xs text-slate-600">
                    Resultado previsto: <span className="font-semibold">{projectedQuantity.toFixed(2)} {selectedItem.unit}</span>
                  </p>
                )}
              </div>
            )}
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
            <div>
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
                required
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="space-y-1 text-sm">
              <span className="text-slate-600">Reserva asociada (opcional)</span>
              <input
                value={reservationSearch}
                onChange={(event) => setReservationSearch(event.target.value)}
                placeholder="Buscar huésped o código"
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              />
              <select
                value={movementForm.reservation_id}
                onChange={(event) => setMovementForm((current) => ({ ...current, reservation_id: event.target.value }))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              >
                <option value="">Sin reserva asociada</option>
                {filteredReservations.map((reservation) => (
                  <option key={reservation.id} value={reservation.id}>
                    {reservationLabel(reservation)}
                  </option>
                ))}
              </select>
              {reservationsQuery.isFetching && <span className="text-xs text-slate-500">Buscando reservas...</span>}
            </label>
            <button
              type="submit"
              disabled={createMovementMutation.isPending || willGoNegative}
              className="w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              Registrar {movementLabel[movementForm.movement_type]}
            </button>
          </form>

          <StockMovementHistory
            movements={movementHistory}
            isLoading={movementHistoryQuery.isLoading}
            selectedItem={selectedItem?.name}
            itemById={itemById}
            locationById={locationById}
            reservationById={reservationById}
          />

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

function reservationSearchText(reservation: Reservation) {
  return `${reservation.confirmation_code} ${reservation.guest?.first_name ?? ""} ${reservation.guest?.last_name ?? ""}`.toLocaleLowerCase();
}

function reservationLabel(reservation: Reservation) {
  const guestName = reservation.guest ? `${reservation.guest.first_name} ${reservation.guest.last_name}`.trim() : "Huésped sin nombre";
  return `${reservation.confirmation_code} · ${guestName} · ${reservation.check_in_date}`;
}

function StockMovementHistory({
  movements,
  isLoading,
  selectedItem,
  itemById,
  locationById,
  reservationById
}: {
  movements: StockMovement[];
  isLoading: boolean;
  selectedItem?: string;
  itemById: Map<number, { name: string; unit: string }>;
  locationById: Map<number, { name: string }>;
  reservationById: Map<number, Reservation>;
}) {
  return (
    <section aria-labelledby="stock-history-title" className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div>
        <p className="text-xs uppercase tracking-wide text-slate-500">Auditoría operativa</p>
        <h2 id="stock-history-title" className="text-lg font-semibold text-slate-900">Historial reciente</h2>
        <p className="mt-1 text-xs text-slate-500">
          {selectedItem ? `Movimientos de ${selectedItem}.` : "Seleccioná un item para filtrar sus movimientos."}
        </p>
      </div>
      {isLoading ? <p className="text-sm text-slate-500">Cargando movimientos...</p> : null}
      {!isLoading && movements.length === 0 ? <p className="text-sm text-slate-600">Todavía no hay movimientos para mostrar.</p> : null}
      <ul className="space-y-2" aria-label="Historial de movimientos de stock">
        {movements.map((movement) => {
          const item = itemById.get(movement.item_id);
          const location = movement.location_id ? locationById.get(movement.location_id) : undefined;
          const reservation = movement.reservation_id ? reservationById.get(movement.reservation_id) : undefined;
          return (
            <li key={movement.id} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-900">
                    {movementHistoryLabel[movement.movement_type]} · {item?.name ?? "Item eliminado"}
                  </p>
                  <p className="text-xs text-slate-600">
                    {movement.quantity} {item?.unit ?? "unidad"}
                    {location ? ` · ${location.name}` : ""}
                    {reservation ? ` · Reserva ${reservation.confirmation_code}` : ""}
                  </p>
                </div>
                <time className="shrink-0 text-xs text-slate-500" dateTime={movement.created_at}>
                  {new Date(movement.created_at).toLocaleString("es-AR")}
                </time>
              </div>
              {movement.reason ? <p className="mt-1 text-xs text-slate-600">Motivo: {movement.reason}</p> : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
