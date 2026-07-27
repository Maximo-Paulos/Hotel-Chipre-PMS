import { useMemo, useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createLaundryRemito,
  createLaundryVendor,
  getLaundryVendorBalance,
  getLaundryVendorSpend,
  listLaundryRemitos,
  listLaundryVendorPrices,
  listLaundryVendors,
  setLaundryVendorPrice,
  updateLaundryVendor,
  type LaundryRemitoLineCreate,
  type LaundryVendor,
  type RemitoDirection
} from "../../api/laundryVendor";
import { createStockItem, getCurrentStock, listStockItems, listStockLocations, type StockItem } from "../../api/stock";
import { hasValidSession } from "../../api/client";
import { useGuardedMutation } from "../../hooks/useGuardedMutation";
import { useSession } from "../../state/session";
import { formatMoney } from "../../utils/currency";
import { startOfCurrentMonthIso, startOfCurrentWeekIso, todayIso } from "../../utils/date";

// D2 (Via D lavanderia): replaces the old LaundryBatch/LaundryItem UI
// entirely -- D0 confirmed no open batches in production, so there is no
// read-only legacy view to keep around (see memory checkpoint
// 20260726-002247 for the D1 backend this consumes). A remito is a transfer
// between the hotel's own StockLocation and the vendor's dedicated one, so
// "en el lavadero ahora" and "limpio disponible en el hotel" are both just
// current_stock() narrowed to different location_id values -- see the two
// panels near the bottom of this file.
// C4: both take session.role (not baseRole) by design -- they only ever
// hide buttons the backend would reject anyway (the page's own data fetches
// are gated on hasValidSession only, not on these), so previewing "what a
// housekeeping user sees here" via "Cambiar vista" is the switcher's job.
const canManageVendors = (role: string | null) => ["owner", "co_owner", "manager"].includes(role ?? "");
const canOperateRemitos = (role: string | null) =>
  ["owner", "co_owner", "manager", "housekeeping"].includes(role ?? "");

// D3 (Via D lavanderia): "cuanto le pague al lavadero" range presets, using
// hotel-local (not UTC) dates -- see utils/date.ts (startOfCurrentWeekIso/
// startOfCurrentMonthIso, shared with the D5 stock consumption report).
const dayStartIso = (day: string) => new Date(`${day}T00:00:00`).toISOString();
const dayEndIso = (day: string) => new Date(`${day}T23:59:59.999`).toISOString();

const emptyVendorForm = { name: "", contact_phone: "", contact_email: "" };
const emptyPriceForm = { stock_item_id: "", unit_price: "" };
const emptyLinenItemForm = { name: "", unit: "unidad" };

