import { useState } from "react";

import type { StockItem, StockItemUpdate } from "../api/stock";
import { useCollaborativeResource } from "../hooks/useCollaborativeResource";

// Owner: "editar el producto por las dudas" -- name/sku/unit/minimo, the
// fields PATCH /api/stock/items/{id} already accepted but no UI ever sent.
// unit_cost keeps its own inline field (UnitCostField) since that is the one
// field owners change often; this modal is for the rest.
export default function EditStockItemModal({
  item,
  saving,
  collaborationEnabled,
  onSave,
  onCollaborativeSaved,
  onCancel
}: {
  item: StockItem | null;
  saving: boolean;
  collaborationEnabled: boolean;
  onSave: (changes: StockItemUpdate) => void | Promise<void>;
  onCollaborativeSaved: () => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState({ name: "", sku: "", unit: "", min_quantity: "" });
  const [formError, setFormError] = useState<string | null>(null);

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

  const collaborativeItem = useCollaborativeResource({
    resourceType: "stock_item",
    resourceId: item?.id,
    initialValues: item
      ? {
          name: item.name,
          sku: item.sku ?? null,
          unit: item.unit,
          min_quantity: item.min_quantity ?? null,
          unit_cost: item.unit_cost ?? null,
          active: item.active
        }
      : null,
    enabled: Boolean(item && collaborationEnabled)
  });

  const collaborativeForm = {
    ...form,
    name: String(collaborativeItem.draftValues.name ?? form.name),
    sku: String(collaborativeItem.draftValues.sku ?? ""),
    unit: String(collaborativeItem.draftValues.unit ?? form.unit),
    min_quantity:
      collaborativeItem.draftValues.min_quantity === null || collaborativeItem.draftValues.min_quantity === undefined
        ? ""
        : String(collaborativeItem.draftValues.min_quantity)
  };

  const setItemField = (field: "name" | "sku" | "unit" | "min_quantity", value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
    const normalized = field === "sku" || field === "min_quantity" ? value || null : value;
    collaborativeItem.setField(field, normalized);
  };

  const handleCancel = () => {
    if (collaborativeItem.isSaving || saving) return;
    onCancel();
  };

  if (!item) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex animate-fade-in items-center justify-center bg-slate-900/40 px-4 py-6"
      onClick={handleCancel}
    >
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-stock-item-title"
        className="w-full max-w-sm animate-scale-in rounded-xl border border-slate-200 bg-white p-5 shadow-xl"
        onClick={(event) => event.stopPropagation()}
        onSubmit={async (event) => {
          event.preventDefault();
          setFormError(null);
          try {
            if (collaborativeItem.status !== "idle") {
              if (Object.keys(collaborativeItem.conflicts).length > 0) {
                setFormError("Hay conflictos en el item. Elegí qué valor conservar antes de guardar.");
                return;
              }
              if (collaborativeItem.isDirty) {
                await collaborativeItem.save();
                onCollaborativeSaved();
              }
              return;
            }
            await onSave({
              name: collaborativeForm.name,
              sku: collaborativeForm.sku || null,
              unit: collaborativeForm.unit,
              min_quantity: collaborativeForm.min_quantity || null
            });
          } catch (error) {
            setFormError(error instanceof Error ? error.message : "No se pudo guardar el item.");
          }
        }}
      >
        <h2 id="edit-stock-item-title" className="text-base font-semibold text-slate-900">
          Editar item de stock
        </h2>
        {collaborationEnabled && collaborativeItem.status !== "idle" ? (
          <div className="mt-2 space-y-2 rounded-md border border-sky-200 bg-sky-50 px-2 py-1.5 text-xs text-sky-900" data-testid="stock-collaboration" role="status">
            <p>
              {collaborativeItem.status === "connected"
                ? `Coedición conectada${collaborativeItem.peers.length ? ` · ${collaborativeItem.peers.length} usuario(s) más` : ""}.`
                : collaborativeItem.status === "saving"
                  ? "Guardando y confirmando con el servidor..."
                  : collaborativeItem.status === "conflict"
                    ? "Hay un conflicto de edición."
                    : collaborativeItem.status === "degraded"
                      ? "Coedición degradada; podés usar el guardado normal."
                      : "Conectando coedición..."}
            </p>
            {Object.values(collaborativeItem.conflicts).map((conflict) => (
              <div key={conflict.field} className="rounded border border-amber-200 bg-amber-50 p-2 text-amber-950" data-testid={`stock-conflict-${conflict.field}`}>
                <p className="font-semibold">Conflicto en {conflict.field}</p>
                <p>Propio: {String(conflict.localValue ?? "(vacío)")}</p>
                <p>Remoto: {String(conflict.remoteValue ?? "(vacío)")}</p>
                <div className="mt-1 flex gap-2">
                  <button type="button" className="rounded border border-amber-300 bg-white px-2 py-1 font-semibold" onClick={() => collaborativeItem.keepMine(conflict.field)}>
                    Conservar el mío
                  </button>
                  <button type="button" className="rounded border border-amber-300 bg-white px-2 py-1 font-semibold" onClick={() => collaborativeItem.useRemote(conflict.field)}>
                    Usar remoto
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : null}
        {formError ? <p className="mt-2 rounded-md bg-rose-50 px-2 py-1 text-xs text-rose-800" role="alert">{formError}</p> : null}
        <div className="mt-4 space-y-3">
          <label className="block text-sm">
            <span className="block text-xs uppercase tracking-wide text-slate-500">Nombre</span>
            <input
              required
              value={collaborativeForm.name}
              onChange={(event) => setItemField("name", event.target.value)}
              onFocus={() => collaborativeItem.focusField("name")}
              onBlur={() => collaborativeItem.blurField("name")}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="block text-xs uppercase tracking-wide text-slate-500">SKU</span>
            <input
              value={collaborativeForm.sku}
              onChange={(event) => setItemField("sku", event.target.value)}
              onFocus={() => collaborativeItem.focusField("sku")}
              onBlur={() => collaborativeItem.blurField("sku")}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="block text-xs uppercase tracking-wide text-slate-500">Unidad</span>
            <input
              required
              value={collaborativeForm.unit}
              onChange={(event) => setItemField("unit", event.target.value)}
              onFocus={() => collaborativeItem.focusField("unit")}
              onBlur={() => collaborativeItem.blurField("unit")}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="block text-xs uppercase tracking-wide text-slate-500">Mínimo</span>
            <input
              type="number"
              min="0"
              step="0.01"
              value={collaborativeForm.min_quantity}
              onChange={(event) => setItemField("min_quantity", event.target.value)}
              onFocus={() => collaborativeItem.focusField("min_quantity")}
              onBlur={() => collaborativeItem.blurField("min_quantity")}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
        </div>
        <div className="mt-5 flex gap-2">
          <button
            type="button"
            onClick={handleCancel}
            className="min-h-11 flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={saving || collaborativeItem.isSaving}
            className="min-h-11 flex-1 rounded-lg border border-brand-600 bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
          >
            Guardar
          </button>
        </div>
      </form>
    </div>
  );
}
