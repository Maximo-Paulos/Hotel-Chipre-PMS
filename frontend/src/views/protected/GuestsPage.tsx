import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import React, { useEffect, useMemo, useState } from "react";

import { hasValidSession } from "../../api/client";
import {
  addGuestTag,
  checkInGuestReservation,
  getGuestQuickProfile,
  listGuestTags,
  resolveGuestTag,
  type GuestCompanionPayload,
  type GuestTag,
  type GuestTagPayload,
  type GuestTagType,
  type GuestUpdatePayload
} from "../../api/guests";
import { GUEST_PAGE_SIZE, useGuestCompanionAdd, useGuestUpdate, useGuests } from "../../hooks/useGuests";
import { useReservationDrawer } from "../../hooks/useReservationDrawer";
import { useSession } from "../../state/session";

const DOCUMENT_TYPES = ["DNI", "PASSPORT", "CEDULA"] as const;

const TAG_OPTIONS: Array<{ value: GuestTagType; label: string }> = [
  { value: "prohibido_alojar", label: "Prohibido alojar" },
  { value: "requiere_deposito", label: "Requiere depósito" },
  { value: "no_pago", label: "No pagó" },
  { value: "conflictivo", label: "Conflictivo" },
  { value: "robo", label: "Robo" },
  { value: "robo_cosas", label: "Rompió cosas" },
  { value: "vip", label: "VIP" },
  { value: "alergias", label: "Alergias" },
  { value: "otro", label: "Otro" }
];

const tagLabels = TAG_OPTIONS.reduce<Record<GuestTagType, string>>((acc, option) => {
  acc[option.value] = option.label;
  return acc;
}, {} as Record<GuestTagType, string>);

const emptyForm: GuestUpdatePayload = {
  first_name: "",
  last_name: "",
  date_of_birth: "",
  email: "",
  phone: "",
  document_type: undefined,
  document_number: "",
  nationality: "",
  city: "",
  country: "",
  address_line1: "",
  observations: ""
};

const emptyCompanion: GuestCompanionPayload = {
  first_name: "",
  last_name: "",
  document_type: "DNI",
  document_number: "",
  nationality: "",
  date_of_birth: "",
  relationship_to_guest: ""
};

const emptyTagForm: GuestTagPayload = {
  tag_type: "prohibido_alojar",
  note: "",
  expires_at: ""
};

const canCheckInStatus = (status: string) => ["fully_paid", "pre_check_in"].includes(status);

const formatStatus = (status: string) =>
  status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const formatDate = (value?: string | null) => {
  if (!value) return "Sin fecha";
  return new Date(value).toLocaleDateString("es-AR");
};

const isProhibidoTag = (tag: GuestTag) => tag.tag_type === "prohibido_alojar";

