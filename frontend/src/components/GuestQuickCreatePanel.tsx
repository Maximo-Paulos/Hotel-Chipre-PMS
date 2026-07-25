import { type GuestPayload } from "../api/guests";
import { useGuestCreate } from "../hooks/useGuests";

// Shared "buscar huésped existente (por ID) o alta rápida" sub-form. Used by
// both the direct "reserva rápida" create form and the "Cargar reserva de
// OTA" form (B4) -- same fields, same create-and-assign behavior, so this
// lives in one place instead of being copy-pasted per form.
export type QuickGuestFormValues = {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  document_type: NonNullable<GuestPayload["document_type"]>;
  document_number: string;
};

export const emptyQuickGuestForm = (): QuickGuestFormValues => ({
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  document_type: "DNI",
  document_number: ""
});

export const hasQuickGuestFormData = (form: QuickGuestFormValues) =>
  form.first_name.trim() !== "" ||
  form.last_name.trim() !== "" ||
  form.email.trim() !== "" ||
  form.phone.trim() !== "" ||
  form.document_number.trim() !== "";

type GuestQuickCreatePanelProps = {
  guestId: string;
  onGuestIdChange: (value: string) => void;
  guestIdDisabled?: boolean;
  form: QuickGuestFormValues;
  onFormChange: (updater: (prev: QuickGuestFormValues) => QuickGuestFormValues) => void;
  onGuestCreated: (guestId: number) => void;
  onError: (message: string) => void;
};

export default function GuestQuickCreatePanel({
  guestId,
  onGuestIdChange,
  guestIdDisabled,
  form,
  onFormChange,
  onGuestCreated,
  onError
}: GuestQuickCreatePanelProps) {
  const guestMutation = useGuestCreate();

  const handleCreateGuest = () => {
    guestMutation.mutate(
      {
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        email: form.email.trim() || undefined,
        phone: form.phone.trim() || undefined,
        document_type: form.document_type,
        document_number: form.document_number.trim() || undefined,
        terms_accepted: true
      },
      {
        onSuccess: (guest) => {
          onGuestIdChange(String(guest.id));
          onFormChange(emptyQuickGuestForm);
          onGuestCreated(guest.id);
        },
        onError: (err: unknown) => onError(err instanceof Error ? err.message : "No se pudo crear el huésped")
      }
    );
  };

  return (
    <div className="space-y-3 sm:col-span-2">
      <label className="block text-xs font-semibold text-slate-600 sm:max-w-xs">
        ID Huésped
        <input
          type="number"
          min={1}
          placeholder="Ej: 12 (deja vacío y usa Huésped rápido)"
          value={guestId}
          onChange={(e) => onGuestIdChange(e.target.value)}
          disabled={guestIdDisabled}
          className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
        />
      </label>

      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Huésped rápido</p>
            <p className="text-xs text-slate-600">Creá y asigná sin salir del formulario.</p>
          </div>
          {guestMutation.isPending && <span className="text-xs text-slate-500">Guardando...</span>}
        </div>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
          <input
            placeholder="Nombre"
            value={form.first_name}
            onChange={(e) => onFormChange((prev) => ({ ...prev, first_name: e.target.value }))}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
          />
          <input
            placeholder="Apellido"
            value={form.last_name}
            onChange={(e) => onFormChange((prev) => ({ ...prev, last_name: e.target.value }))}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
          />
          <input
            placeholder="Email"
            value={form.email}
            onChange={(e) => onFormChange((prev) => ({ ...prev, email: e.target.value }))}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
          />
          <input
            placeholder="Teléfono"
            value={form.phone}
            onChange={(e) => onFormChange((prev) => ({ ...prev, phone: e.target.value }))}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
          />
          <label className="text-xs font-semibold text-slate-600">
            Tipo de documento
            <select
              aria-label="Tipo de documento"
              value={form.document_type}
              onChange={(e) =>
                onFormChange((prev) => ({
                  ...prev,
                  document_type: e.target.value as NonNullable<GuestPayload["document_type"]>
                }))
              }
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
            >
              <option value="DNI">DNI</option>
              <option value="PASSPORT">Pasaporte</option>
              <option value="CEDULA">Cédula</option>
            </select>
          </label>
          <input
            placeholder="Documento"
            value={form.document_number}
            onChange={(e) => onFormChange((prev) => ({ ...prev, document_number: e.target.value }))}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
          />
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-600">
          <button
            type="button"
            onClick={handleCreateGuest}
            disabled={guestMutation.isPending || !form.first_name || !form.last_name}
            className="rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Crear Huésped y asignar ID
          </button>
          <span>Se asigna automáticamente al campo ID Huésped</span>
        </div>
      </div>
    </div>
  );
}
