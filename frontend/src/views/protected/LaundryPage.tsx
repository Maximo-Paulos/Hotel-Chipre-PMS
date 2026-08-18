import { useMemo, useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";

import {
  createLaundryRemito,
  createLaundryVendor,
  getLaundryVendorBalance,
  getLaundryVendorSettlements,
  getLaundryVendorSpend,
  listLaundryRemitos,
  listLaundryVendorPrices,
  listLaundryVendors,
  markLaundryVendorSettlementPaid,
  setLaundryVendorPrice,
  updateLaundryVendor,
  type LaundryRemitoLineCreate,
  type LaundryVendor,
  type LaundryVendorSettlementQuarter,
  type RemitoDirection
} from "../../api/laundryVendor";
import {
  createLinenItem,
  createLinenLocation,
  createLinenMovement,
  getLinenSummary,
  listLinenItems,
  listLinenLocations,
  type LinenItem
} from "../../api/linen";
import type { StockMovementType } from "../../api/stock";
import { hasValidSession } from "../../api/client";
import { useGuardedMutation } from "../../hooks/useGuardedMutation";
import { useEffectivePermissions } from "../../hooks/usePermissions";
import { useIsDesktopViewport } from "../../hooks/useIsDesktopViewport";
import { useOnlineStatus } from "../../hooks/useOnlineStatus";
import { useSession } from "../../state/session";
import { formatMoney } from "../../utils/currency";
import { startOfCurrentMonthIso, startOfCurrentWeekIso, todayIso } from "../../utils/date";

// Mobile task-based tabs (see useIsDesktopViewport docstring): "outbound" and
// "inbound" both render the SAME "Nuevo remito" form (direction pre-selected,
// still togglable), not two copies -- desktop keeps showing every section at
// once regardless of mobileTab. "vendors" (lavaderos/precios/catálogo) is
// only offered to users who actually hold laundry:manage_vendors -- mirrors
// the existing (tested, see housekeeping-laundry-journey.spec.ts) desktop
// behavior of never revealing that panel exists to housekeeping at all,
// rather than showing a permission-denied explanation for it.
type LaundryMobileTab = "available" | "outbound" | "inbound" | "vendors" | "history";

// D2 (Via D lavanderia): replaces the old LaundryBatch/LaundryItem UI
// entirely -- D0 confirmed no open batches in production, so there is no
// read-only legacy view to keep around (see memory checkpoint
// 20260726-002247 for the D1 backend this consumes). A remito is a transfer
// between the hotel's own LinenLocation and the vendor's dedicated one, so
// "en el lavadero ahora" and "limpio disponible en el hotel" are both just
// current_stock() narrowed to different location_id values -- see the two
// panels near the bottom of this file.
// D3 (Via D lavanderia): "cuanto le pague al lavadero" range presets, using
// hotel-local (not UTC) dates -- see utils/date.ts (startOfCurrentWeekIso/
// startOfCurrentMonthIso, shared with the D5 stock consumption report).
const dayStartIso = (day: string) => new Date(`${day}T00:00:00`).toISOString();
const dayEndIso = (day: string) => new Date(`${day}T23:59:59.999`).toISOString();

const emptyVendorForm = { name: "", contact_phone: "", contact_email: "" };
const emptyPriceForm = { linen_item_id: "", unit_price: "" };
const emptyLinenItemForm = { name: "", unit: "unidad" };
const emptyLinenLocationForm = { name: "" };
const emptyMovementForm = { linen_item_id: "", location_id: "", movement_type: "in" as StockMovementType, quantity: "1", reason: "" };

type LineDraft = { linen_item_id: number; item_name: string; unit: string; quantity: string };

const emptyRemitoForm = () => ({
  direction: "outbound" as RemitoDirection,
  vendor_id: "",
  house_location_id: "",
  remito_number: "",
  remito_date: todayIso(),
  notes: ""
});

export function LaundryPage() {
  const { session } = useSession();
  const { hasPermission } = useEffectivePermissions();
  const queryClient = useQueryClient();
  const enabled = hasValidSession(session);
  const manageVendors = hasPermission("laundry:manage_vendors");
  const operateRemitos = hasPermission("laundry:operate_remitos");
  const isDesktop = useIsDesktopViewport();
  const isOnline = useOnlineStatus();
  const mobileTabs = useMemo(() => {
    const tabs: Array<{ tab: LaundryMobileTab; label: string }> = [];
    if (operateRemitos) tabs.push({ tab: "available", label: "Disponible" });
    if (operateRemitos) tabs.push({ tab: "outbound", label: "Salida" });
    if (operateRemitos) tabs.push({ tab: "inbound", label: "Retorno" });
    if (manageVendors) tabs.push({ tab: "vendors", label: "Lavaderos" });
    if (operateRemitos) tabs.push({ tab: "history", label: "Historial" });
    return tabs;
  }, [operateRemitos, manageVendors]);
  const [mobileTab, setMobileTab] = useState<LaundryMobileTab>("available");
  const showSection = (tab: LaundryMobileTab) => isDesktop || mobileTab === tab;
  const remitoFormVisible = isDesktop || mobileTab === "outbound" || mobileTab === "inbound";
  const selectMobileTab = (tab: LaundryMobileTab) => {
    setMobileTab(tab);
    if (tab === "outbound" || tab === "inbound") {
      setRemitoForm((current) => (current.direction === tab ? current : { ...current, direction: tab }));
    }
  };

  const [message, setMessage] = useState<string | null>(null);
  const [selectedVendorId, setSelectedVendorId] = useState<number | null>(null);
  const [vendorForm, setVendorForm] = useState(emptyVendorForm);
  const [priceForm, setPriceForm] = useState(emptyPriceForm);
  const [linenItemForm, setLinenItemForm] = useState(emptyLinenItemForm);
  const [linenLocationForm, setLinenLocationForm] = useState(emptyLinenLocationForm);
  const [movementForm, setMovementForm] = useState(emptyMovementForm);
  const [remitoForm, setRemitoForm] = useState(emptyRemitoForm);
  const [lines, setLines] = useState<LineDraft[]>([]);
  const [lineDraft, setLineDraft] = useState({ linen_item_id: "", quantity: "1" });
  const [remitoError, setRemitoError] = useState<string | null>(null);
  const [houseStockLocationId, setHouseStockLocationId] = useState<string>("");
  const [spendRange, setSpendRange] = useState(() => ({ from: startOfCurrentMonthIso(), to: todayIso() }));
  const [settlementYear, setSettlementYear] = useState(() => new Date().getFullYear());

  const vendorsQuery = useQuery({
    queryKey: ["laundry-vendors", session.hotelId],
    queryFn: () => listLaundryVendors(session),
    enabled,
    staleTime: 30 * 1000
  });
  // LaundryPage's own linen_items/linen_locations tables -- physically
  // separate from StockPage's general supplies (see api/linen.ts).
  const itemsQuery = useQuery({
    queryKey: ["linen-items", session.hotelId],
    queryFn: () => listLinenItems(session),
    enabled,
    staleTime: 30 * 1000
  });
  const locationsQuery = useQuery({
    queryKey: ["linen-locations", session.hotelId],
    queryFn: () => listLinenLocations(session),
    enabled,
    staleTime: 60 * 1000
  });
  const remitosQuery = useQuery({
    queryKey: ["laundry-remitos", session.hotelId],
    queryFn: () => listLaundryRemitos({}, session),
    enabled,
    staleTime: 15 * 1000
  });

  const vendors = useMemo(() => vendorsQuery.data ?? [], [vendorsQuery.data]);
  const activeVendors = useMemo(() => vendors.filter((vendor) => vendor.active), [vendors]);
  const items = useMemo(() => itemsQuery.data ?? [], [itemsQuery.data]);
  const locations = useMemo(() => locationsQuery.data ?? [], [locationsQuery.data]);
  const remitos = useMemo(() => remitosQuery.data ?? [], [remitosQuery.data]);
  const itemById = useMemo(() => new Map(items.map((item) => [item.id, item])), [items]);
  const vendorById = useMemo(() => new Map(vendors.map((vendor) => [vendor.id, vendor])), [vendors]);

  // Vendor LinenLocations are administrative (created automatically with the
  // vendor to represent "what's physically at that laundry") -- exclude them
  // from any selector meant to pick a real hotel storage location, so they
  // don't get mixed with places like "Deposito" or "Recepcion".
  const vendorLocationIds = useMemo(() => new Set(vendors.map((vendor) => vendor.linen_location_id)), [vendors]);
  const houseLocations = useMemo(
    () => locations.filter((location) => !vendorLocationIds.has(location.id)),
    [locations, vendorLocationIds]
  );

  const selectedVendor = selectedVendorId ? (vendorById.get(selectedVendorId) ?? null) : null;
  const pricesQuery = useQuery({
    queryKey: ["laundry-vendor-prices", session.hotelId, selectedVendorId],
    queryFn: () => listLaundryVendorPrices(selectedVendorId as number, session),
    enabled: enabled && manageVendors && selectedVendorId !== null,
    staleTime: 15 * 1000
  });
  const selectedVendorPrices = useMemo(() => pricesQuery.data ?? [], [pricesQuery.data]);

  // Liquidacion trimestral: totals are computed live server-side from each
  // remito's frozen unit_price_snapshot (see vendor_settlements), so this
  // never disagrees with the spend report above -- it's the same numbers,
  // grouped by calendar quarter with an owner-only paid/not-paid mark on top.
  const settlementsQuery = useQuery({
    queryKey: ["laundry-vendor-settlements", session.hotelId, selectedVendorId, settlementYear],
    queryFn: () => getLaundryVendorSettlements(selectedVendorId as number, settlementYear, session),
    enabled: enabled && manageVendors && selectedVendorId !== null,
    staleTime: 15 * 1000
  });
  const settlementQuarters = useMemo(() => settlementsQuery.data ?? [], [settlementsQuery.data]);

  // Prices for the vendor picked in the remito form (may differ from
  // selectedVendorId, which drives the admin panel above).
  const remitoVendorId = remitoForm.vendor_id ? Number(remitoForm.vendor_id) : null;
  const remitoVendorPricesQuery = useQuery({
    queryKey: ["laundry-vendor-prices", session.hotelId, remitoVendorId],
    queryFn: () => listLaundryVendorPrices(remitoVendorId as number, session),
    enabled: enabled && manageVendors && remitoVendorId !== null,
    staleTime: 15 * 1000
  });
  const remitoVendorPriceByItem = useMemo(() => {
    const map = new Map<number, { unit_price: string; currency_code: string }>();
    (remitoVendorPricesQuery.data ?? []).forEach((price) =>
      map.set(price.linen_item_id, { unit_price: String(price.unit_price), currency_code: price.currency_code })
    );
    return map;
  }, [remitoVendorPricesQuery.data]);

  const balanceQueries = useQueries({
    queries: vendors.map((vendor) => ({
      queryKey: ["laundry-vendor-balance", session.hotelId, vendor.id],
      queryFn: () => getLaundryVendorBalance(vendor.id, session),
      enabled,
      staleTime: 15 * 1000
    }))
  });

  // Spend report: GET /api/laundry/vendors/{id}/spend is per-vendor only
  // (gated by laundry:manage_vendors, which housekeeping never holds anyway).
  // A hotel realistically has 1-3 laundries (see plan D3), so N small
  // parallel requests summed client-side is simpler than adding and testing
  // a new aggregate backend endpoint for a handful of rows.
  // ponytail: revisit with a real GET /api/laundry/spend-summary if a hotel
  // ever runs enough vendors that N requests becomes noticeable.
  const spendQueries = useQueries({
    queries: vendors.map((vendor) => ({
      queryKey: ["laundry-vendor-spend", session.hotelId, vendor.id, spendRange.from, spendRange.to],
      queryFn: () =>
        getLaundryVendorSpend(
          vendor.id,
          { dateFrom: dayStartIso(spendRange.from), dateTo: dayEndIso(spendRange.to) },
          session
        ),
      enabled: enabled && manageVendors,
      staleTime: 15 * 1000
    }))
  });
  const spendTotal = useMemo(
    () => spendQueries.reduce((sum, query) => sum + Number(query.data?.total ?? 0), 0),
    [spendQueries]
  );
  const spendFetching = spendQueries.some((query) => query.isFetching);

  // Task 5 backend: one request for every linen item's balance instead of
  // the old per-item useQueries N+1 loop (see LinenSummaryEntry docstring).
  // Available to operateRemitos too, not just manageVendors -- the backend
  // endpoint (get_current_laundry_linen_stock / get_laundry_linen_summary)
  // already accepts either permission; the previous `manageVendors &&` gate
  // around this panel hid it from housekeeping unnecessarily.
  const houseStockSummaryQuery = useQuery({
    queryKey: ["linen-summary", session.hotelId, houseStockLocationId || "hotel-wide"],
    queryFn: () =>
      getLinenSummary(houseStockLocationId ? { locationId: Number(houseStockLocationId) } : {}, session),
    enabled: enabled && Boolean(houseStockLocationId),
    staleTime: 15 * 1000
  });
  const houseStockByItemId = useMemo(() => {
    const map = new Map<number, string>();
    (houseStockSummaryQuery.data ?? []).forEach((entry) => map.set(entry.item.id, String(entry.current_quantity)));
    return map;
  }, [houseStockSummaryQuery.data]);

  const invalidateVendors = () => queryClient.invalidateQueries({ queryKey: ["laundry-vendors", session.hotelId] });
  const invalidatePrices = (vendorId: number) =>
    queryClient.invalidateQueries({ queryKey: ["laundry-vendor-prices", session.hotelId, vendorId] });
  const invalidateLinenItems = () => queryClient.invalidateQueries({ queryKey: ["linen-items", session.hotelId] });
  const invalidateLinenLocations = () =>
    queryClient.invalidateQueries({ queryKey: ["linen-locations", session.hotelId] });
  const invalidateAfterRemito = () => {
    queryClient.invalidateQueries({ queryKey: ["laundry-remitos", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["laundry-vendor-balance", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["laundry-vendor-spend", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["linen-summary", session.hotelId] });
  };
  const invalidateAfterMovement = () => {
    queryClient.invalidateQueries({ queryKey: ["linen-summary", session.hotelId] });
  };

  const createVendorMutation = useMutation({
    mutationFn: () =>
      createLaundryVendor(
        {
          name: vendorForm.name,
          contact_phone: vendorForm.contact_phone || null,
          contact_email: vendorForm.contact_email || null
        },
        session
      ),
    onSuccess: (vendor) => {
      invalidateVendors();
      setVendorForm(emptyVendorForm);
      setSelectedVendorId(vendor.id);
      setMessage(`Lavadero "${vendor.name}" creado.`);
    }
  });

  const updateVendorMutation = useMutation({
    mutationFn: ({ vendorId, active }: { vendorId: number; active: boolean }) =>
      updateLaundryVendor(vendorId, { active }, session),
    onSuccess: (vendor) => {
      invalidateVendors();
      setMessage(`Lavadero "${vendor.name}" actualizado.`);
    }
  });

  // D (stock/lavanderia separation, real split): linen_items is its own
  // table now (see api/linen.ts) -- this form is the only way to add a new
  // linen type, there is no StockPage equivalent to fall back on.
  const createLinenItemMutation = useMutation({
    mutationFn: () => createLinenItem({ name: linenItemForm.name, unit: linenItemForm.unit }, session),
    onSuccess: () => {
      invalidateLinenItems();
      setLinenItemForm(emptyLinenItemForm);
      setMessage("Tipo de ropa blanca creado.");
    }
  });

  const createLinenLocationMutation = useMutation({
    mutationFn: () => createLinenLocation({ name: linenLocationForm.name }, session),
    onSuccess: () => {
      invalidateLinenLocations();
      setLinenLocationForm(emptyLinenLocationForm);
      setMessage("Ubicacion de lavanderia creada.");
    }
  });

  // Replaces the old workaround of loading an opening balance for a new
  // linen type through StockPage's generic movement form -- linen_items is
  // its own table now, so StockPage's form can no longer target it at all.
  const createLinenMovementMutation = useMutation({
    mutationFn: () =>
      createLinenMovement(
        {
          linen_item_id: Number(movementForm.linen_item_id),
          location_id: movementForm.location_id ? Number(movementForm.location_id) : null,
          movement_type: movementForm.movement_type,
          quantity: movementForm.quantity,
          reason: movementForm.reason || null
        },
        session
      ),
    onSuccess: () => {
      invalidateAfterMovement();
      setMovementForm(emptyMovementForm);
      setMessage("Movimiento registrado.");
    }
  });

  const setPriceMutation = useMutation({
    mutationFn: () =>
      setLaundryVendorPrice(
        selectedVendorId as number,
        { linen_item_id: Number(priceForm.linen_item_id), unit_price: priceForm.unit_price },
        session
      ),
    onSuccess: () => {
      if (selectedVendorId) invalidatePrices(selectedVendorId);
      setPriceForm(emptyPriceForm);
      setMessage("Precio guardado.");
    }
  });

  const markSettlementMutation = useMutation({
    mutationFn: ({ periodStart, paid, notes }: { periodStart: string; paid: boolean; notes?: string | null }) =>
      markLaundryVendorSettlementPaid(selectedVendorId as number, periodStart, { paid, notes }, session),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["laundry-vendor-settlements", session.hotelId, selectedVendorId]
      });
    }
  });

  // A duplicate remito submission would create a second real stock transfer
  // (and, for outbound, a second real charge from the laundry) -- guard it.
  const createRemitoMutation = useGuardedMutation({
    mutationFn: () =>
      createLaundryRemito(
        {
          vendor_id: Number(remitoForm.vendor_id),
          direction: remitoForm.direction,
          remito_number: remitoForm.remito_number.trim(),
          remito_date: new Date(`${remitoForm.remito_date}T00:00:00`).toISOString(),
          house_location_id: Number(remitoForm.house_location_id),
          notes: remitoForm.notes || null,
          lines: lines.map<LaundryRemitoLineCreate>((line) => ({
            linen_item_id: line.linen_item_id,
            quantity: line.quantity
          }))
        },
        session
      ),
    onSuccess: (response) => {
      invalidateAfterRemito();
      setLines([]);
      // Keep direction/vendor/house location: a remito cycle is "salida,
      // salida, entrada, ..." for the same vendor+location in one sitting
      // (see plan D), so re-selecting all three before every single line is
      // friction, not a safety feature -- only remito_number/date/lines/notes
      // are one-shot per remito and reset.
      setRemitoForm((current) => ({
        ...emptyRemitoForm(),
        direction: current.direction,
        vendor_id: current.vendor_id,
        house_location_id: current.house_location_id
      }));
      setMessage(
        response.warnings.length > 0
          ? `Remito ${response.remito.remito_number} guardado. ${response.warnings.join(" ")}`
          : `Remito ${response.remito.remito_number} guardado.`
      );
    }
  });

  const handleCreateVendor = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    if (!isOnline) {
      setMessage("Sin conexión. Conectate para crear el lavadero.");
      return;
    }
    try {
      await createVendorMutation.mutateAsync();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo crear el lavadero.");
    }
  };

  const handleSetPrice = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    if (!isOnline) {
      setMessage("Sin conexión. Conectate para guardar el precio.");
      return;
    }
    try {
      await setPriceMutation.mutateAsync();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo guardar el precio.");
    }
  };

  const handleCreateLinenItem = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    if (!isOnline) {
      setMessage("Sin conexión. Conectate para crear el tipo de ropa blanca.");
      return;
    }
    try {
      await createLinenItemMutation.mutateAsync();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo crear el tipo de ropa blanca.");
    }
  };

  const handleCreateLinenLocation = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    if (!isOnline) {
      setMessage("Sin conexión. Conectate para crear la ubicación.");
      return;
    }
    try {
      await createLinenLocationMutation.mutateAsync();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo crear la ubicacion.");
    }
  };

  // Opening balance / correction for a linen item -- linen_items has no
  // StockPage equivalent to fall back on anymore (see linen_service.py).
  const handleCreateLinenMovement = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    if (!isOnline) {
      setMessage("Sin conexión. Conectate para registrar el movimiento.");
      return;
    }
    try {
      await createLinenMovementMutation.mutateAsync();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo registrar el movimiento.");
    }
  };

  const addLine = () => {
    const itemId = Number(lineDraft.linen_item_id);
    const item = itemById.get(itemId);
    const quantity = Number(lineDraft.quantity);
    if (!item || !Number.isFinite(quantity) || quantity <= 0) return;
    setLines((current) => {
      const withoutItem = current.filter((line) => line.linen_item_id !== itemId);
      return [...withoutItem, { linen_item_id: itemId, item_name: item.name, unit: item.unit, quantity: lineDraft.quantity }];
    });
    setLineDraft({ linen_item_id: "", quantity: "1" });
  };

  const removeLine = (itemId: number) => setLines((current) => current.filter((line) => line.linen_item_id !== itemId));

  const remitoTotal = useMemo(() => {
    return lines.reduce((sum, line) => {
      const price = remitoVendorPriceByItem.get(line.linen_item_id);
      if (!price) return sum;
      return sum + Number(price.unit_price) * Number(line.quantity || 0);
    }, 0);
  }, [lines, remitoVendorPriceByItem]);
  const remitoCurrency = remitoVendorPricesQuery.data?.[0]?.currency_code;

  const handleCreateRemito = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setRemitoError(null);
    if (!isOnline) {
      setRemitoError("Sin conexión. Conectate para guardar el remito.");
      return;
    }
    if (lines.length === 0) {
      setRemitoError("Agregá al menos una línea (ítem + cantidad).");
      return;
    }
    try {
      await createRemitoMutation.mutateAsync();
    } catch (error) {
      // Surfaces the backend's exact message (e.g. "Not enough 'Sabanas' at
      // the source location: have 6.00, need 10.00") instead of a generic
      // failure -- the whole point of this guard per the task's D2 spec.
      setRemitoError(error instanceof Error ? error.message : "No se pudo guardar el remito.");
    }
  };

  const itemsAvailableToAdd = items.filter((item) => !lines.some((line) => line.linen_item_id === item.id));

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operacion</p>
          <h1 className="text-2xl font-semibold text-slate-900">Lavanderia</h1>
          <p className="text-sm text-slate-600">
            Ropa blanca con lavadero externo: lavaderos, remitos de salida/entrada y balance de qué hay dónde.
          </p>
        </div>
        {(vendorsQuery.isFetching || remitosQuery.isFetching) && <p className="text-xs text-slate-500">Actualizando...</p>}
      </header>

      {message ? <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">{message}</div> : null}

      {!isOnline && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900" role="status">
          Sin conexión. Podés seguir mirando los datos ya cargados, pero remitos, movimientos y altas se habilitan cuando vuelvas a estar online.
        </div>
      )}

      {/* Mobile task-based tabs -- desktop (md+) ignores mobileTab and keeps
          showing every section the user's permissions allow, same as before
          this task. Tab list itself is permission-filtered (see mobileTabs),
          not just its content. */}
      {mobileTabs.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-1 md:hidden" role="tablist" aria-label="Secciones de lavandería">
          {mobileTabs.map(({ tab, label }) => (
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
      )}

      {manageVendors && (
        <section className={showSection("vendors") ? "space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" : "hidden"}>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Lavaderos</p>
            <h2 className="text-lg font-semibold text-slate-900">Lavaderos y precios ({vendors.length})</h2>
            {vendorsQuery.error && <p className="text-xs text-rose-700">No se pudo cargar: {(vendorsQuery.error as Error).message}</p>}
          </div>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
            <div className="grid gap-3 sm:grid-cols-2">
              {vendors.map((vendor) => (
                <VendorCard
                  key={vendor.id}
                  vendor={vendor}
                  selected={selectedVendorId === vendor.id}
                  onSelect={() => setSelectedVendorId(vendor.id)}
                  onToggleActive={() => updateVendorMutation.mutate({ vendorId: vendor.id, active: !vendor.active })}
                  toggling={updateVendorMutation.isPending}
                />
              ))}
              {!vendorsQuery.isLoading && vendors.length === 0 && (
                <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-600 sm:col-span-2">
                  Todavía no hay lavaderos cargados. Creá el primero al lado.
                </div>
              )}
            </div>

            <div className="space-y-4">
              <form className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4" onSubmit={handleCreateVendor}>
                <p className="text-sm font-semibold text-slate-700">Nuevo lavadero</p>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Nombre</span>
                  <input
                    value={vendorForm.name}
                    onChange={(event) => setVendorForm((current) => ({ ...current, name: event.target.value }))}
                    required
                    className="w-full rounded-lg border border-slate-300 px-3 py-2"
                  />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Teléfono de contacto</span>
                  <input
                    value={vendorForm.contact_phone}
                    onChange={(event) => setVendorForm((current) => ({ ...current, contact_phone: event.target.value }))}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2"
                  />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Email de contacto</span>
                  <input
                    type="email"
                    value={vendorForm.contact_email}
                    onChange={(event) => setVendorForm((current) => ({ ...current, contact_email: event.target.value }))}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2"
                  />
                </label>
                <button
                  type="submit"
                  disabled={createVendorMutation.isPending || !isOnline}
                  className="min-h-11 w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                >
                  Crear lavadero
                </button>
              </form>

              {selectedVendor ? (
                <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-sm font-semibold text-slate-700">Precios de {selectedVendor.name}</p>
                  <ul className="space-y-1 text-sm">
                    {selectedVendorPrices.map((price) => {
                      const item = itemById.get(price.linen_item_id);
                      return (
                        <li key={price.id} className="flex items-center justify-between rounded-lg bg-white px-3 py-2 shadow-sm">
                          <span>{item?.name ?? `Ítem #${price.linen_item_id}`}</span>
                          <span className="font-semibold text-slate-900">
                            {formatMoney(price.unit_price, price.currency_code)}
                          </span>
                        </li>
                      );
                    })}
                    {selectedVendorPrices.length === 0 && (
                      <li className="text-xs text-slate-500">Sin precios cargados todavía.</li>
                    )}
                  </ul>
                  <form className="space-y-2" onSubmit={handleSetPrice}>
                    <label className="space-y-1 text-xs font-semibold text-slate-600">
                      Ítem
                      <select
                        value={priceForm.linen_item_id}
                        onChange={(event) => setPriceForm((current) => ({ ...current, linen_item_id: event.target.value }))}
                        required
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                      >
                        <option value="">Seleccionar</option>
                        {items.map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="space-y-1 text-xs font-semibold text-slate-600">
                      Precio por unidad
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={priceForm.unit_price}
                        onChange={(event) => setPriceForm((current) => ({ ...current, unit_price: event.target.value }))}
                        required
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                      />
                    </label>
                    <button
                      type="submit"
                      disabled={setPriceMutation.isPending || !isOnline}
                      className="min-h-11 w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                    >
                      Guardar precio
                    </button>
                  </form>
                </div>
              ) : (
                <p className="text-xs text-slate-500">Elegí un lavadero para editar sus precios.</p>
              )}
            </div>
          </div>
        </section>
      )}

      {manageVendors && (
        <section className={showSection("vendors") ? "space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" : "hidden"}>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Ropa blanca</p>
            <h2 className="text-lg font-semibold text-slate-900">Tipos de ropa blanca ({items.length})</h2>
            <p className="text-sm text-slate-600">
              Sabanas, toallas, fundas: separado del stock general de insumos (bolsas, detergentes, jabon), que se
              administra en Stock.
            </p>
          </div>
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
            <ul className="grid gap-2 sm:grid-cols-2">
              {items.map((item) => (
                <li key={item.id} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                  {item.name} <span className="text-xs text-slate-500">({item.unit})</span>
                </li>
              ))}
              {!itemsQuery.isLoading && items.length === 0 && (
                <li className="text-xs text-slate-500 sm:col-span-2">Todavía no hay tipos de ropa blanca cargados.</li>
              )}
            </ul>
            <form className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4" onSubmit={handleCreateLinenItem}>
              <p className="text-sm font-semibold text-slate-700">Nuevo tipo de ropa blanca</p>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Nombre</span>
                <input
                  value={linenItemForm.name}
                  onChange={(event) => setLinenItemForm((current) => ({ ...current, name: event.target.value }))}
                  placeholder="Toallas de piscina"
                  required
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Unidad</span>
                <input
                  value={linenItemForm.unit}
                  onChange={(event) => setLinenItemForm((current) => ({ ...current, unit: event.target.value }))}
                  required
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <button
                type="submit"
                disabled={createLinenItemMutation.isPending || !isOnline}
                className="min-h-11 w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
              >
                Crear tipo de ropa blanca
              </button>
            </form>
          </div>
        </section>
      )}

      {manageVendors && (
        <section className={showSection("vendors") ? "space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" : "hidden"}>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Ropa blanca</p>
            <h2 className="text-lg font-semibold text-slate-900">Ubicaciones y movimientos ({houseLocations.length})</h2>
            <p className="text-sm text-slate-600">
              Depositos propios del hotel para ropa blanca (ej. "Deposito de blancos") y carga de saldo inicial o
              correcciones de inventario -- separado de las ubicaciones de Stock general.
            </p>
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <ul className="grid gap-2">
              {houseLocations.map((location) => (
                <li key={location.id} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                  {location.name}
                </li>
              ))}
              {!locationsQuery.isLoading && houseLocations.length === 0 && (
                <li className="text-xs text-slate-500">Todavía no hay ubicaciones cargadas.</li>
              )}
            </ul>
            <form className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4" onSubmit={handleCreateLinenLocation}>
              <p className="text-sm font-semibold text-slate-700">Nueva ubicación</p>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Nombre</span>
                <input
                  value={linenLocationForm.name}
                  onChange={(event) => setLinenLocationForm({ name: event.target.value })}
                  placeholder="Deposito de blancos"
                  required
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <button
                type="submit"
                disabled={createLinenLocationMutation.isPending || !isOnline}
                className="min-h-11 w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
              >
                Crear ubicación
              </button>
            </form>
            <form className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4" onSubmit={handleCreateLinenMovement}>
              <p className="text-sm font-semibold text-slate-700">Registrar movimiento</p>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Ítem</span>
                <select
                  value={movementForm.linen_item_id}
                  onChange={(event) => setMovementForm((current) => ({ ...current, linen_item_id: event.target.value }))}
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
                <span className="text-slate-600">Ubicación</span>
                <select
                  value={movementForm.location_id}
                  onChange={(event) => setMovementForm((current) => ({ ...current, location_id: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                >
                  <option value="">Sin ubicación</option>
                  {houseLocations.map((location) => (
                    <option key={location.id} value={location.id}>
                      {location.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="grid grid-cols-2 gap-2" role="group" aria-label="Dirección del movimiento">
                <button
                  type="button"
                  aria-pressed={movementForm.movement_type === "in"}
                  onClick={() => setMovementForm((current) => ({ ...current, movement_type: "in" }))}
                  className={`min-h-11 rounded-lg border px-3 py-2 text-xs font-semibold ${
                    movementForm.movement_type === "in"
                      ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                      : "border-slate-200 bg-white text-slate-700"
                  }`}
                >
                  Ingreso
                </button>
                <button
                  type="button"
                  aria-pressed={movementForm.movement_type === "out"}
                  onClick={() => setMovementForm((current) => ({ ...current, movement_type: "out" }))}
                  className={`min-h-11 rounded-lg border px-3 py-2 text-xs font-semibold ${
                    movementForm.movement_type === "out"
                      ? "border-rose-300 bg-rose-50 text-rose-800"
                      : "border-slate-200 bg-white text-slate-700"
                  }`}
                >
                  Egreso
                </button>
              </div>
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
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Motivo</span>
                <input
                  value={movementForm.reason}
                  onChange={(event) => setMovementForm((current) => ({ ...current, reason: event.target.value }))}
                  placeholder="Stock inicial, conteo fisico"
                  required
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <button
                type="submit"
                disabled={createLinenMovementMutation.isPending || !isOnline}
                className="min-h-11 w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
              >
                Registrar movimiento
              </button>
            </form>
          </div>
        </section>
      )}

      {manageVendors && (
        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Reporte</p>
              <h2 className="text-lg font-semibold text-slate-900">Gasto de lavadero por período</h2>
              <p className="text-sm text-slate-600">
                Total facturado según lo que se mandó a lavar (remitos de salida) en el rango elegido.
              </p>
            </div>
            <div className="flex flex-wrap items-end gap-2">
              <button
                type="button"
                onClick={() => setSpendRange({ from: startOfCurrentWeekIso(), to: todayIso() })}
                className="min-h-11 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Semana actual
              </button>
              <button
                type="button"
                onClick={() => setSpendRange({ from: startOfCurrentMonthIso(), to: todayIso() })}
                className="min-h-11 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Mes actual
              </button>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Desde</span>
                <input
                  type="date"
                  value={spendRange.from}
                  max={spendRange.to}
                  onChange={(event) => setSpendRange((current) => ({ ...current, from: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Hasta</span>
                <input
                  type="date"
                  value={spendRange.to}
                  min={spendRange.from}
                  onChange={(event) => setSpendRange((current) => ({ ...current, to: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </label>
            </div>
          </div>

          <p className="text-2xl font-semibold text-slate-900">
            Total del período: {formatMoney(spendTotal)}
            {spendFetching && <span className="ml-2 text-xs font-normal text-slate-500">Actualizando...</span>}
          </p>

          <div className="grid gap-3 sm:grid-cols-2">
            {vendors.map((vendor, index) => {
              const spend = spendQueries[index]?.data;
              const byItem = spend?.by_item ?? [];
              return (
                <div key={vendor.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-slate-900">{vendor.name}</p>
                    <p className="text-sm font-semibold text-slate-900">{formatMoney(spend?.total ?? 0)}</p>
                  </div>
                  {byItem.length === 0 ? (
                    <p className="mt-2 text-xs text-slate-500">Sin remitos de salida en este período.</p>
                  ) : (
                    <ul className="mt-2 space-y-1 text-xs text-slate-700">
                      {byItem.map((line) => (
                        <li key={line.linen_item_id} className="flex justify-between gap-2">
                          <span>
                            {line.linen_item_name} × {line.quantity}
                          </span>
                          <span className="font-semibold">{formatMoney(line.subtotal)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
            {vendors.length === 0 && <p className="text-xs text-slate-500">Todavía no hay lavaderos.</p>}
          </div>
        </section>
      )}

      {manageVendors && (
        <SettlementSection
          selectedVendor={selectedVendor}
          year={settlementYear}
          onYearChange={setSettlementYear}
          quarters={settlementQuarters}
          query={settlementsQuery}
          onMark={(periodStart, paid, notes) => markSettlementMutation.mutate({ periodStart, paid, notes })}
          marking={markSettlementMutation.isPending}
        />
      )}

      {operateRemitos && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
          <section className={showSection("history") ? "space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" : "hidden"}>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Historial</p>
              <h2 className="text-lg font-semibold text-slate-900">Remitos ({remitos.length})</h2>
              {remitosQuery.error && <p className="text-xs text-rose-700">No se pudo cargar: {(remitosQuery.error as Error).message}</p>}
            </div>
            <ul className="space-y-2" aria-label="Historial de remitos">
              {remitos.map((remito) => {
                const vendor = vendorById.get(remito.vendor_id);
                return (
                  <li key={remito.id} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">
                          {remito.direction === "outbound" ? "Salida" : "Entrada"} · {vendor?.name ?? `Lavadero #${remito.vendor_id}`}
                        </p>
                        <p className="text-xs text-slate-600">Remito {remito.remito_number}</p>
                      </div>
                      <time className="shrink-0 text-xs text-slate-500" dateTime={remito.remito_date}>
                        {new Date(remito.remito_date).toLocaleDateString("es-AR")}
                      </time>
                    </div>
                    <ul className="mt-2 space-y-1">
                      {remito.lines.map((line) => (
                        <li key={line.id} className="text-xs text-slate-600">
                          {itemById.get(line.linen_item_id)?.name ?? `Ítem #${line.linen_item_id}`}: {line.quantity}
                        </li>
                      ))}
                    </ul>
                  </li>
                );
              })}
              {!remitosQuery.isLoading && remitos.length === 0 && (
                <li className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
                  Todavía no hay remitos registrados.
                </li>
              )}
            </ul>

            <div className="border-t border-slate-200 pt-4" role="region" aria-labelledby="vendor-balance-title">
              <p className="text-xs uppercase tracking-wide text-slate-500">Balance por lavadero</p>
              <h3 id="vendor-balance-title" className="text-base font-semibold text-slate-900">
                Qué está en cada lavadero ahora
              </h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {vendors.map((vendor, index) => {
                  const balance = balanceQueries[index]?.data ?? [];
                  return (
                    <div key={vendor.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                      <p className="text-sm font-semibold text-slate-900">{vendor.name}</p>
                      {balance.length === 0 ? (
                        <p className="text-xs text-slate-500">Nada pendiente en este lavadero.</p>
                      ) : (
                        <ul className="mt-1 space-y-1 text-xs text-slate-700">
                          {balance.map((line) => (
                            <li key={line.linen_item_id} className="flex justify-between">
                              <span>{line.linen_item_name}</span>
                              <span className="font-semibold">{line.quantity}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  );
                })}
                {vendors.length === 0 && <p className="text-xs text-slate-500">Todavía no hay lavaderos.</p>}
              </div>
            </div>
          </section>

          <aside className="space-y-4">
            <form
              className={remitoFormVisible ? "space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" : "hidden"}
              onSubmit={handleCreateRemito}
            >
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Remito</p>
                <h2 className="text-lg font-semibold text-slate-900">Nuevo remito</h2>
              </div>

              <div className="grid grid-cols-2 gap-2" role="group" aria-label="Dirección del remito">
                <button
                  type="button"
                  aria-pressed={remitoForm.direction === "outbound"}
                  onClick={() => setRemitoForm((current) => ({ ...current, direction: "outbound" }))}
                  className={`min-h-11 rounded-lg border px-3 py-2 text-xs font-semibold ${
                    remitoForm.direction === "outbound"
                      ? "border-rose-300 bg-rose-50 text-rose-800"
                      : "border-slate-200 bg-white text-slate-700"
                  }`}
                >
                  Salida (se lleva sucia)
                </button>
                <button
                  type="button"
                  aria-pressed={remitoForm.direction === "inbound"}
                  onClick={() => setRemitoForm((current) => ({ ...current, direction: "inbound" }))}
                  className={`min-h-11 rounded-lg border px-3 py-2 text-xs font-semibold ${
                    remitoForm.direction === "inbound"
                      ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                      : "border-slate-200 bg-white text-slate-700"
                  }`}
                >
                  Entrada (trae limpia)
                </button>
              </div>

              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Lavadero</span>
                <select
                  value={remitoForm.vendor_id}
                  onChange={(event) => setRemitoForm((current) => ({ ...current, vendor_id: event.target.value }))}
                  required
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                >
                  <option value="">Seleccionar</option>
                  {activeVendors.map((vendor) => (
                    <option key={vendor.id} value={vendor.id}>
                      {vendor.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Ubicación casa (origen/destino en el hotel)</span>
                <select
                  value={remitoForm.house_location_id}
                  onChange={(event) => setRemitoForm((current) => ({ ...current, house_location_id: event.target.value }))}
                  required
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                >
                  <option value="">Seleccionar</option>
                  {houseLocations.map((location) => (
                    <option key={location.id} value={location.id}>
                      {location.name}
                    </option>
                  ))}
                </select>
              </label>

              <div className="grid grid-cols-2 gap-2">
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">N° de remito (papel)</span>
                  <input
                    value={remitoForm.remito_number}
                    onChange={(event) => setRemitoForm((current) => ({ ...current, remito_number: event.target.value }))}
                    required
                    className="w-full rounded-lg border border-slate-300 px-3 py-2"
                  />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Fecha</span>
                  <input
                    type="date"
                    value={remitoForm.remito_date}
                    onChange={(event) => setRemitoForm((current) => ({ ...current, remito_date: event.target.value }))}
                    required
                    className="w-full rounded-lg border border-slate-300 px-3 py-2"
                  />
                </label>
              </div>

              <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Líneas</p>
                {lines.length > 0 && (
                  <ul className="space-y-1">
                    {lines.map((line) => {
                      const price = remitoVendorPriceByItem.get(line.linen_item_id);
                      const subtotal = price ? Number(price.unit_price) * Number(line.quantity || 0) : null;
                      return (
                        <li key={line.linen_item_id} className="flex items-center justify-between gap-2 rounded-md bg-white px-3 py-2 text-sm shadow-sm">
                          <span>
                            {line.item_name} × {line.quantity} {line.unit}
                          </span>
                          <span className="flex items-center gap-2">
                            {manageVendors && (
                              <span className="text-xs text-slate-600">
                                {subtotal !== null ? formatMoney(subtotal, remitoCurrency) : "sin precio"}
                              </span>
                            )}
                            <button
                              type="button"
                              onClick={() => removeLine(line.linen_item_id)}
                              aria-label={`Quitar ${line.item_name}`}
                              className="text-xs font-semibold text-rose-700 hover:underline"
                            >
                              Quitar
                            </button>
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                )}
                <div className="grid grid-cols-[1fr_90px_auto] items-end gap-2">
                  <label className="space-y-1 text-xs font-semibold text-slate-600">
                    Ítem
                    <select
                      value={lineDraft.linen_item_id}
                      onChange={(event) => setLineDraft((current) => ({ ...current, linen_item_id: event.target.value }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    >
                      <option value="">Seleccionar</option>
                      {itemsAvailableToAdd.map((item: LinenItem) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1 text-xs font-semibold text-slate-600">
                    Cant.
                    <input
                      type="number"
                      min="0.01"
                      step="0.01"
                      value={lineDraft.quantity}
                      onChange={(event) => setLineDraft((current) => ({ ...current, quantity: event.target.value }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={addLine}
                    disabled={!lineDraft.linen_item_id}
                    className="min-h-11 rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700 hover:bg-brand-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Agregar línea
                  </button>
                </div>
                {manageVendors && lines.length > 0 && (
                  <p className="text-right text-sm font-semibold text-slate-800">
                    Total estimado: {formatMoney(remitoTotal, remitoCurrency)}
                  </p>
                )}
              </div>

              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Notas (opcional)</span>
                <textarea
                  value={remitoForm.notes}
                  onChange={(event) => setRemitoForm((current) => ({ ...current, notes: event.target.value }))}
                  rows={2}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>

              {remitoError && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800" role="alert">
                  {remitoError}
                </div>
              )}

              <button
                type="submit"
                disabled={createRemitoMutation.isPending || !isOnline}
                className="min-h-11 w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
              >
                {createRemitoMutation.isPending ? "Guardando..." : "Guardar remito"}
              </button>
            </form>

            {/* GET /api/laundry/items/{id}/current and .../items/summary both
                accept laundry:operate_remitos OR laundry:manage_vendors (see
                app/api/laundry_vendor.py) -- housekeeping holds the former,
                so this is not manageVendors-gated (a prior version of this
                comment incorrectly claimed the backend required stock:operate,
                which does not apply to this linen-specific endpoint at all). */}
            <div className={showSection("available") ? "" : "hidden"}>
              <HouseStockPanel
                locations={houseLocations}
                items={items}
                selectedLocationId={houseStockLocationId}
                onSelectLocation={setHouseStockLocationId}
                currentByItemId={houseStockByItemId}
                isLoading={houseStockSummaryQuery.isFetching}
              />
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}

function VendorCard({
  vendor,
  selected,
  onSelect,
  onToggleActive,
  toggling
}: {
  vendor: LaundryVendor;
  selected: boolean;
  onSelect: () => void;
  onToggleActive: () => void;
  toggling: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-4 shadow-sm ${selected ? "border-brand-200 bg-brand-50" : "border-slate-200 bg-white"}`}
    >
      <button type="button" onClick={onSelect} className="w-full text-left">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="break-words text-base font-semibold text-slate-900">{vendor.name}</h3>
            <p className="text-xs text-slate-500">{vendor.contact_phone || vendor.contact_email || "Sin contacto cargado"}</p>
          </div>
          <span className={`rounded-full px-2 py-1 text-xs font-semibold ${vendor.active ? "bg-emerald-100 text-emerald-800" : "bg-slate-200 text-slate-700"}`}>
            {vendor.active ? "Activo" : "Inactivo"}
          </span>
        </div>
      </button>
      <button
        type="button"
        onClick={onToggleActive}
        disabled={toggling}
        className="mt-3 min-h-11 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
      >
        {vendor.active ? "Marcar inactivo" : "Reactivar"}
      </button>
    </div>
  );
}

const QUARTER_LABELS: Record<string, string> = {
  "01": "T1 (ene-mar)",
  "04": "T2 (abr-jun)",
  "07": "T3 (jul-sep)",
  "10": "T4 (oct-dic)"
};

function quarterLabel(periodStart: string) {
  const month = periodStart.slice(5, 7);
  return QUARTER_LABELS[month] ?? periodStart;
}

// D-liquidacion: "lo que nosotros anotamos, trimestre a trimestre" para
// comparar contra la factura real del lavadero. total_amount reusa
// exactamente el mismo calculo que el reporte de gasto de arriba (suma de
// unit_price_snapshot, nunca el precio vigente) -- ver
// vendor_settlements en app/services/laundry_vendor_service.py. El estado
// pagado/no pagado es solo una alerta visual: nunca bloquea nada.
function SettlementSection({
  selectedVendor,
  year,
  onYearChange,
  quarters,
  query,
  onMark,
  marking
}: {
  selectedVendor: LaundryVendor | null;
  year: number;
  onYearChange: (year: number) => void;
  quarters: LaundryVendorSettlementQuarter[];
  query: UseQueryResult<LaundryVendorSettlementQuarter[]>;
  onMark: (periodStart: string, paid: boolean, notes?: string | null) => void;
  marking: boolean;
}) {
  return (
    <section
      aria-labelledby="laundry-settlement-title"
      className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Reporte</p>
          <h2 id="laundry-settlement-title" className="text-lg font-semibold text-slate-900">
            Liquidación por trimestre {selectedVendor ? `· ${selectedVendor.name}` : ""}
          </h2>
          <p className="text-sm text-slate-600">
            Lo que anotamos nosotros, trimestre a trimestre, para comparar contra la factura real del lavadero.
          </p>
        </div>
        <label className="space-y-1 text-sm">
          <span className="text-slate-600">Año</span>
          <input
            type="number"
            value={year}
            onChange={(event) => onYearChange(Number(event.target.value) || year)}
            className="w-28 rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
      </div>

      {!selectedVendor && (
        <p className="text-xs text-slate-500">Elegí un lavadero arriba para ver su liquidación trimestral.</p>
      )}
      {selectedVendor && query.isFetching && <p className="text-xs text-slate-500">Actualizando...</p>}
      {selectedVendor && query.isError && (
        <p className="text-xs text-rose-700">No se pudo cargar la liquidación de este lavadero.</p>
      )}

      {selectedVendor && (
        <div className="space-y-3">
          {quarters.map((quarter) => (
            <SettlementQuarterRow
              key={quarter.period_start}
              quarter={quarter}
              onMark={onMark}
              marking={marking}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function SettlementQuarterRow({
  quarter,
  onMark,
  marking
}: {
  quarter: LaundryVendorSettlementQuarter;
  onMark: (periodStart: string, paid: boolean, notes?: string | null) => void;
  marking: boolean;
}) {
  const [notesDraft, setNotesDraft] = useState(quarter.notes ?? "");

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-slate-900">
            {quarterLabel(quarter.period_start)} · {quarter.period_start} a {quarter.period_end}
          </p>
          <p className="text-sm text-slate-700">Total anotado: {formatMoney(quarter.total_amount)}</p>
        </div>
        <button
          type="button"
          onClick={() => onMark(quarter.period_start, !quarter.paid)}
          disabled={marking}
          className={`min-h-11 rounded-full px-3 py-1.5 text-xs font-semibold disabled:opacity-60 ${
            quarter.paid ? "bg-emerald-100 text-emerald-800 hover:bg-emerald-200" : "bg-amber-100 text-amber-800 hover:bg-amber-200"
          }`}
        >
          {quarter.paid ? "Pagado" : "No pagado"}
        </button>
      </div>

      {quarter.by_item.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-slate-700">
          {quarter.by_item.map((line) => (
            <li key={line.linen_item_id} className="flex justify-between gap-2">
              <span>
                {line.linen_item_name} × {line.quantity}
              </span>
              <span className="font-semibold">{formatMoney(line.subtotal)}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-end">
        <label className="flex-1 space-y-1 text-xs font-semibold text-slate-600">
          Notas (diferencias con la factura real)
          <textarea
            value={notesDraft}
            onChange={(event) => setNotesDraft(event.target.value)}
            rows={1}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal"
          />
        </label>
        <button
          type="button"
          onClick={() => onMark(quarter.period_start, quarter.paid, notesDraft)}
          disabled={marking}
          className="min-h-11 shrink-0 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
        >
          Guardar nota
        </button>
      </div>
    </div>
  );
}

// "Limpio disponible en el hotel": current_stock() narrowed to whichever
// hotel LinenLocation the operator picks (e.g. "Deposito de blancos"). This
// lives here (not on StockPage) because it's the number that answers "¿me
// alcanza para mandar este remito?" right before creating one -- the general
// StockPage keeps the hotel-wide total, which never moves on a transfer.
function HouseStockPanel({
  locations,
  items,
  selectedLocationId,
  onSelectLocation,
  currentByItemId,
  isLoading
}: {
  locations: Array<{ id: number; name: string }>;
  items: LinenItem[];
  selectedLocationId: string;
  onSelectLocation: (value: string) => void;
  currentByItemId: Map<number, string>;
  isLoading: boolean;
}) {
  return (
    <section aria-labelledby="house-stock-title" className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div>
        <p className="text-xs uppercase tracking-wide text-slate-500">Stock del hotel</p>
        <h2 id="house-stock-title" className="text-lg font-semibold text-slate-900">Limpio disponible en el hotel</h2>
      </div>
      <label className="space-y-1 text-sm">
        <span className="text-slate-600">Ubicación</span>
        <select
          value={selectedLocationId}
          onChange={(event) => onSelectLocation(event.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2"
        >
          <option value="">Elegí una ubicación</option>
          {locations.map((location) => (
            <option key={location.id} value={location.id}>
              {location.name}
            </option>
          ))}
        </select>
      </label>
      {selectedLocationId ? (
        <>
          {isLoading && <p className="text-xs text-slate-500">Actualizando...</p>}
          <ul className="space-y-1 text-sm">
            {items.map((item) => (
              <li key={item.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
                <span>{item.name}</span>
                <span className="font-semibold text-slate-900">
                  {currentByItemId.has(item.id) ? `${currentByItemId.get(item.id)} ${item.unit}` : "..."}
                </span>
              </li>
            ))}
            {items.length === 0 && <li className="text-xs text-slate-500">No hay ítems de stock cargados.</li>}
          </ul>
        </>
      ) : (
        <p className="text-xs text-slate-500">Elegí una ubicación para ver el stock limpio disponible ahí.</p>
      )}
    </section>
  );
}
