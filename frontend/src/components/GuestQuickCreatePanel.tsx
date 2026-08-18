import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { hasValidSession } from "../api/client";
import { listGuests, type Guest, type GuestPayload } from "../api/guests";
import { useGuest, useGuestCreate } from "../hooks/useGuests";
import { useEffectivePermissions } from "../hooks/usePermissions";
import { useSession } from "../state/session";

import { GuestRestrictionBadge } from "./GuestRestrictionBadge";

// Shared "buscar huésped existente (por nombre/DNI) o alta rápida" sub-form.
// Used by both the direct "reserva rápida" create form and the "Cargar
// reserva de OTA" form (B4) -- same fields, same create-and-assign behavior,
// so this lives in one place instead of being copy-pasted per form.
//
// E1: this used to be a raw numeric "ID Huésped" text input -- the hotel
// owner has no way to know a guest's internal ID, and can't tell two guests
// with the same name apart (e.g. two "Lucas Fernández") without seeing more
// than a number. Replaced with the same search-by-name/DNI pattern already
// used in GuestsPage.tsx, plus a confirmation card (name/email/phone/DNI)
// before the guest is actually assigned to the reservation.
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

const GUEST_SEARCH_MIN_LENGTH = 2;
const GUEST_SEARCH_LIMIT = 8;
const GUEST_SEARCH_DEBOUNCE_MS = 300;

const guestFullName = (guest: Pick<Guest, "first_name" | "last_name">) =>
  `${guest.first_name} ${guest.last_name}`.trim();

function GuestSummaryCard({
  guest,
  onChange,
  changeLabel
}: {
  guest: Guest;
  onChange?: () => void;
  changeLabel?: string;
}) {
  return (
    <div
      className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm"
      data-testid="guest-confirm-card"
    >
      <p className="text-xs uppercase tracking-wide text-emerald-700">Huésped seleccionado</p>
      <p className="font-semibold text-emerald-900">
        {guestFullName(guest) || `Huésped #${guest.id}`}{" "}
        <span className="font-normal text-emerald-700">#{guest.id}</span>
      </p>
      <GuestRestrictionBadge guestId={guest.id} className="mt-1" />
      <dl className="mt-1 grid gap-x-3 gap-y-0.5 text-xs text-emerald-800 sm:grid-cols-2">
        <div>
          <dt className="inline font-medium">Email: </dt>
          <dd className="inline">{guest.email || "—"}</dd>
        </div>
        <div>
          <dt className="inline font-medium">Teléfono: </dt>
          <dd className="inline">{guest.phone || "—"}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="inline font-medium">Documento: </dt>
          <dd className="inline">
            {guest.document_number ? `${guest.document_type ?? ""} ${guest.document_number}`.trim() : "—"}
          </dd>
        </div>
      </dl>
      {onChange && (
        <button
          type="button"
          onClick={onChange}
          data-testid="guest-change-button"
          className="mt-2 text-xs font-semibold text-emerald-700 underline hover:text-emerald-900"
        >
          {changeLabel ?? "Buscar otro huésped"}
        </button>
      )}
    </div>
  );
}

