import { useQuery, useQueryClient } from "@tanstack/react-query";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

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
import type { RestrictionOverride } from "../../api/guestRestrictions";
import { GuestRestrictionBadge } from "../../components/GuestRestrictionBadge";
import { GuestRestrictionsPanel } from "../../components/GuestRestrictionsPanel";
import { RestrictionOverrideModal } from "../../components/RestrictionOverrideModal";
import { GUEST_PAGE_SIZE, useGuestCompanionAdd, useGuestUpdate, useGuests } from "../../hooks/useGuests";
import { useEffectivePermissions } from "../../hooks/usePermissions";
import { useReservationDrawer } from "../../hooks/useReservationDrawer";
import { useRestrictionOverridePrompt } from "../../hooks/useRestrictionOverridePrompt";
import { useSession } from "../../state/session";
import { useCollaborativeResource } from "../../hooks/useCollaborativeResource";
import { refreshAfterMutation, refreshGuestState } from "../../api/queryInvalidation";
import { useGuardedMutation } from "../../hooks/useGuardedMutation";

const DOCUMENT_TYPES = ["DNI", "PASSPORT", "CEDULA"] as const;

const TAG_OPTIONS: Array<{ value: GuestTagType }> = [
  { value: "prohibido_alojar" },
  { value: "requiere_deposito" },
  { value: "no_pago" },
  { value: "conflictivo" },
  { value: "robo" },
  { value: "robo_cosas" },
  { value: "vip" },
  { value: "alergias" },
  { value: "otro" }
];

// ponytail: tag labels resolved via t(`tags.types.${value}`) at render time
// instead of a precomputed map -- one lookup path, and unknown tag types
// still render (via i18next's defaultValue) instead of needing a fallback.

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

const formatDate = (value: string | null | undefined, t: TFunction) => {
  if (!value) return t("checkIn.noDate");
  return new Date(value).toLocaleDateString("es-AR");
};

const isProhibidoTag = (tag: GuestTag) => tag.tag_type === "prohibido_alojar";