export function GuestsPage() {
  const { session } = useSession();
  const { openReservation } = useReservationDrawer();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  // A5: the backend already paginated (app/api/guests.py:114-130) but the
  // frontend never sent skip/limit, so a hotel with >50 guests only ever
  // saw the first 50 with no indication more existed.
  const [page, setPage] = useState(0);
  const [selectedGuestId, setSelectedGuestId] = useState<number | null>(null);
  const [formValues, setFormValues] = useState<GuestUpdatePayload>(emptyForm);
  const [companionValues, setCompanionValues] = useState<GuestCompanionPayload>(emptyCompanion);
  const [tagValues, setTagValues] = useState<GuestTagPayload>(emptyTagForm);
  const [formMessage, setFormMessage] = useState<string | null>(null);
  const [companionMessage, setCompanionMessage] = useState<string | null>(null);
  const [tagMessage, setTagMessage] = useState<string | null>(null);
  const [checkInMessage, setCheckInMessage] = useState<string | null>(null);
  const guestsQuery = useGuests(search, page);
  const updateGuestMutation = useGuestUpdate();
  const addCompanionMutation = useGuestCompanionAdd();
  const guests = useMemo(() => guestsQuery.data ?? [], [guestsQuery.data]);
  // No exact total from the backend (deliberate -- see api/guests.ts):
  // a full page is the only signal that a next page might exist.
  const hasNextPage = guests.length === GUEST_PAGE_SIZE;

  const handleSearchChange = (value: string) => {
    setSearch(value);
    setPage(0);
  };

  const selectedGuest = useMemo(
    () => guests.find((guest) => guest.id === selectedGuestId) ?? guests[0] ?? null,
    [guests, selectedGuestId]
  );

  const tagsQuery = useQuery({
    queryKey: ["guest-tags", session.hotelId, selectedGuest?.id],
    queryFn: () => listGuestTags(selectedGuest!.id, session),
    enabled: Boolean(selectedGuest?.id) && hasValidSession(session),
    staleTime: 30 * 1000
  });

  const quickProfileQuery = useQuery({
    queryKey: ["guest-quick-profile", session.hotelId, selectedGuest?.id],
    queryFn: () => getGuestQuickProfile(selectedGuest!.id, session),
    enabled: Boolean(selectedGuest?.id) && hasValidSession(session),
    staleTime: 30 * 1000
  });

  const invalidateGuestOperationalData = async (guestId: number) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["guests", session.hotelId] }),
      queryClient.invalidateQueries({ queryKey: ["guest", session.hotelId, guestId] }),
      queryClient.invalidateQueries({ queryKey: ["guest-tags", session.hotelId, guestId] }),
      queryClient.invalidateQueries({ queryKey: ["guest-quick-profile", session.hotelId, guestId] })
    ]);
  };

  const addTagMutation = useMutation({
    mutationFn: ({ guestId, payload }: { guestId: number; payload: GuestTagPayload }) =>
      addGuestTag(guestId, payload, session),
    onSuccess: async (_, variables) => invalidateGuestOperationalData(variables.guestId)
  });

  const resolveTagMutation = useMutation({
    mutationFn: ({ guestId, tagId }: { guestId: number; tagId: number }) => resolveGuestTag(guestId, tagId, session),
    onSuccess: async (_, variables) => invalidateGuestOperationalData(variables.guestId)
  });

  const checkInMutation = useMutation({
    mutationFn: ({ reservationId, override }: { reservationId: number; override: boolean }) =>
      checkInGuestReservation(reservationId, { override_prohibido: override }, session),
    onSuccess: async (_, variables) => {
      if (selectedGuest?.id) {
        await invalidateGuestOperationalData(selectedGuest.id);
      }
      await queryClient.invalidateQueries({ queryKey: ["reservations", session.hotelId] });
      await queryClient.invalidateQueries({ queryKey: ["reservation", session.hotelId, variables.reservationId] });
    }
  });

  useEffect(() => {
    if (!selectedGuest) {
      setSelectedGuestId(null);
      setFormValues(emptyForm);
      setCompanionValues(emptyCompanion);
      setTagValues(emptyTagForm);
      return;
    }

    setSelectedGuestId(selectedGuest.id);
    setFormValues({
      first_name: selectedGuest.first_name,
      last_name: selectedGuest.last_name,
      date_of_birth: selectedGuest.date_of_birth ?? "",
      email: selectedGuest.email ?? "",
      phone: selectedGuest.phone ?? "",
      document_type: selectedGuest.document_type ?? undefined,
      document_number: selectedGuest.document_number ?? "",
      nationality: selectedGuest.nationality ?? "",
      city: selectedGuest.city ?? "",
      country: selectedGuest.country ?? "",
      address_line1: selectedGuest.address_line1 ?? "",
      observations: selectedGuest.observations ?? ""
    });
    setCompanionValues(emptyCompanion);
    setTagValues(emptyTagForm);
    setFormMessage(null);
    setCompanionMessage(null);
    setTagMessage(null);
    setCheckInMessage(null);
  }, [selectedGuest]);

  const activeTags = tagsQuery.data ?? quickProfileQuery.data?.active_tags ?? [];
  const hasProhibido = activeTags.some(isProhibidoTag);
  // C4: real permission gate (bypasses a legal/compliance block on check-in),
  // reads baseRole -- not the "Cambiar vista" preview role -- so previewing
  // as a lower role can't hide it from the real owner/manager, and a
  // manipulated localStorage role can't reveal it to someone who isn't.
  const canOverrideProhibido = ["owner", "co_owner", "manager"].includes(session.baseRole ?? "");
  const companions = selectedGuest?.companions ?? [];
  const lastStays = quickProfileQuery.data?.last_stays ?? [];

  const handleChange = (field: keyof GuestUpdatePayload, value: string) => {
    setFormValues((current) => ({ ...current, [field]: value }));
  };

  const handleCompanionChange = (field: keyof GuestCompanionPayload, value: string) => {
    setCompanionValues((current) => ({ ...current, [field]: value }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedGuestId) return;
    setFormMessage(null);
    try {
      const payload: GuestUpdatePayload = {
        ...formValues,
        document_type: formValues.document_type || undefined,
        date_of_birth: formValues.date_of_birth || undefined
      };
      await updateGuestMutation.mutateAsync({ guestId: selectedGuestId, payload });
      setFormMessage("Huésped guardado.");
    } catch (error) {
      setFormMessage(error instanceof Error ? error.message : "No se pudo guardar el huésped.");
    }
  };

  const handleCompanionSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedGuestId) return;
    setCompanionMessage(null);
    try {
      const payload: GuestCompanionPayload = {
        ...companionValues,
        date_of_birth: companionValues.date_of_birth || undefined
      };
      await addCompanionMutation.mutateAsync({ guestId: selectedGuestId, companions: [payload] });
      setCompanionMessage("Acompañante guardado.");
      setCompanionValues(emptyCompanion);
      await guestsQuery.refetch();
    } catch (error) {
      setCompanionMessage(error instanceof Error ? error.message : "No se pudo guardar el acompañante.");
    }
  };

  const handleTagSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedGuestId) return;
    setTagMessage(null);
    try {
      await addTagMutation.mutateAsync({
        guestId: selectedGuestId,
        payload: {
          tag_type: tagValues.tag_type,
          note: tagValues.note?.trim() || null,
          expires_at: tagValues.expires_at || null
        }
      });
      setTagValues(emptyTagForm);
      setTagMessage("Etiqueta agregada.");
    } catch (error) {
      setTagMessage(error instanceof Error ? error.message : "No se pudo agregar la etiqueta.");
    }
  };

  const handleResolveTag = async (tagId: number) => {
    if (!selectedGuestId) return;
    setTagMessage(null);
    try {
      await resolveTagMutation.mutateAsync({ guestId: selectedGuestId, tagId });
      setTagMessage("Etiqueta resuelta.");
    } catch (error) {
      setTagMessage(error instanceof Error ? error.message : "No se pudo resolver la etiqueta.");
    }
  };

  const handleCheckIn = async (reservationId: number, override: boolean) => {
    setCheckInMessage(null);
    try {
      await checkInMutation.mutateAsync({ reservationId, override });
      setCheckInMessage(override ? "Check-in realizado con override autorizado." : "Check-in realizado.");
    } catch (error) {
      setCheckInMessage(error instanceof Error ? error.message : "No se pudo realizar el check-in.");
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Huéspedes</p>
          <h1 className="text-2xl font-semibold text-slate-900">Ficha de huéspedes</h1>
          <p className="text-sm text-slate-600">
            Buscá por nombre, documento o email y mantené actualizado el registro operativo.
          </p>
        </div>
        <div className="w-full max-w-sm">
          <input
            type="search"
            value={search}
            onChange={(event) => handleSearchChange(event.target.value)}
            placeholder="Buscar por nombre, documento o email"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
          />
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-4 py-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Listado</p>
            <h2 className="text-lg font-semibold text-slate-900">Huéspedes del hotel</h2>
          </div>
          <div className="max-h-[65vh] overflow-y-auto">
            {guestsQuery.isLoading ? (
              <p className="px-4 py-3 text-sm text-slate-500">Cargando huéspedes...</p>
            ) : guests.length === 0 ? (
              <p className="px-4 py-3 text-sm text-slate-500">No hay huéspedes para el filtro actual.</p>
            ) : (
              <div className="divide-y divide-slate-200">
                {guests.map((guest) => {
                  const isActive = guest.id === selectedGuest?.id;
                  const fullName = `${guest.first_name} ${guest.last_name}`.trim();
                  return (
                    <button
                      key={guest.id}
                      type="button"
                      onClick={() => setSelectedGuestId(guest.id)}
                      className={`w-full px-4 py-3 text-left hover:bg-slate-50 ${isActive ? "bg-brand-50" : "bg-white"}`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-slate-900">{fullName || `Huésped #${guest.id}`}</p>
                          <p className="text-xs text-slate-500">
                            {guest.document_number || guest.email || guest.phone || "Sin documento ni contacto"}
                          </p>
                        </div>
                        <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-semibold text-slate-600">
                          #{guest.id}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
          <div className="flex items-center justify-between gap-2 border-t border-slate-200 px-4 py-3">
            <span className="text-xs text-slate-500" data-testid="guests-page-indicator">
              Página {page + 1}
              {guestsQuery.isFetching ? " · Actualizando..." : ""}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                data-testid="guests-prev-page"
                onClick={() => setPage((current) => Math.max(0, current - 1))}
                disabled={page === 0 || guestsQuery.isFetching}
                className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                ← Anterior
              </button>
              <button
                type="button"
                data-testid="guests-next-page"
                onClick={() => setPage((current) => current + 1)}
                disabled={!hasNextPage || guestsQuery.isFetching}
                className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Siguiente →
              </button>
            </div>
          </div>
        </section>

        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          {selectedGuest ? (
            <>
              <form className="space-y-4" onSubmit={handleSubmit}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">Ficha operativa</p>
                    <h2 className="text-lg font-semibold text-slate-900">
                      {selectedGuest.first_name} {selectedGuest.last_name}
                    </h2>
                    <p className="text-xs text-slate-500">
                      Actualizado{" "}
                      {selectedGuest.updated_at ? new Date(selectedGuest.updated_at).toLocaleString("es-AR") : "sin fecha"}
                    </p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                    ID {selectedGuest.id}
                  </span>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Nombre</span>
                    <input
                      value={formValues.first_name ?? ""}
                      onChange={(e) => handleChange("first_name", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Apellido</span>
                    <input
                      value={formValues.last_name ?? ""}
                      onChange={(e) => handleChange("last_name", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Fecha de nacimiento</span>
                    <input
                      type="date"
                      value={formValues.date_of_birth ?? ""}
                      onChange={(e) => handleChange("date_of_birth", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Email</span>
                    <input
                      value={formValues.email ?? ""}
                      onChange={(e) => handleChange("email", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Teléfono</span>
                    <input
                      value={formValues.phone ?? ""}
                      onChange={(e) => handleChange("phone", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Tipo de documento</span>
                    <select
                      value={formValues.document_type ?? ""}
                      onChange={(e) => handleChange("document_type", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    >
                      <option value="">Seleccionar</option>
                      {DOCUMENT_TYPES.map((type) => (
                        <option key={type} value={type}>
                          {type}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Número de documento</span>
                    <input
                      value={formValues.document_number ?? ""}
                      onChange={(e) => handleChange("document_number", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Nacionalidad</span>
                    <input
                      value={formValues.nationality ?? ""}
                      onChange={(e) => handleChange("nationality", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Ciudad</span>
                    <input
                      value={formValues.city ?? ""}
                      onChange={(e) => handleChange("city", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm md:col-span-2">
                    <span className="text-slate-600">Dirección</span>
                    <input
                      value={formValues.address_line1 ?? ""}
                      onChange={(e) => handleChange("address_line1", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm md:col-span-2">
                    <span className="text-slate-600">Observaciones</span>
                    <textarea
                      value={formValues.observations ?? ""}
                      onChange={(e) => handleChange("observations", e.target.value)}
                      rows={4}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                </div>

                {formMessage ? (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                    {formMessage}
                  </div>
                ) : null}

                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={updateGuestMutation.isPending}
                    className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                  >
                    Guardar huésped
                  </button>
                </div>
              </form>

              <section className="space-y-4 border-t border-slate-200 pt-4">
                <div className="flex flex-col gap-1">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Etiquetas</p>
                  <h3 className="text-base font-semibold text-slate-900">Alertas y segmentación</h3>
                  {hasProhibido ? (
                    <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-800">
                      Este huésped tiene una etiqueta activa de prohibido alojar. El check-in queda bloqueado salvo override autorizado.
                    </p>
                  ) : null}
                </div>

                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  {tagsQuery.isLoading ? (
                    <p className="text-sm text-slate-500">Cargando etiquetas...</p>
                  ) : activeTags.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {activeTags.map((tag) => (
                        <div
                          key={tag.id}
                          className={`flex max-w-full items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${
                            isProhibidoTag(tag)
                              ? "border-red-200 bg-red-50 text-red-800"
                              : "border-slate-200 bg-white text-slate-700"
                          }`}
                        >
                          <span>{tagLabels[tag.tag_type] ?? tag.tag_type}</span>
                          {tag.note ? <span className="truncate font-normal text-slate-500">- {tag.note}</span> : null}
                          <button
                            type="button"
                            onClick={() => handleResolveTag(tag.id)}
                            disabled={resolveTagMutation.isPending}
                            className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-600 hover:bg-slate-100 disabled:opacity-60"
                          >
                            Resolver
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">Sin etiquetas activas.</p>
                  )}
                </div>

                <form className="grid gap-4 md:grid-cols-[220px_minmax(0,1fr)_180px_auto]" onSubmit={handleTagSubmit}>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Etiqueta</span>
                    <select
                      value={tagValues.tag_type}
                      onChange={(e) => setTagValues((current) => ({ ...current, tag_type: e.target.value as GuestTagType }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    >
                      {TAG_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Nota</span>
                    <input
                      value={tagValues.note ?? ""}
                      onChange={(e) => setTagValues((current) => ({ ...current, note: e.target.value }))}
                      placeholder="Detalle operativo"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Vence</span>
                    <input
                      type="datetime-local"
                      value={tagValues.expires_at ?? ""}
                      onChange={(e) => setTagValues((current) => ({ ...current, expires_at: e.target.value }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <div className="flex items-end">
                    <button
                      type="submit"
                      disabled={addTagMutation.isPending}
                      className="w-full rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                    >
                      Agregar
                    </button>
                  </div>
                  {tagMessage ? (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 md:col-span-4">
                      {tagMessage}
                    </div>
                  ) : null}
                </form>
              </section>

              <section className="space-y-4 border-t border-slate-200 pt-4">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Check-in</p>
                  <h3 className="text-base font-semibold text-slate-900">Últimas estadías</h3>
                </div>

                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  {quickProfileQuery.isLoading ? (
                    <p className="text-sm text-slate-500">Cargando estadías...</p>
                  ) : lastStays.length > 0 ? (
                    <div className="space-y-2">
                      {lastStays.map((stay) => {
                        const canCheckIn = canCheckInStatus(String(stay.status));
                        return (
                          <div key={stay.reservation_id} className="rounded-md bg-white px-3 py-2 text-sm shadow-sm">
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                              <div>
                                <p className="font-semibold text-slate-900">
                                  Reserva{" "}
                                  <button
                                    type="button"
                                    onClick={() => openReservation(stay.reservation_id)}
                                    className="text-brand-700 hover:underline"
                                  >
                                    {stay.confirmation_code}
                                  </button>{" "}
                                  · {formatStatus(String(stay.status))}
                                </p>
                                <p className="text-xs text-slate-500">
                                  {formatDate(stay.check_in_date)} a {formatDate(stay.check_out_date)}
                                  {stay.room_number ? ` · Hab. ${stay.room_number}` : ""}
                                </p>
                              </div>
                              {canCheckIn ? (
                                <div className="flex flex-wrap gap-2">
                                  <button
                                    type="button"
                                    onClick={() => handleCheckIn(stay.reservation_id, false)}
                                    disabled={checkInMutation.isPending || hasProhibido}
                                    className="rounded-lg border border-brand-200 bg-brand-600 px-3 py-2 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                                  >
                                    Check-in
                                  </button>
                                  {hasProhibido && canOverrideProhibido ? (
                                    <button
                                      type="button"
                                      onClick={() => handleCheckIn(stay.reservation_id, true)}
                                      disabled={checkInMutation.isPending}
                                      className="rounded-lg border border-red-200 bg-red-600 px-3 py-2 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-60"
                                    >
                                      Override prohibido
                                    </button>
                                  ) : null}
                                </div>
                              ) : null}
                            </div>
                            {hasProhibido && canCheckIn && !canOverrideProhibido ? (
                              <p className="mt-2 text-xs font-medium text-red-700">
                                Solo manager, owner o co-owner pueden autorizar el override.
                              </p>
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">Sin estadías recientes para este huésped.</p>
                  )}
                </div>

                {checkInMessage ? (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                    {checkInMessage}
                  </div>
                ) : null}
              </section>

              <section className="space-y-4 border-t border-slate-200 pt-4">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Acompañantes</p>
                  <h3 className="text-base font-semibold text-slate-900">Personas asociadas a la estadía</h3>
                </div>

                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  {companions.length > 0 ? (
                    <div className="space-y-2">
                      {companions.map((companion) => (
                        <div
                          key={companion.id ?? `${companion.first_name}-${companion.last_name}`}
                          className="rounded-md bg-white px-3 py-2 text-sm shadow-sm"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-semibold text-slate-900">
                              {companion.first_name} {companion.last_name}
                            </p>
                            <span className="text-xs text-slate-500">
                              {companion.relationship_to_guest || "relación pendiente"}
                            </span>
                          </div>
                          <p className="text-xs text-slate-500">
                            {companion.document_type || "Sin documento"}{" "}
                            {companion.document_number ? `- ${companion.document_number}` : ""}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">Sin acompañantes registrados.</p>
                  )}
                </div>

                <form className="grid gap-4 md:grid-cols-2" onSubmit={handleCompanionSubmit}>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Nombre</span>
                    <input
                      value={companionValues.first_name ?? ""}
                      onChange={(e) => handleCompanionChange("first_name", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Apellido</span>
                    <input
                      value={companionValues.last_name ?? ""}
                      onChange={(e) => handleCompanionChange("last_name", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Fecha de nacimiento</span>
                    <input
                      type="date"
                      value={companionValues.date_of_birth ?? ""}
                      onChange={(e) => handleCompanionChange("date_of_birth", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Relación</span>
                    <input
                      value={companionValues.relationship_to_guest ?? ""}
                      onChange={(e) => handleCompanionChange("relationship_to_guest", e.target.value)}
                      placeholder="hijo, pareja, tutor..."
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Tipo de documento</span>
                    <select
                      value={companionValues.document_type ?? ""}
                      onChange={(e) => handleCompanionChange("document_type", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    >
                      {DOCUMENT_TYPES.map((type) => (
                        <option key={type} value={type}>
                          {type}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Número de documento</span>
                    <input
                      value={companionValues.document_number ?? ""}
                      onChange={(e) => handleCompanionChange("document_number", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm md:col-span-2">
                    <span className="text-slate-600">Nacionalidad</span>
                    <input
                      value={companionValues.nationality ?? ""}
                      onChange={(e) => handleCompanionChange("nationality", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>

                  {companionMessage ? (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 md:col-span-2">
                      {companionMessage}
                    </div>
                  ) : null}

                  <div className="flex justify-end md:col-span-2">
                    <button
                      type="submit"
                      disabled={addCompanionMutation.isPending}
                      className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                    >
                      Agregar acompañante
                    </button>
                  </div>
                </form>
              </section>
            </>
          ) : (
            <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-500">
              Seleccioná un huésped para abrir la ficha.
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
