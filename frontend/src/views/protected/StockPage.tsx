import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";

import {
  createStockItem,
  createStockLocation,
  createStockMovement,
  deleteStockItem,
  getStockConsumptionReport,
  getStockSummary,
  listLowStockItems,
  listStockMovements,
  listStockItems,
  listStockLocations,
  updateStockItem,
  type StockConsumptionGroupBy,
  type StockConsumptionReport,
  type StockItem,
  type StockItemUpdate,
  type StockMovement,
  type StockMovementCreate,
  type StockMovementType
} from "../../api/stock";
import { formatMoney } from "../../utils/currency";
import { listReservations, type Reservation } from "../../api/reservations";
import { hasValidSession } from "../../api/client";
import ConfirmDialog from "../../components/ConfirmDialog";
import { useGuardedMutation } from "../../hooks/useGuardedMutation";
import { useIsDesktopViewport } from "../../hooks/useIsDesktopViewport";
import { useOnlineStatus } from "../../hooks/useOnlineStatus";
import { useSession } from "../../state/session";
import { startOfCurrentMonthIso, startOfCurrentWeekIso, todayIso } from "../../utils/date";

// Mobile task-based tabs (see the useIsDesktopViewport docstring for why this
// is JS state, not a CSS breakpoint split): "movement" and "adjustment" both
// render the SAME <form id="stock-movement-form"> (filtered to a subset of
// availableMovementModeOptions), not two copies -- there is exactly one
// movement form in the DOM at all times, same as desktop always had.
type StockMobileTab = "summary" | "movement" | "adjustment" | "alerts" | "history";
const STOCK_MOBILE_TABS: Array<{ tab: StockMobileTab; label: string }> = [
  { tab: "summary", label: "Resumen" },
  { tab: "movement", label: "Movimiento" },
  { tab: "adjustment", label: "Ajuste" },
  { tab: "alerts", label: "Alertas" },
  { tab: "history", label: "Historial" }
];

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
  const isDesktop = useIsDesktopViewport();
  const isOnline = useOnlineStatus();
  const [mobileTab, setMobileTab] = useState<StockMobileTab>("summary");
  // Desktop keeps every mode (Ingreso/Egreso/Ajuste) in the one form, exactly
  // as before. On mobile, "Movimiento" and "Ajuste" are separate tabs that
  // both render this same form, filtered to their own subset -- see
  // STOCK_MOBILE_TABS docstring.
  const mobileFilteredMovementModeOptions = useMemo(() => {
    if (isDesktop) return availableMovementModeOptions;
    if (mobileTab === "adjustment") return availableMovementModeOptions.filter((option) => option.type === "adjustment");
    return availableMovementModeOptions.filter((option) => option.type !== "adjustment");
  }, [availableMovementModeOptions, isDesktop, mobileTab]);
  const showSection = (tab: StockMobileTab) => isDesktop || mobileTab === tab;
  const movementFormVisible = isDesktop || mobileTab === "movement" || (mobileTab === "adjustment" && canAdjustStock);
  const queryClient = useQueryClient();
  const [itemForm, setItemForm] = useState(emptyItemForm);
  const [locationForm, setLocationForm] = useState(emptyLocationForm);
  const [movementForm, setMovementForm] = useState(emptyMovementForm);
  const [adjustmentDirection, setAdjustmentDirection] = useState<"increase" | "decrease">("increase");
  const [reservationSearch, setReservationSearch] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [itemPendingDelete, setItemPendingDelete] = useState<{ id: number; name: string } | null>(null);
  // Owner: "editar el producto por las dudas" -- unit_cost already has its
  // own inline field (UnitCostField); this covers the rest (name/sku/unit/
  // minimo), which the backend already accepted via PATCH but the UI never
  // exposed. Modal instead of another inline field per card: four fields is
  // too much for a card without cramming it, same tradeoff ManualOtaReservationModal
  // already made for a multi-field form.
  const [itemBeingEdited, setItemBeingEdited] = useState<StockItem | null>(null);
  // D5 (Via D): "cuanto se consumio de cada item" por periodo, con variacion
  // % contra el periodo anterior de igual largo (calculado en el backend).
  const [consumptionGroupBy, setConsumptionGroupBy] = useState<StockConsumptionGroupBy>("week");
  const [consumptionRange, setConsumptionRange] = useState(() => ({ from: startOfCurrentWeekIso(), to: todayIso() }));
  // Mobile "Historial" tab: the backend has no cursor/offset pagination for
  // GET /api/stock/movements (limit only, capped at 200 -- see app/api/stock.py),
  // so "Ver más" just raises the requested limit client-side.
  const [historyLimit, setHistoryLimit] = useState(20);
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

  // Task 5 backend: one request for every item's balance instead of the old
  // per-item useQueries N+1 loop (see StockSummaryEntry docstring).
  const stockSummaryQuery = useQuery({
    queryKey: ["stock-summary", session.hotelId],
    queryFn: () => getStockSummary({}, session),
    enabled,
    staleTime: 15 * 1000
  });

  const items = useMemo(() => itemsQuery.data ?? [], [itemsQuery.data]);
  const locations = useMemo(() => locationsQuery.data ?? [], [locationsQuery.data]);
  const lowStock = useMemo(() => lowStockQuery.data ?? [], [lowStockQuery.data]);
  const reservations = useMemo(() => reservationsQuery.data ?? [], [reservationsQuery.data]);

  const currentByItemId = useMemo(() => {
    const map = new Map<number, string>();
    (stockSummaryQuery.data ?? []).forEach((entry) => map.set(entry.item.id, String(entry.current_quantity)));
    return map;
  }, [stockSummaryQuery.data]);

  const selectedItem = useMemo(
    () => items.find((item) => String(item.id) === movementForm.item_id),
    [items, movementForm.item_id]
  );
  const selectedCurrentStock = selectedItem ? currentByItemId.get(selectedItem.id) : null;
  const historyItemId = movementForm.item_id ? Number(movementForm.item_id) : undefined;
  const movementHistoryQuery = useQuery({
    queryKey: ["stock-movements", session.hotelId, historyItemId, historyLimit],
    queryFn: () => listStockMovements({ itemId: historyItemId, limit: historyLimit }, session),
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
    setMobileTab(movementType === "adjustment" ? "adjustment" : "movement");
    document.getElementById("stock-movement-form")?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const selectMobileTab = (tab: StockMobileTab) => {
    setMobileTab(tab);
    // Keep the shared form's mode in sync with which tab it's rendered
    // under -- otherwise "Ajuste" could show the form still set to "in".
    if (tab === "adjustment" && movementForm.movement_type !== "adjustment") {
      setMovementForm((current) => ({ ...current, movement_type: "adjustment" }));
      setAdjustmentDirection("increase");
    } else if (tab === "movement" && movementForm.movement_type === "adjustment") {
      setMovementForm((current) => ({ ...current, movement_type: "in" }));
    }
  };

  const invalidateStock = () => {
    queryClient.invalidateQueries({ queryKey: ["stock-items", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["stock-locations", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["stock-low", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["stock-summary", session.hotelId] });
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

  const updateItemMutation = useMutation({
    mutationFn: ({ itemId, changes }: { itemId: number; changes: StockItemUpdate }) =>
      updateStockItem(itemId, changes, session),
    onSuccess: () => {
      invalidateStock();
      setItemBeingEdited(null);
      setMessage("Item actualizado.");
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
  // adjustment. useGuardedMutation blocks the double-tap itself; the
  // Idempotency-Key header (Task 5 backend) covers the other case -- a form
  // resubmit after a flaky connection that already reached the server.
  const createMovementMutation = useGuardedMutation({
    mutationFn: ({ payload, idempotencyKey }: { payload: StockMovementCreate; idempotencyKey: string }) =>
      createStockMovement(payload, { idempotencyKey }, session),
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
    if (!isOnline) {
      setMessage("Sin conexión. Conectate para crear el item.");
      return;
    }
    try {
      await createItemMutation.mutateAsync();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo crear el item.");
    }
  };

  const handleCreateLocation = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    if (!isOnline) {
      setMessage("Sin conexión. Conectate para crear la ubicación.");
      return;
    }
    try {
      await createLocationMutation.mutateAsync();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo crear la ubicacion.");
    }
  };

  const handleCreateMovement = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    if (!isOnline) {
      setMessage("Sin conexión. Conectate para registrar el movimiento.");
      return;
    }
    try {
      await createMovementMutation.mutateAsync({
        payload: {
          item_id: Number(movementForm.item_id),
          location_id: movementForm.location_id ? Number(movementForm.location_id) : null,
          movement_type: apiMovementType,
          quantity: movementForm.quantity,
          reason: movementForm.reason || null,
          reservation_id: movementForm.reservation_id ? Number(movementForm.reservation_id) : null
        },
        // One key per submit attempt (not per mutation instance): a retry of
        // this same click reuses it, a brand-new click gets a fresh one.
        idempotencyKey: globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`
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
        {(itemsQuery.isFetching || lowStockQuery.isFetching || stockSummaryQuery.isFetching) && (
          <p className="text-xs text-slate-500">Actualizando...</p>
        )}
      </header>

      {message ? <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">{message}</div> : null}

      {!isOnline && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900" role="status">
          Sin conexión. Podés seguir mirando los datos ya cargados, pero los movimientos y altas se habilitan cuando vuelvas a estar online.
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <StatusBadge label="Items" value={items.length} className="bg-slate-100 text-slate-700" />
        <StatusBadge label="Ubicaciones" value={locations.length} className="bg-sky-100 text-sky-800" />
        <StatusBadge label="Bajo stock" value={lowStock.length} className="bg-rose-100 text-rose-800" />
      </div>

      {/* Mobile task-based tabs -- desktop (md+) ignores mobileTab entirely
          and keeps showing every section at once, same as before this task. */}
      <div className="flex gap-2 overflow-x-auto pb-1 md:hidden" role="tablist" aria-label="Secciones de stock">
        {STOCK_MOBILE_TABS.map(({ tab, label }) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={mobileTab === tab}
            onClick={() => selectMobileTab(tab)}
            className={`min-h-11 shrink-0 rounded-full border px-4 py-2 text-sm font-semibold ${
              mobileTab === tab ? "border-brand-300 bg-brand-50 text-brand-800" : "border-slate-200 bg-white text-slate-600"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {!isDesktop && mobileTab === "alerts" && (
        <StockAlertsPanel lowStock={lowStock} currentByItemId={currentByItemId} onRestock={(itemId) => selectMovement(itemId, "in")} />
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className={showSection("summary") ? "space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" : "hidden"}>
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
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      aria-label={`Editar ${item.name}`}
                      className="min-h-11 flex-1 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                      onClick={() => setItemBeingEdited(item)}
                    >
                      Editar
                    </button>
                    <button
                      type="button"
                      aria-label={`Eliminar ${item.name}`}
                      disabled={deleteItemMutation.isPending}
                      className="min-h-11 flex-1 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-500 hover:bg-slate-50 disabled:opacity-60"
                      onClick={() => setItemPendingDelete({ id: item.id, name: item.name })}
                    >
                      Eliminar
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
          {!isDesktop && mobileTab === "adjustment" && !canAdjustStock && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" role="alert">
              <p className="font-semibold">No tenés permiso para hacer ajustes de stock.</p>
              <p className="mt-1 text-xs">Pedile a un dueño o co-dueño que corrija el conteo, o usá la pestaña "Movimiento" para un ingreso/egreso normal.</p>
            </div>
          )}
          <form
            id="stock-movement-form"
            className={movementFormVisible ? "space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" : "hidden"}
            onSubmit={handleCreateMovement}
          >
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Movimiento</p>
              <h2 className="text-lg font-semibold text-slate-900">Registrar {movementLabel[movementForm.movement_type]}</h2>
              <p className="mt-1 text-xs text-slate-500">Elegí una acción, revisá el resultado previsto y confirmá con un motivo.</p>
            </div>
            <div className="grid gap-2" role="group" aria-label="Acción de inventario">
              {mobileFilteredMovementModeOptions.map((option) => {
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
              disabled={createMovementMutation.isPending || willGoNegative || !isOnline}
              className="w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              Registrar {movementLabel[movementForm.movement_type]}
            </button>
          </form>

          <div className={showSection("history") ? "space-y-3" : "hidden"}>
            <StockMovementHistory
              movements={movementHistory}
              isLoading={movementHistoryQuery.isLoading}
              selectedItem={selectedItem?.name}
              itemById={itemById}
              locationById={locationById}
              reservationById={reservationById}
            />
            {!isDesktop && historyLimit < 200 && movementHistory.length >= historyLimit && (
              <button
                type="button"
                onClick={() => setHistoryLimit((current) => Math.min(200, current + 20))}
                className="min-h-11 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                Ver más movimientos
              </button>
            )}
          </div>

          <form className={showSection("summary") ? "space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" : "hidden"} onSubmit={handleCreateItem}>
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
              disabled={createItemMutation.isPending || !isOnline}
              className="w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              Crear item
            </button>
          </form>

          <form
            className={showSection("summary") ? "space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" : "hidden"}
            onSubmit={handleCreateLocation}
          >
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
              disabled={createLocationMutation.isPending || !isOnline}
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

      <EditStockItemModal
        item={itemBeingEdited}
        saving={updateItemMutation.isPending}
        onSave={(changes) => itemBeingEdited && updateItemMutation.mutate({ itemId: itemBeingEdited.id, changes })}
        onCancel={() => setItemBeingEdited(null)}
      />
    </div>
  );
}

// Owner: "editar el producto por las dudas" -- name/sku/unit/minimo, the
// fields PATCH /api/stock/items/{id} already accepted but no UI ever sent.
// unit_cost keeps its own inline field (UnitCostField) since that is the one
// field owners change often; this modal is for the rest.
function EditStockItemModal({
  item,
  saving,
  onSave,
  onCancel
}: {
  item: StockItem | null;
  saving: boolean;
  onSave: (changes: StockItemUpdate) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState({ name: "", sku: "", unit: "", min_quantity: "" });

  // Re-seed the draft from the item that was just opened -- item identity
  // (id) changes each time "Editar" is clicked on a different card.
  const [openItemId, setOpenItemId] = useState<number | null>(null);
  if (item && item.id !== openItemId) {
    setOpenItemId(item.id);
    setForm({
      name: item.name,
      sku: item.sku ?? "",
      unit: item.unit,
      min_quantity: item.min_quantity != null ? String(item.min_quantity) : ""
    });
  } else if (!item && openItemId !== null) {
    setOpenItemId(null);
  }

  if (!item) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex animate-fade-in items-center justify-center bg-slate-900/40 px-4 py-6"
      onClick={onCancel}
    >
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-stock-item-title"
        className="w-full max-w-sm animate-scale-in rounded-xl border border-slate-200 bg-white p-5 shadow-xl"
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => {
          event.preventDefault();
          onSave({
            name: form.name,
            sku: form.sku || null,
            unit: form.unit,
            min_quantity: form.min_quantity || null
          });
        }}
      >
        <h2 id="edit-stock-item-title" className="text-base font-semibold text-slate-900">
          Editar item de stock
        </h2>
        <div className="mt-4 space-y-3">
          <label className="block text-sm">
            <span className="block text-xs uppercase tracking-wide text-slate-500">Nombre</span>
            <input
              required
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="block text-xs uppercase tracking-wide text-slate-500">SKU</span>
            <input
              value={form.sku}
              onChange={(event) => setForm((current) => ({ ...current, sku: event.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="block text-xs uppercase tracking-wide text-slate-500">Unidad</span>
            <input
              required
              value={form.unit}
              onChange={(event) => setForm((current) => ({ ...current, unit: event.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="block text-xs uppercase tracking-wide text-slate-500">Minimo</span>
            <input
              type="number"
              min="0"
              step="0.01"
              value={form.min_quantity}
              onChange={(event) => setForm((current) => ({ ...current, min_quantity: event.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
        </div>
        <div className="mt-5 flex gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="min-h-11 flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={saving}
            className="min-h-11 flex-1 rounded-lg border border-brand-600 bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
          >
            Guardar
          </button>
        </div>
      </form>
    </div>
  );
}

// Mobile-only "Alertas" tab: only unmounted (not just CSS-hidden) when its
// tab isn't active, so it never shows up in a desktop-viewport DOM at all --
// desktop already shows the same info inline via the "Bajo" badge on each
// item card, this is the mobile equivalent of a dedicated triage list.
function StockAlertsPanel({
  lowStock,
  currentByItemId,
  onRestock
}: {
  lowStock: StockItem[];
  currentByItemId: Map<number, string>;
  onRestock: (itemId: number) => void;
}) {
  return (
    <section aria-labelledby="stock-alerts-title" className="space-y-3 rounded-xl border border-rose-200 bg-rose-50 p-4">
      <div>
        <p className="text-xs uppercase tracking-wide text-rose-700">Alertas</p>
        <h2 id="stock-alerts-title" className="text-lg font-semibold text-rose-900">
          Bajo stock ({lowStock.length})
        </h2>
      </div>
      {lowStock.length === 0 ? (
        <p className="text-sm text-rose-800">Ningún item está por debajo de su mínimo ahora mismo.</p>
      ) : (
        <ul className="space-y-2">
          {lowStock.map((item) => (
            <li key={item.id} className="flex items-center justify-between gap-3 rounded-lg bg-white px-3 py-2 shadow-sm">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-slate-900">{item.name}</p>
                <p className="text-xs text-slate-500">
                  {currentByItemId.get(item.id) ?? "..."} {item.unit} · mínimo {item.min_quantity ?? "sin minimo"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => onRestock(item.id)}
                className="min-h-11 shrink-0 rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700 hover:bg-brand-100"
              >
                Registrar ingreso
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
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