export default function GuestQuickCreatePanel({
  guestId,
  onGuestIdChange,
  guestIdDisabled,
  form,
  onFormChange,
  onGuestCreated,
  onError
}: GuestQuickCreatePanelProps) {
  const { session } = useSession();
  const { hasPermission } = useEffectivePermissions();
  const canViewGuests = hasPermission("guest:view");
  const canCreateGuests = hasPermission("guest:create");
  const guestMutation = useGuestCreate();

  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [selectedGuest, setSelectedGuest] = useState<Guest | null>(null);
  const [pendingGuest, setPendingGuest] = useState<Guest | null>(null);
  const [showQuickCreate, setShowQuickCreate] = useState(false);

  useEffect(() => {
    const handle = setTimeout(() => setDebouncedQuery(query.trim()), GUEST_SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [query]);

  const searchEnabled =
    hasValidSession(session) && canViewGuests && !guestIdDisabled && !guestId && debouncedQuery.length >= GUEST_SEARCH_MIN_LENGTH;

  const searchQuery = useQuery({
    queryKey: ["guest-search", session.hotelId, debouncedQuery],
    queryFn: () => listGuests({ search: debouncedQuery, limit: GUEST_SEARCH_LIMIT }, session),
    enabled: searchEnabled,
    staleTime: 30 * 1000
  });

  // Covers both edit mode (guestIdDisabled, guestId came from the
  // reservation being edited) and any case where guestId is already set but
  // this component never fetched the full Guest object itself -- fetch it
  // by id so the card can show a name instead of a raw number.
  const needsFetch = canViewGuests && Boolean(guestId) && !selectedGuest;
  const fetchedGuestQuery = useGuest(needsFetch ? Number(guestId) : undefined);
  const confirmedGuest = selectedGuest ?? (needsFetch ? fetchedGuestQuery.data ?? null : null);

  const resetSearchState = () => {
    setQuery("");
    setDebouncedQuery("");
    setPendingGuest(null);
  };

  const handleConfirmPending = () => {
    if (!pendingGuest) return;
    setSelectedGuest(pendingGuest);
    onGuestIdChange(String(pendingGuest.id));
    resetSearchState();
  };

  const handleChangeGuest = () => {
    setSelectedGuest(null);
    onGuestIdChange("");
    resetSearchState();
    setShowQuickCreate(false);
  };

  const handleCreateGuest = () => {
    if (!canCreateGuests) return;
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
          setSelectedGuest(guest);
          onGuestIdChange(String(guest.id));
          onFormChange(emptyQuickGuestForm);
          setShowQuickCreate(false);
          onGuestCreated(guest.id);
        },
        onError: (err: unknown) => onError(err instanceof Error ? err.message : "No se pudo crear el huésped")
      }
    );
  };

  const results = searchQuery.data ?? [];

  return (
    <div className="space-y-3 sm:col-span-2">
      <p className="text-xs font-semibold text-slate-600">Huésped</p>

      {guestId ? (
        confirmedGuest ? (
          <GuestSummaryCard
            guest={confirmedGuest}
            onChange={guestIdDisabled ? undefined : handleChangeGuest}
          />
        ) : (
          <p className="text-xs text-slate-500">Cargando huésped #{guestId}...</p>
        )
      ) : pendingGuest ? (
        <div className="space-y-2">
          <GuestSummaryCard guest={pendingGuest} />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleConfirmPending}
              data-testid="guest-confirm-button"
              className="rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100"
            >
              Confirmar
            </button>
            <button
              type="button"
              onClick={() => setPendingGuest(null)}
              data-testid="guest-search-again-button"
              className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"
            >
              Buscar otro
            </button>
          </div>
        </div>
      ) : showQuickCreate && canCreateGuests && !guestIdDisabled ? (
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
            <span>Se asigna automáticamente al huésped de la reserva.</span>
            <button
              type="button"
              onClick={() => setShowQuickCreate(false)}
              data-testid="guest-quick-create-toggle"
              className="font-semibold text-brand-700 underline hover:text-brand-800"
            >
              Volver a buscar
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={guestIdDisabled}
            placeholder="Buscar por nombre, documento o email"
            aria-label="Buscar huésped"
            data-testid="guest-search-input"
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
          />
          {debouncedQuery.length >= GUEST_SEARCH_MIN_LENGTH &&
            (searchQuery.isLoading ? (
              <p className="text-xs text-slate-500">Buscando...</p>
            ) : results.length > 0 ? (
              <div
                className="max-h-56 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-200"
                data-testid="guest-search-results"
              >
                {results.map((guest) => (
                  <button
                    key={guest.id}
                    type="button"
                    onClick={() => setPendingGuest(guest)}
                    data-testid={`guest-search-result-${guest.id}`}
                    className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50"
                  >
                    <p className="font-medium text-slate-900">{guestFullName(guest) || `Huésped #${guest.id}`}</p>
                    <p className="text-xs text-slate-500">
                      {guest.document_number || "Sin documento"}
                      {guest.email ? ` · ${guest.email}` : ""}
                    </p>
                    <GuestRestrictionBadge guestId={guest.id} className="mt-1" />
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">No se encontraron huéspedes para "{debouncedQuery}".</p>
            ))}
          {!guestIdDisabled && canCreateGuests && (
            <button
              type="button"
              onClick={() => setShowQuickCreate(true)}
              data-testid="guest-quick-create-toggle"
              className="text-xs font-semibold text-brand-700 underline hover:text-brand-800"
            >
              ¿No lo encontrás? Crear huésped nuevo
            </button>
          )}
          {!canViewGuests && !canCreateGuests && (
            <p className="text-xs text-slate-500">No tenés permisos para consultar ni crear huéspedes.</p>
          )}
        </div>
      )}
    </div>
  );
}