export function GuestsPage() {
  const { t } = useTranslation("guests");
  const { session } = useSession();
  const { hasPermission } = useEffectivePermissions();
  const canEditGuest = hasPermission("guest:update");
  const canManageTags = hasPermission("guest:tags_manage");
  const canCheckIn = hasPermission("checkin:perform");
  const canOverrideProhibido = hasPermission("reservation:prohibition_override");
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
  const initializedGuestIdRef = useRef<number | null>(null);
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

  const collaborativeGuest = useCollaborativeResource({
    resourceType: "guest",
    resourceId: selectedGuest?.id,
    initialValues: selectedGuest
      ? {
          first_name: selectedGuest.first_name,
          last_name: selectedGuest.last_name,
          document_type: selectedGuest.document_type ?? null,
          document_number: selectedGuest.document_number ?? null,
          nationality: selectedGuest.nationality ?? null,
          date_of_birth: selectedGuest.date_of_birth ?? null,
          email: selectedGuest.email ?? null,
          phone: selectedGuest.phone ?? null,
          address_line1: selectedGuest.address_line1 ?? null,
          city: selectedGuest.city ?? null,
          country: selectedGuest.country ?? null,
          observations: selectedGuest.observations ?? null
        }
      : null,
    enabled: Boolean(selectedGuest && canEditGuest)
  });

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

  const invalidateGuestOperationalData = (guestId: number) => refreshGuestState(queryClient, session.hotelId, guestId);

  const addTagMutation = useGuardedMutation({
    mutationFn: ({ guestId, payload }: { guestId: number; payload: GuestTagPayload }) =>
      addGuestTag(guestId, payload, session),
    onSuccess: async (_, variables) => invalidateGuestOperationalData(variables.guestId)
  });

  const resolveTagMutation = useGuardedMutation({
    mutationFn: ({ guestId, tagId }: { guestId: number; tagId: number }) => resolveGuestTag(guestId, tagId, session),
    onSuccess: async (_, variables) => invalidateGuestOperationalData(variables.guestId)
  });

  const restrictionOverridePrompt = useRestrictionOverridePrompt();

  const checkInMutation = useGuardedMutation({
    mutationFn: ({
      reservationId,
      override,
      restrictionOverride
    }: {
      reservationId: number;
      override: boolean;
      restrictionOverride?: RestrictionOverride | null;
    }) =>
      checkInGuestReservation(
        reservationId,
        { override_prohibido: override, restriction_override: restrictionOverride ?? undefined },
        session
      ),
    onSuccess: async (_, variables) => {
      await refreshAfterMutation(queryClient, session.hotelId, ["guests", "reservations", "rooms", "payments", "cash", "analytics"]);
      void variables;
    }
  });

  useEffect(() => {
    if (!selectedGuest) {
      initializedGuestIdRef.current = null;
      setSelectedGuestId(null);
      setFormValues(emptyForm);
      setCompanionValues(emptyCompanion);
      setTagValues(emptyTagForm);
      return;
    }

    // Query invalidation replaces the selected guest object even when the
    // operator is still editing the same record. Reinitialize only when the
    // selected identity changes so save/tag feedback is not erased by a
    // successful background refresh.
    if (initializedGuestIdRef.current === selectedGuest.id) return;
    initializedGuestIdRef.current = selectedGuest.id;

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
  const companions = selectedGuest?.companions ?? [];
  const lastStays = quickProfileQuery.data?.last_stays ?? [];

  const collaborativeGuestValues: GuestUpdatePayload = selectedGuest
    ? Object.keys(formValues).reduce<GuestUpdatePayload>((values, field) => {
        const draftValue = collaborativeGuest.draftValues[field];
        values[field as keyof GuestUpdatePayload] = (draftValue === undefined ? formValues[field as keyof GuestUpdatePayload] : draftValue) as never;
        return values;
      }, { ...formValues })
    : formValues;

  const handleChange = (field: keyof GuestUpdatePayload, value: string) => {
    setFormValues((current) => ({ ...current, [field]: value }));
    if (selectedGuest) {
      const normalizedValue = field === "document_type" || field === "date_of_birth" ? value || null : value;
      collaborativeGuest.setField(field, normalizedValue);
    }
  };

  const handleCompanionChange = (field: keyof GuestCompanionPayload, value: string) => {
    setCompanionValues((current) => ({ ...current, [field]: value }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedGuestId || !canEditGuest) return;
    setFormMessage(null);
    try {
      const payload: GuestUpdatePayload = {
        ...collaborativeGuestValues,
        document_type: collaborativeGuestValues.document_type || undefined,
        date_of_birth: collaborativeGuestValues.date_of_birth || undefined
      };
      if (collaborativeGuest.status !== "idle") {
        if (Object.keys(collaborativeGuest.conflicts).length > 0) {
          setFormMessage(t("profile.saveConflict"));
          return;
        }
        if (collaborativeGuest.isDirty) await collaborativeGuest.save();
      } else {
        await updateGuestMutation.mutateAsync({ guestId: selectedGuestId, payload });
      }
      setFormMessage(t("profile.saveSuccess"));
    } catch (error) {
      setFormMessage(error instanceof Error ? error.message : t("profile.saveError"));
    }
  };

  const handleCompanionSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedGuestId || !canEditGuest) return;
    setCompanionMessage(null);
    try {
      const payload: GuestCompanionPayload = {
        ...companionValues,
        date_of_birth: companionValues.date_of_birth || undefined
      };
      await addCompanionMutation.mutateAsync({ guestId: selectedGuestId, companions: [payload] });
      setCompanionMessage(t("companions.addSuccess"));
      setCompanionValues(emptyCompanion);
      await guestsQuery.refetch();
    } catch (error) {
      setCompanionMessage(error instanceof Error ? error.message : t("companions.addError"));
    }
  };

  const handleTagSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedGuestId || !canManageTags) return;
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
      setTagMessage(t("tags.addSuccess"));
    } catch (error) {
      setTagMessage(error instanceof Error ? error.message : t("tags.addError"));
    }
  };

  const handleResolveTag = async (tagId: number) => {
    if (!selectedGuestId || !canManageTags) return;
    setTagMessage(null);
    try {
      await resolveTagMutation.mutateAsync({ guestId: selectedGuestId, tagId });
      setTagMessage(t("tags.resolveSuccess"));
    } catch (error) {
      setTagMessage(error instanceof Error ? error.message : t("tags.resolveError"));
    }
  };

  const handleCheckIn = async (
    reservationId: number,
    override: boolean,
    restrictionOverride?: RestrictionOverride
  ) => {
    if (!canCheckIn || (override && !canOverrideProhibido)) return;
    setCheckInMessage(null);
    try {
      await checkInMutation.mutateAsync({ reservationId, override, restrictionOverride });
      setCheckInMessage(override ? t("checkIn.successOverride") : t("checkIn.success"));
    } catch (error) {
      // The guest has an active GuestRestriction (separate from the legacy
      // "prohibido_alojar" tag above) -- prompt for an override reason and
      // retry instead of surfacing a raw 409/403.
      if (
        restrictionOverridePrompt.handleError(error, (nextOverride) =>
          void handleCheckIn(reservationId, override, nextOverride)
        )
      ) {
        return;
      }
      setCheckInMessage(error instanceof Error ? error.message : t("checkIn.error"));
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">{t("list.eyebrow")}</p>
          <h1 className="text-2xl font-semibold text-slate-900">{t("list.title")}</h1>
          <p className="text-sm text-slate-600">{t("list.description")}</p>
        </div>
        <div className="w-full max-w-sm">
          <input
            type="search"
            value={search}
            onChange={(event) => handleSearchChange(event.target.value)}
            placeholder={t("list.searchPlaceholder")}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
          />
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-4 py-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">{t("list.panelEyebrow")}</p>
            <h2 className="text-lg font-semibold text-slate-900">{t("list.panelTitle")}</h2>
          </div>
          <div className="max-h-[65vh] overflow-y-auto">
            {guestsQuery.isLoading ? (
              <p className="px-4 py-3 text-sm text-slate-500">{t("list.loading")}</p>
            ) : guests.length === 0 ? (
              <p className="px-4 py-3 text-sm text-slate-500">{t("list.empty")}</p>
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
                        <div className="min-w-0">
                          <p className="font-semibold text-slate-900">{fullName || t("list.fallbackName", { id: guest.id })}</p>
                          <p className="text-xs text-slate-500">
                            {guest.document_number || guest.email || guest.phone || t("list.noContact")}
                          </p>
                          <GuestRestrictionBadge guestId={guest.id} className="mt-1" />
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
              {t("list.pageIndicator", { page: page + 1 })}
              {guestsQuery.isFetching ? t("list.updating") : ""}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                data-testid="guests-prev-page"
                onClick={() => setPage((current) => Math.max(0, current - 1))}
                disabled={page === 0 || guestsQuery.isFetching}
                className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {t("list.prevPage")}
              </button>
              <button
                type="button"
                data-testid="guests-next-page"
                onClick={() => setPage((current) => current + 1)}
                disabled={!hasNextPage || guestsQuery.isFetching}
                className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {t("list.nextPage")}
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
                    <p className="text-xs uppercase tracking-wide text-slate-500">{t("profile.eyebrow")}</p>
                    <h2 className="text-lg font-semibold text-slate-900">
                      {selectedGuest.first_name} {selectedGuest.last_name}
                    </h2>
                    <p className="text-xs text-slate-500">
                      {t("profile.updatedAt", {
                        date: selectedGuest.updated_at ? new Date(selectedGuest.updated_at).toLocaleString("es-AR") : t("profile.noDate")
                      })}
                    </p>
                    <GuestRestrictionBadge guestId={selectedGuest.id} className="mt-2" />
                  </div>
                  <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                    {t("profile.idLabel", { id: selectedGuest.id })}
                  </span>
                </div>

                {canEditGuest && collaborativeGuest.status !== "idle" ? (
                  <div
                    className="space-y-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900"
                    data-testid="guest-collaboration"
                    role="status"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span>
                        {collaborativeGuest.status === "connected"
                          ? `${t("collaboration.connected")}${collaborativeGuest.peers.length ? t("collaboration.connectedPeers", { count: collaborativeGuest.peers.length }) : ""}.`
                          : collaborativeGuest.status === "saving"
                            ? t("collaboration.saving")
                            : collaborativeGuest.status === "conflict"
                              ? t("collaboration.conflict")
                              : collaborativeGuest.status === "degraded"
                                ? t("collaboration.degraded")
                                : t("collaboration.connecting")}
                      </span>
                      {collaborativeGuest.peers.length > 0 ? (
                        <span className="text-xs text-sky-700">
                          {collaborativeGuest.peers.map((peer) => peer.fields.length ? peer.fields.join(", ") : t("collaboration.noActiveField")).join(" · ")}
                        </span>
                      ) : null}
                    </div>
                    {Object.values(collaborativeGuest.conflicts).map((conflict) => (
                      <div key={conflict.field} className="rounded-md border border-amber-200 bg-amber-50 p-2 text-amber-950" data-testid={`guest-conflict-${conflict.field}`}>
                        <p className="font-semibold">{t("collaboration.conflictIn", { field: conflict.field })}</p>
                        <p className="text-xs">{t("collaboration.ownValue", { value: String(conflict.localValue ?? t("collaboration.emptyValue")) })}</p>
                        <p className="text-xs">{t("collaboration.remoteValue", { value: String(conflict.remoteValue ?? t("collaboration.emptyValue")) })}</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <button type="button" className="rounded border border-amber-300 bg-white px-2 py-1 text-xs font-semibold" onClick={() => collaborativeGuest.keepMine(conflict.field)}>
                            {t("collaboration.keepMine")}
                          </button>
                          <button type="button" className="rounded border border-amber-300 bg-white px-2 py-1 text-xs font-semibold" onClick={() => collaborativeGuest.useRemote(conflict.field)}>
                            {t("collaboration.useRemote")}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}

                <fieldset disabled={!canEditGuest} className="grid gap-4 md:grid-cols-2 disabled:opacity-70">
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("profile.fields.firstName")}</span>
                    <input
                      value={collaborativeGuestValues.first_name ?? ""}
                      onChange={(e) => handleChange("first_name", e.target.value)}
                      onFocus={() => collaborativeGuest.focusField("first_name")}
                      onBlur={() => collaborativeGuest.blurField("first_name")}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("profile.fields.lastName")}</span>
                    <input
                      value={collaborativeGuestValues.last_name ?? ""}
                      onChange={(e) => handleChange("last_name", e.target.value)}
                      onFocus={() => collaborativeGuest.focusField("last_name")}
                      onBlur={() => collaborativeGuest.blurField("last_name")}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("profile.fields.dateOfBirth")}</span>
                    <input
                      type="date"
                      value={collaborativeGuestValues.date_of_birth ?? ""}
                      onChange={(e) => handleChange("date_of_birth", e.target.value)}
                      onFocus={() => collaborativeGuest.focusField("date_of_birth")}
                      onBlur={() => collaborativeGuest.blurField("date_of_birth")}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("profile.fields.email")}</span>
                    <input
                      value={collaborativeGuestValues.email ?? ""}
                      onChange={(e) => handleChange("email", e.target.value)}
                      onFocus={() => collaborativeGuest.focusField("email")}
                      onBlur={() => collaborativeGuest.blurField("email")}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("profile.fields.phone")}</span>
                    <input
                      value={collaborativeGuestValues.phone ?? ""}
                      onChange={(e) => handleChange("phone", e.target.value)}
                      onFocus={() => collaborativeGuest.focusField("phone")}
                      onBlur={() => collaborativeGuest.blurField("phone")}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("profile.fields.documentType")}</span>
                    <select
                      value={collaborativeGuestValues.document_type ?? ""}
                      onChange={(e) => handleChange("document_type", e.target.value)}
                      onFocus={() => collaborativeGuest.focusField("document_type")}
                      onBlur={() => collaborativeGuest.blurField("document_type")}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    >
                      <option value="">{t("profile.fields.select")}</option>
                      {DOCUMENT_TYPES.map((type) => (
                        <option key={type} value={type}>
                          {type}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("profile.fields.documentNumber")}</span>
                    <input
                      value={collaborativeGuestValues.document_number ?? ""}
                      onChange={(e) => handleChange("document_number", e.target.value)}
                      onFocus={() => collaborativeGuest.focusField("document_number")}
                      onBlur={() => collaborativeGuest.blurField("document_number")}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("profile.fields.nationality")}</span>
                    <input
                      value={collaborativeGuestValues.nationality ?? ""}
                      onChange={(e) => handleChange("nationality", e.target.value)}
                      onFocus={() => collaborativeGuest.focusField("nationality")}
                      onBlur={() => collaborativeGuest.blurField("nationality")}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("profile.fields.city")}</span>
                    <input
                      value={collaborativeGuestValues.city ?? ""}
                      onChange={(e) => handleChange("city", e.target.value)}
                      onFocus={() => collaborativeGuest.focusField("city")}
                      onBlur={() => collaborativeGuest.blurField("city")}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm md:col-span-2">
                    <span className="text-slate-600">{t("profile.fields.address")}</span>
                    <input
                      value={collaborativeGuestValues.address_line1 ?? ""}
                      onChange={(e) => handleChange("address_line1", e.target.value)}
                      onFocus={() => collaborativeGuest.focusField("address_line1")}
                      onBlur={() => collaborativeGuest.blurField("address_line1")}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm md:col-span-2">
                    <span className="text-slate-600">{t("profile.fields.observations")}</span>
                    <textarea
                      value={collaborativeGuestValues.observations ?? ""}
                      onChange={(e) => handleChange("observations", e.target.value)}
                      onFocus={() => collaborativeGuest.focusField("observations")}
                      onBlur={() => collaborativeGuest.blurField("observations")}
                      rows={4}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                </fieldset>

                {formMessage ? (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                    {formMessage}
                  </div>
                ) : null}

                {canEditGuest ? <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={updateGuestMutation.isPending || collaborativeGuest.isSaving}
                    className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                  >
                    {t("profile.save")}
                  </button>
                </div> : (
                  <p className="text-xs text-slate-500">{t("profile.readOnlyHint")}</p>
                )}
              </form>

              <section className="space-y-4 border-t border-slate-200 pt-4">
                <div className="flex flex-col gap-1">
                  <p className="text-xs uppercase tracking-wide text-slate-500">{t("tags.eyebrow")}</p>
                  <h3 className="text-base font-semibold text-slate-900">{t("tags.title")}</h3>
                  {hasProhibido ? (
                    <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-800">
                      {t("tags.prohibidoWarning")}
                    </p>
                  ) : null}
                </div>

                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  {tagsQuery.isLoading ? (
                    <p className="text-sm text-slate-500">{t("tags.loading")}</p>
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
                          <span>{t(`tags.types.${tag.tag_type}`, { defaultValue: tag.tag_type })}</span>
                          {tag.note ? <span className="truncate font-normal text-slate-500">- {tag.note}</span> : null}
                          {canManageTags && (
                            <button
                              type="button"
                              onClick={() => handleResolveTag(tag.id)}
                              disabled={resolveTagMutation.isPending}
                              className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-600 hover:bg-slate-100 disabled:opacity-60"
                            >
                              {t("tags.resolve")}
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">{t("tags.empty")}</p>
                  )}
                </div>

                {canManageTags ? <form className="grid gap-4 md:grid-cols-[220px_minmax(0,1fr)_180px_auto]" onSubmit={handleTagSubmit}>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("tags.typeLabel")}</span>
                    <select
                      value={tagValues.tag_type}
                      onChange={(e) => setTagValues((current) => ({ ...current, tag_type: e.target.value as GuestTagType }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    >
                      {TAG_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {t(`tags.types.${option.value}`)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("tags.noteLabel")}</span>
                    <input
                      value={tagValues.note ?? ""}
                      onChange={(e) => setTagValues((current) => ({ ...current, note: e.target.value }))}
                      placeholder={t("tags.notePlaceholder")}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("tags.expiresLabel")}</span>
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
                      {t("tags.add")}
                    </button>
                  </div>
                  {tagMessage ? (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 md:col-span-4">
                      {tagMessage}
                    </div>
                  ) : null}
                </form> : null}
              </section>

              <GuestRestrictionsPanel guestId={selectedGuest.id} />

              <section className="space-y-4 border-t border-slate-200 pt-4">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">{t("checkIn.eyebrow")}</p>
                  <h3 className="text-base font-semibold text-slate-900">{t("checkIn.title")}</h3>
                </div>

                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  {quickProfileQuery.isLoading ? (
                    <p className="text-sm text-slate-500">{t("checkIn.loading")}</p>
                  ) : lastStays.length > 0 ? (
                    <div className="space-y-2">
                      {lastStays.map((stay) => {
                        const canCheckInStay = canCheckInStatus(String(stay.status));
                        return (
                          <div key={stay.reservation_id} className="rounded-md bg-white px-3 py-2 text-sm shadow-sm">
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                              <div>
                                <p className="font-semibold text-slate-900">
                                  {t("checkIn.reservationPrefix")}{" "}
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
                                  {t("checkIn.dateRange", { start: formatDate(stay.check_in_date, t), end: formatDate(stay.check_out_date, t) })}
                                  {stay.room_number ? t("checkIn.roomSuffix", { room: stay.room_number }) : ""}
                                </p>
                              </div>
                              {canCheckIn && canCheckInStay ? (
                                <div className="flex flex-wrap gap-2">
                                  <button
                                    type="button"
                                    onClick={() => handleCheckIn(stay.reservation_id, false)}
                                    disabled={checkInMutation.isPending || hasProhibido}
                                    className="rounded-lg border border-brand-200 bg-brand-600 px-3 py-2 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                                  >
                                    {t("checkIn.action")}
                                  </button>
                                  {hasProhibido && canOverrideProhibido ? (
                                    <button
                                      type="button"
                                      onClick={() => handleCheckIn(stay.reservation_id, true)}
                                      disabled={checkInMutation.isPending}
                                      className="rounded-lg border border-red-200 bg-red-600 px-3 py-2 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-60"
                                    >
                                      {t("checkIn.override")}
                                    </button>
                                  ) : null}
                                </div>
                              ) : null}
                            </div>
                            {hasProhibido && canCheckIn && canCheckInStay && !canOverrideProhibido ? (
                              <p className="mt-2 text-xs font-medium text-red-700">
                                {t("checkIn.onlyManagerOverride")}
                              </p>
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">{t("checkIn.empty")}</p>
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
                  <p className="text-xs uppercase tracking-wide text-slate-500">{t("companions.eyebrow")}</p>
                  <h3 className="text-base font-semibold text-slate-900">{t("companions.title")}</h3>
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
                              {companion.relationship_to_guest || t("companions.relationshipPending")}
                            </span>
                          </div>
                          <p className="text-xs text-slate-500">
                            {companion.document_type || t("companions.noDocument")}{" "}
                            {companion.document_number ? `- ${companion.document_number}` : ""}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">{t("companions.empty")}</p>
                  )}
                </div>

                {canEditGuest ? <form className="grid gap-4 md:grid-cols-2" onSubmit={handleCompanionSubmit}>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("companions.fields.firstName")}</span>
                    <input
                      value={companionValues.first_name ?? ""}
                      onChange={(e) => handleCompanionChange("first_name", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("companions.fields.lastName")}</span>
                    <input
                      value={companionValues.last_name ?? ""}
                      onChange={(e) => handleCompanionChange("last_name", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("companions.fields.dateOfBirth")}</span>
                    <input
                      type="date"
                      value={companionValues.date_of_birth ?? ""}
                      onChange={(e) => handleCompanionChange("date_of_birth", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("companions.fields.relationship")}</span>
                    <input
                      value={companionValues.relationship_to_guest ?? ""}
                      onChange={(e) => handleCompanionChange("relationship_to_guest", e.target.value)}
                      placeholder={t("companions.fields.relationshipPlaceholder")}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("companions.fields.documentType")}</span>
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
                    <span className="text-slate-600">{t("companions.fields.documentNumber")}</span>
                    <input
                      value={companionValues.document_number ?? ""}
                      onChange={(e) => handleCompanionChange("document_number", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm md:col-span-2">
                    <span className="text-slate-600">{t("companions.fields.nationality")}</span>
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
                      {t("companions.add")}
                    </button>
                  </div>
                </form> : null}
              </section>
            </>
          ) : (
            <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-500">
              {t("emptySelection")}
            </div>
          )}
        </section>
      </div>

      {restrictionOverridePrompt.phase !== "idle" ? (
        <RestrictionOverrideModal
          phase={restrictionOverridePrompt.phase}
          onSubmit={restrictionOverridePrompt.submit}
          onCancel={restrictionOverridePrompt.dismiss}
          isPending={checkInMutation.isPending}
        />
      ) : null}
    </div>
  );
}
