import { useMemo, useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";

import {
  createStockItem,
  createStockLocation,
  createStockMovement,
  deleteStockItem,
  getCurrentStock,
  getStockConsumptionReport,
  listLowStockItems,
  listStockMovements,
  listStockItems,
  listStockLocations,
  updateStockItem,
  type StockConsumptionGroupBy,
  type StockConsumptionReport,
  type StockMovement,
  type StockMovementCreate,
  type StockMovementType
} from "../../api/stock";
import { formatMoney } from "../../utils/currency";
import { listReservations, type Reservation } from "../../api/reservations";
import { hasValidSession } from "../../api/client";
import ConfirmDialog from "../../components/ConfirmDialog";
import { useGuardedMutation } from "../../hooks/useGuardedMutation";
import { useSession } from "../../state/session";
import { startOfCurrentMonthIso, startOfCurrentWeekIso, todayIso } from "../../utils/date";

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
  unit_cost: "",
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
  // C4: reads baseRole, not the "Cambiar vista" preview role -- this hides a
  // real inventory-correcting action, so it must reflect the real user.
  const canAdjustStock = ["owner", "co_owner"].includes(session.baseRole ?? "");
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
  const [itemPendingDelete, setItemPendingDelete] = useState<{ id: number; name: string } | null>(null);
  // D5 (Via D): "cuanto se consumio de cada item" por periodo, con variacion
  // % contra el periodo anterior de igual largo (calculado en el backend).
  const [consumptionGroupBy, setConsumptionGroupBy] = useState<StockConsumptionGroupBy>("week");
  const [consumptionRange, setConsumptionRange] = useState(() => ({ from: startOfCurrentWeekIso(), to: todayIso() }));
  const enabled = hasValidSession(session);

  // Stock general (insumos: bolsas, detergentes, jabon) -- ropa blanca de
  // lavanderia vive en su propia tabla/API (linen_items, ver
  // api/linen.ts y LaundryPage.tsx), no aca.
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
    // A2: backend now defaults to limit=50 -- this stock/room mapping used
    // to see every reservation, so ask for the server's max page size
    // explicitly instead of silently losing rows past #50.
    queryFn: () => listReservations({ status: "all", order: "check_in", limit: 200 }, session),
    enabled,
    staleTime: 15 * 1000
  });
  const consumptionReportQuery = useQuery({
    queryKey: ["stock-consumption-report", session.hotelId, consumptionRange.from, consumptionRange.to, consumptionGroupBy],
    queryFn: () =>
      getStockConsumptionReport(
        { dateFrom: consumptionRange.from, dateTo: consumptionRange.to, groupBy: consumptionGroupBy },
        session
      ),
    enabled: enabled && consumptionRange.from <= consumptionRange.to,
    staleTime: 15 * 1000
  });

  const items = useMemo(() => itemsQuery.data ?? [], [itemsQuery.data]);
  const locations = useMemo(() => locationsQuery.data ?? [], [locationsQuery.data]);
  const lowStock = useMemo(() => lowStockQuery.data ?? [], [lowStockQuery.data]);
  const reservations = useMemo(() => reservationsQuery.data ?? [], [reservationsQuery.data]);

  const stockQueries = useQueries({
    queries: items.map((item) => ({
      queryKey: ["stock-current", session.hotelId, item.id],
      queryFn: () => getCurrentStock(item.id, {}, session),
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
    queryClient.invalidateQueries({ queryKey: ["stock-consumption-report", session.hotelId] });
  };

  const createItemMutation = useMutation({
    mutationFn: () =>
      createStockItem(
        {
          name: itemForm.name,
          sku: itemForm.sku || null,
          unit: itemForm.unit,
          min_quantity: itemForm.min_quantity || null,
          unit_cost: itemForm.unit_cost || null,
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

  // Owner: "quiero que se pueda poner en las cosas de stock... el costo por
  // unidad" -- inline edit on each card instead of a separate full item-edit
  // form, since unit_cost is the only field that needs changing after creation.
  const updateItemCostMutation = useMutation({
    mutationFn: ({ itemId, unitCost }: { itemId: number; unitCost: string }) =>
      updateStockItem(itemId, { unit_cost: unitCost || null }, session),
    onSuccess: () => {
      invalidateStock();
      setMessage("Costo por unidad actualizado.");
    }
  });

  const deleteItemMutation = useMutation({
    mutationFn: (itemId: number) => deleteStockItem(itemId, session),
    onSuccess: () => {
      invalidateStock();
      setMessage("Item eliminado.");
    }
  });

  const confirmDeleteItem = async () => {
    if (!itemPendingDelete) return;
    const item = itemPendingDelete;
    setItemPendingDelete(null);
    setMessage(null);
    try {
      await deleteItemMutation.mutateAsync(item.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo eliminar el item.");
    }
  };

  const createLocationMutation = useMutation({
    mutationFn: () => createStockLocation({ name: locationForm.name }, session),
    onSuccess: () => {
      invalidateStock();
      setLocationForm(emptyLocationForm);
      setMessage("Ubicacion creada.");
    }
  });

  // A double-click/double-enter on "Registrar movimiento" before the button
  // re-renders as disabled would otherwise double the recorded stock
  // adjustment (register_movement has no server-side idempotency key).
  const createMovementMutation = useGuardedMutation({
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
                  <div className="mt-4 grid grid-cols-2 gap-2">
                    <div className="rounded-lg bg-slate-50 px-3 py-2">
                      <p className="text-xs uppercase tracking-wide text-slate-500">Stock actual</p>
                      <p className="text-xl font-semibold text-slate-900">
                        {current} <span className="text-sm font-normal text-slate-500">{item.unit}</span>
                      </p>
                    </div>
                    <UnitCostField
                      unitCost={item.unit_cost ?? null}
                      onSave={(unitCost) => updateItemCostMutation.mutate({ itemId: item.id, unitCost })}
                      saving={updateItemCostMutation.isPending}
                    />
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
                  <button
                    type="button"
                    aria-label={`Eliminar ${item.name}`}
                    disabled={deleteItemMutation.isPending}
                    className="mt-2 min-h-11 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-500 hover:bg-slate-50 disabled:opacity-60"
                    onClick={() => setItemPendingDelete({ id: item.id, name: item.name })}
                  >
                    Eliminar
                  </button>
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
            {/* Ubicacion y reserva son opcionales en el backend para el caso comun
                (insumos generales: se compra -> sube, se usa -> baja). Se ocultan
                por default para no pesar como obligatorias; el caso puntual
                (ej: minibar de una habitacion, o vincular a una estadia) sigue
                disponible al abrir "Opciones avanzadas". */}
            <details className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
              <summary className="cursor-pointer text-sm font-medium text-slate-600">Opciones avanzadas</summary>
              <div className="mt-3 space-y-4">
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
              </div>
            </details>
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
            <div className="grid grid-cols-2 gap-3">
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
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Costo por unidad</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={itemForm.unit_cost}
                  onChange={(event) => setItemForm((current) => ({ ...current, unit_cost: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
            </div>
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

      <StockConsumptionReportSection
        range={consumptionRange}
        onRangeChange={setConsumptionRange}
        groupBy={consumptionGroupBy}
        onGroupByChange={setConsumptionGroupBy}
        query={consumptionReportQuery}
      />

      <ConfirmDialog
        open={itemPendingDelete !== null}
        title="Eliminar item de stock"
        message={
          itemPendingDelete
            ? `¿Eliminar "${itemPendingDelete.name}" del inventario? Esta acción no se puede deshacer.`
            : ""
        }
        confirmLabel="Eliminar"
        onConfirm={confirmDeleteItem}
        onCancel={() => setItemPendingDelete(null)}
      />
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

// Owner: "quiero que se pueda poner en las cosas de stock... el costo por
// unidad" -- shown next to "Stock actual" on each card, editable inline
// (click to open a small input) instead of a full separate edit form.
function UnitCostField({
  unitCost,
  onSave,
  saving
}: {
  unitCost: string | number | null;
  onSave: (unitCost: string) => void;
  saving: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(unitCost !== null ? String(unitCost) : "");

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => {
          setDraft(unitCost !== null ? String(unitCost) : "");
          setEditing(true);
        }}
        className="rounded-lg bg-slate-50 px-3 py-2 text-left hover:bg-slate-100"
      >
        <p className="text-xs uppercase tracking-wide text-slate-500">Costo por unidad</p>
        <p className="text-xl font-semibold text-slate-900">
          {unitCost !== null ? formatMoney(unitCost) : <span className="text-sm font-normal text-slate-400">Sin costo</span>}
        </p>
      </button>
    );
  }

  return (
    <form
      className="rounded-lg bg-slate-50 px-3 py-2"
      onSubmit={(event) => {
        event.preventDefault();
        onSave(draft);
        setEditing(false);
      }}
    >
      <label className="block text-xs uppercase tracking-wide text-slate-500" htmlFor="unit-cost-draft">
        Costo por unidad
      </label>
      <div className="mt-1 flex items-center gap-1">
        <input
          id="unit-cost-draft"
          type="number"
          min="0"
          step="0.01"
          autoFocus
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          className="w-full rounded-lg border border-slate-300 px-2 py-1 text-sm"
        />
        <button
          type="submit"
          disabled={saving}
          className="min-h-8 shrink-0 rounded-lg border border-brand-200 bg-brand-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60"
        >
          OK
        </button>
      </div>
    </form>
  );
}

// D5 (Via D): equivalente para stock del "15% ocupacion, $500.000 hoy" del
// dashboard -- cuanto se consumio de cada item en el periodo, comparado
// contra el periodo anterior de igual largo (variacion % calculada en el
// backend) para detectar consumo anomalo. Reusa el patron visual del panel
// de gasto de lavadero (D3, LaundryPage.tsx): mismos presets de rango y
// mismo layout de tarjeta/seccion, cambiando la tabla por-item.
function StockConsumptionReportSection({
  range,
  onRangeChange,
  groupBy,
  onGroupByChange,
  query
}: {
  range: { from: string; to: string };
  onRangeChange: (range: { from: string; to: string }) => void;
  groupBy: StockConsumptionGroupBy;
  onGroupByChange: (groupBy: StockConsumptionGroupBy) => void;
  query: UseQueryResult<StockConsumptionReport>;
}) {
  const report = query.data;
  const items = report?.items ?? [];

  return (
    <section
      aria-labelledby="stock-consumption-title"
      className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Reporte</p>
          <h2 id="stock-consumption-title" className="text-lg font-semibold text-slate-900">
            Consumo de stock por periodo
          </h2>
          <p className="text-sm text-slate-600">
            Egresos y ajustes de baja por item en el rango elegido, comparados contra el periodo anterior de igual
            largo.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <button
            type="button"
            onClick={() => {
              onGroupByChange("week");
              onRangeChange({ from: startOfCurrentWeekIso(), to: todayIso() });
            }}
            className={`min-h-11 rounded-lg border px-3 py-1.5 text-xs font-semibold hover:bg-slate-50 ${
              groupBy === "week" ? "border-brand-300 bg-brand-50 text-brand-700" : "border-slate-200 bg-white text-slate-700"
            }`}
          >
            Semana actual
          </button>
          <button
            type="button"
            onClick={() => {
              onGroupByChange("month");
              onRangeChange({ from: startOfCurrentMonthIso(), to: todayIso() });
            }}
            className={`min-h-11 rounded-lg border px-3 py-1.5 text-xs font-semibold hover:bg-slate-50 ${
              groupBy === "month" ? "border-brand-300 bg-brand-50 text-brand-700" : "border-slate-200 bg-white text-slate-700"
            }`}
          >
            Mes actual
          </button>
          <label className="space-y-1 text-sm">
            <span className="text-slate-600">Desde</span>
            <input
              type="date"
              value={range.from}
              max={range.to}
              onChange={(event) => onRangeChange({ ...range, from: event.target.value })}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-slate-600">Hasta</span>
            <input
              type="date"
              value={range.to}
              min={range.from}
              onChange={(event) => onRangeChange({ ...range, to: event.target.value })}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
        </div>
      </div>

      {query.isFetching && <p className="text-xs text-slate-500">Actualizando...</p>}
      {query.isError && (
        <p className="text-xs text-rose-700">No se pudo cargar el reporte de consumo. Revisa el rango elegido.</p>
      )}
      {report && (
        <p className="text-xs text-slate-500">
          Periodo anterior comparado: {report.previous_date_from} a {report.previous_date_to}
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="px-3 py-2">Item</th>
              <th className="px-3 py-2">Este periodo</th>
              <th className="px-3 py-2">Periodo anterior</th>
              <th className="px-3 py-2">Variacion</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map((item) => (
              <tr key={item.stock_item_id}>
                <td className="px-3 py-2 font-semibold text-slate-900">{item.stock_item_name}</td>
                <td className="px-3 py-2 text-slate-700">
                  {item.current_quantity} {item.unit}
                </td>
                <td className="px-3 py-2 text-slate-500">
                  {item.previous_quantity} {item.unit}
                </td>
                <td className={`px-3 py-2 font-semibold ${variationColor(item.variation_pct)}`}>
                  {formatVariation(item.variation_pct)}
                </td>
              </tr>
            ))}
            {items.length === 0 && !query.isLoading && (
              <tr>
                <td colSpan={4} className="px-3 py-3 text-xs text-slate-500">
                  Sin consumo registrado en este periodo.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function formatVariation(value?: string | number | null) {
  if (value === null || value === undefined) return "Sin dato anterior";
  const number = Number(value);
  const sign = number > 0 ? "+" : "";
  return `${sign}${number}%`;
}

function variationColor(value?: string | number | null) {
  if (value === null || value === undefined) return "text-slate-500";
  const number = Number(value);
  if (number > 0) return "text-rose-700";
  if (number < 0) return "text-emerald-700";
  return "text-slate-700";
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