type LineDraft = { stock_item_id: number; item_name: string; unit: string; quantity: string };

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
  const queryClient = useQueryClient();
  const enabled = hasValidSession(session);
  const manageVendors = canManageVendors(session.role);
  const operateRemitos = canOperateRemitos(session.role);

  const [message, setMessage] = useState<string | null>(null);
  const [selectedVendorId, setSelectedVendorId] = useState<number | null>(null);
  const [vendorForm, setVendorForm] = useState(emptyVendorForm);
  const [priceForm, setPriceForm] = useState(emptyPriceForm);
  const [linenItemForm, setLinenItemForm] = useState(emptyLinenItemForm);
  const [remitoForm, setRemitoForm] = useState(emptyRemitoForm);
  const [lines, setLines] = useState<LineDraft[]>([]);
  const [lineDraft, setLineDraft] = useState({ stock_item_id: "", quantity: "1" });
  const [remitoError, setRemitoError] = useState<string | null>(null);
  const [houseStockLocationId, setHouseStockLocationId] = useState<string>("");
  const [spendRange, setSpendRange] = useState(() => ({ from: startOfCurrentMonthIso(), to: todayIso() }));

  const vendorsQuery = useQuery({
    queryKey: ["laundry-vendors", session.hotelId],
    queryFn: () => listLaundryVendors(session),
    enabled,
    staleTime: 30 * 1000
  });
  // LaundryPage only ever deals with ropa blanca (kind="linen") -- general
  // supplies (bolsas, detergentes, jabon) live in StockPage instead.
  const itemsQuery = useQuery({
    queryKey: ["stock-items", session.hotelId, "linen"],
    queryFn: () => listStockItems({ kind: "linen" }, session),
    enabled,
    staleTime: 30 * 1000
  });
  const locationsQuery = useQuery({
    queryKey: ["stock-locations", session.hotelId],
    queryFn: () => listStockLocations(session),
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

  // Vendor StockLocations are administrative (created automatically with the
  // vendor to represent "what's physically at that laundry") -- exclude them
  // from any selector meant to pick a real hotel storage location, so they
  // don't get mixed with places like "Deposito" or "Recepcion".
  const vendorLocationIds = useMemo(() => new Set(vendors.map((vendor) => vendor.stock_location_id)), [vendors]);
  const houseLocations = useMemo(
    () => locations.filter((location) => !vendorLocationIds.has(location.id)),
    [locations, vendorLocationIds]
  );

  const selectedVendor = selectedVendorId ? (vendorById.get(selectedVendorId) ?? null) : null;
  const pricesQuery = useQuery({
    queryKey: ["laundry-vendor-prices", session.hotelId, selectedVendorId],
    queryFn: () => listLaundryVendorPrices(selectedVendorId as number, session),
    enabled: enabled && selectedVendorId !== null,
    staleTime: 15 * 1000
  });
  const selectedVendorPrices = useMemo(() => pricesQuery.data ?? [], [pricesQuery.data]);

  // Prices for the vendor picked in the remito form (may differ from
  // selectedVendorId, which drives the admin panel above).
  const remitoVendorId = remitoForm.vendor_id ? Number(remitoForm.vendor_id) : null;
  const remitoVendorPricesQuery = useQuery({
    queryKey: ["laundry-vendor-prices", session.hotelId, remitoVendorId],
    queryFn: () => listLaundryVendorPrices(remitoVendorId as number, session),
    enabled: enabled && remitoVendorId !== null,
    staleTime: 15 * 1000
  });
  const remitoVendorPriceByItem = useMemo(() => {
    const map = new Map<number, { unit_price: string; currency_code: string }>();
    (remitoVendorPricesQuery.data ?? []).forEach((price) =>
      map.set(price.stock_item_id, { unit_price: String(price.unit_price), currency_code: price.currency_code })
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

  const houseStockQueries = useQueries({
    queries: items.map((item) => ({
      queryKey: ["stock-current", session.hotelId, item.id, houseStockLocationId || "hotel-wide"],
      queryFn: () =>
        getCurrentStock(item.id, houseStockLocationId ? { locationId: Number(houseStockLocationId) } : {}, session),
      enabled: enabled && Boolean(houseStockLocationId),
      staleTime: 15 * 1000
    }))
  });

  const invalidateVendors = () => queryClient.invalidateQueries({ queryKey: ["laundry-vendors", session.hotelId] });
  const invalidatePrices = (vendorId: number) =>
    queryClient.invalidateQueries({ queryKey: ["laundry-vendor-prices", session.hotelId, vendorId] });
  const invalidateAfterRemito = () => {
    queryClient.invalidateQueries({ queryKey: ["laundry-remitos", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["laundry-vendor-balance", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["laundry-vendor-spend", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["stock-current", session.hotelId] });
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

  // D (stock/lavanderia separation): LaundryPage used to reuse StockPage's
  // generic item form for new ropa blanca (e.g. "toallas de piscina" nuevas)
  // -- now that kind separates the two lists, it needs its own create-item
  // form so a new linen type never has to be added from StockPage.
  const createLinenItemMutation = useMutation({
    mutationFn: () =>
      createStockItem({ name: linenItemForm.name, unit: linenItemForm.unit, kind: "linen" }, session),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stock-items", session.hotelId] });
      setLinenItemForm(emptyLinenItemForm);
      setMessage("Tipo de ropa blanca creado.");
    }
  });

  const setPriceMutation = useMutation({
    mutationFn: () =>
      setLaundryVendorPrice(
        selectedVendorId as number,
        { stock_item_id: Number(priceForm.stock_item_id), unit_price: priceForm.unit_price },
        session
      ),
    onSuccess: () => {
      if (selectedVendorId) invalidatePrices(selectedVendorId);
      setPriceForm(emptyPriceForm);
      setMessage("Precio guardado.");
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
            stock_item_id: line.stock_item_id,
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
    try {
      await createVendorMutation.mutateAsync();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo crear el lavadero.");
    }
  };

  const handleSetPrice = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    try {
      await setPriceMutation.mutateAsync();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo guardar el precio.");
    }
  };

  const handleCreateLinenItem = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    try {
      await createLinenItemMutation.mutateAsync();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo crear el tipo de ropa blanca.");
    }
  };

  const addLine = () => {
    const itemId = Number(lineDraft.stock_item_id);
    const item = itemById.get(itemId);
    const quantity = Number(lineDraft.quantity);
    if (!item || !Number.isFinite(quantity) || quantity <= 0) return;
    setLines((current) => {
      const withoutItem = current.filter((line) => line.stock_item_id !== itemId);
      return [...withoutItem, { stock_item_id: itemId, item_name: item.name, unit: item.unit, quantity: lineDraft.quantity }];
    });
    setLineDraft({ stock_item_id: "", quantity: "1" });
  };

  const removeLine = (itemId: number) => setLines((current) => current.filter((line) => line.stock_item_id !== itemId));

  const remitoTotal = useMemo(() => {
    return lines.reduce((sum, line) => {
      const price = remitoVendorPriceByItem.get(line.stock_item_id);
      if (!price) return sum;
      return sum + Number(price.unit_price) * Number(line.quantity || 0);
    }, 0);
  }, [lines, remitoVendorPriceByItem]);
  const remitoCurrency = remitoVendorPricesQuery.data?.[0]?.currency_code;

  const handleCreateRemito = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setRemitoError(null);
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

  const itemsAvailableToAdd = items.filter((item) => !lines.some((line) => line.stock_item_id === item.id));

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

      {manageVendors && (
        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
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
                  disabled={createVendorMutation.isPending}
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
                      const item = itemById.get(price.stock_item_id);
                      return (
                        <li key={price.id} className="flex items-center justify-between rounded-lg bg-white px-3 py-2 shadow-sm">
                          <span>{item?.name ?? `Ítem #${price.stock_item_id}`}</span>
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
                        value={priceForm.stock_item_id}
                        onChange={(event) => setPriceForm((current) => ({ ...current, stock_item_id: event.target.value }))}
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
                      disabled={setPriceMutation.isPending}
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
        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
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
                disabled={createLinenItemMutation.isPending}
                className="min-h-11 w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
              >
                Crear tipo de ropa blanca
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
                        <li key={line.stock_item_id} className="flex justify-between gap-2">
                          <span>
                            {line.stock_item_name} × {line.quantity}
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

      {operateRemitos && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
          <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
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
                          {itemById.get(line.stock_item_id)?.name ?? `Ítem #${line.stock_item_id}`}: {line.quantity}
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
                            <li key={line.stock_item_id} className="flex justify-between">
                              <span>{line.stock_item_name}</span>
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
            <form className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" onSubmit={handleCreateRemito}>
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
                      const price = remitoVendorPriceByItem.get(line.stock_item_id);
                      const subtotal = price ? Number(price.unit_price) * Number(line.quantity || 0) : null;
                      return (
                        <li key={line.stock_item_id} className="flex items-center justify-between gap-2 rounded-md bg-white px-3 py-2 text-sm shadow-sm">
                          <span>
                            {line.item_name} × {line.quantity} {line.unit}
                          </span>
                          <span className="flex items-center gap-2">
                            <span className="text-xs text-slate-600">
                              {subtotal !== null ? formatMoney(subtotal, remitoCurrency) : "sin precio"}
                            </span>
                            <button
                              type="button"
                              onClick={() => removeLine(line.stock_item_id)}
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
                      value={lineDraft.stock_item_id}
                      onChange={(event) => setLineDraft((current) => ({ ...current, stock_item_id: event.target.value }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    >
                      <option value="">Seleccionar</option>
                      {itemsAvailableToAdd.map((item: StockItem) => (
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
                    disabled={!lineDraft.stock_item_id}
                    className="min-h-11 rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700 hover:bg-brand-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Agregar línea
                  </button>
                </div>
                {lines.length > 0 && (
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
                disabled={createRemitoMutation.isPending}
                className="min-h-11 w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
              >
                {createRemitoMutation.isPending ? "Guardando..." : "Guardar remito"}
              </button>
            </form>

            {/* GET /api/stock/items/{id}/current requires stock:operate,
                which housekeeping does not hold (only the laundry-specific
                permissions above) -- gate this panel the same way StockPage
                itself is gated in AppShell's nav, or housekeeping would see
                a 403 in every row instead of a balance. */}
            {manageVendors && (
              <HouseStockPanel
                locations={houseLocations}
                items={items}
                selectedLocationId={houseStockLocationId}
                onSelectLocation={setHouseStockLocationId}
                stockQueries={houseStockQueries}
              />
            )}
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

// "Limpio disponible en el hotel": current_stock() narrowed to whichever
// hotel StockLocation the operator picks (e.g. "Deposito de blancos"). This
// lives here (not on StockPage) because it's the number that answers "¿me
// alcanza para mandar este remito?" right before creating one -- the general
// StockPage keeps the hotel-wide total, which never moves on a transfer.
function HouseStockPanel({
  locations,
  items,
  selectedLocationId,
  onSelectLocation,
  stockQueries
}: {
  locations: Array<{ id: number; name: string }>;
  items: StockItem[];
  selectedLocationId: string;
  onSelectLocation: (value: string) => void;
  stockQueries: Array<{ data?: { quantity: string | number } }>;
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
        <ul className="space-y-1 text-sm">
          {items.map((item, index) => (
            <li key={item.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
              <span>{item.name}</span>
              <span className="font-semibold text-slate-900">
                {stockQueries[index]?.data ? `${stockQueries[index]?.data?.quantity} ${item.unit}` : "..."}
              </span>
            </li>
          ))}
          {items.length === 0 && <li className="text-xs text-slate-500">No hay ítems de stock cargados.</li>}
        </ul>
      ) : (
        <p className="text-xs text-slate-500">Elegí una ubicación para ver el stock limpio disponible ahí.</p>
      )}
    </section>
  );
}
