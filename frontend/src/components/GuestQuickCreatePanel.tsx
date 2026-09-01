import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { hasValidSession } from "../api/client";
import { listGuests, type Guest, type GuestPayload } from "../api/guests";
import { useGuest, useGuestCreate } from "../hooks/useGuests";
import { useEffectivePermissions } from "../hooks/usePermissions";
import { useSession } from "../state/session";

import { GuestRestrictionBadge } from "./GuestRestrictionBadge";

// Shared search-existing-guest-by-name-or-document-or-quick-create sub-form.
// Used by both the direct quick-reservation create form and the manual OTA
// reservation form (B4) -- same fields, same create-and-assign behavior,
// so this lives in one place instead of being copy-pasted per form.
//
// E1: this used to be a raw numeric guest-ID text input -- the hotel
// owner has no way to know a guest's internal ID, and can't tell two guests
// with the same name apart (e.g. two people sharing a first and last name)
// without seeing more than a number. Replaced with the same search-by-name/DNI
// pattern already used in GuestsPage.tsx, plus a confirmation card
// (name/email/phone/DNI) before the guest is actually assigned to the
// reservation.
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
  const { t } = useTranslation("guests");
  return (
    <div
      className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm"
      data-testid="guest-confirm-card"
    >
      <p className="text-xs uppercase tracking-wide text-emerald-700">{t("quickCreate.selectedTitle")}</p>
      <p className="font-semibold text-emerald-900">
        {guestFullName(guest) || t("quickCreate.fallbackName", { id: guest.id })}{" "}
        <span className="font-normal text-emerald-700">#{guest.id}</span>
      </p>
      <GuestRestrictionBadge guestId={guest.id} className="mt-1" />
      <dl className="mt-1 grid gap-x-3 gap-y-0.5 text-xs text-emerald-800 sm:grid-cols-2">
        <div>
          <dt className="inline font-medium">{t("quickCreate.emailLabel")}</dt>
          <dd className="inline">{guest.email || "—"}</dd>
        </div>
        <div>
          <dt className="inline font-medium">{t("quickCreate.phoneLabel")}</dt>
          <dd className="inline">{guest.phone || "—"}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="inline font-medium">{t("quickCreate.documentLabel")}</dt>
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
          {changeLabel ?? t("quickCreate.changeGuest")}
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
  const { t } = useTranslation("guests");
  const { session } = useSession();
  const { hasPermission } = useEffectivePermissions();
  const canViewGuests = hasPermission("guest:read");
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

  const handleCreateGuest = async () => {
    if (!canCreateGuests) return;
    try {
      const guest = await guestMutation.mutateAsync({
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        email: form.email.trim() || undefined,
        phone: form.phone.trim() || undefined,
        document_type: form.document_type,
        document_number: form.document_number.trim() || undefined,
        terms_accepted: true
      });
      setSelectedGuest(guest);
      onGuestIdChange(String(guest.id));
      onFormChange(emptyQuickGuestForm);
      setShowQuickCreate(false);
      onGuestCreated(guest.id);
    } catch (err: unknown) {
      onError(err instanceof Error ? err.message : t("quickCreate.createError"));
    }
  };

  const results = searchQuery.data ?? [];

  return (
    <div className="space-y-3 sm:col-span-2">
      <p className="text-xs font-semibold text-slate-600">{t("quickCreate.label")}</p>

      {guestId ? (
        confirmedGuest ? (
          <GuestSummaryCard
            guest={confirmedGuest}
            onChange={guestIdDisabled ? undefined : handleChangeGuest}
          />
        ) : (
          <p className="text-xs text-slate-500">{t("quickCreate.loadingGuest", { id: guestId })}</p>
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
              {t("quickCreate.confirm")}
            </button>
            <button
              type="button"
              onClick={() => setPendingGuest(null)}
              data-testid="guest-search-again-button"
              className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"
            >
              {t("quickCreate.searchAgain")}
            </button>
          </div>
        </div>
      ) : showQuickCreate && canCreateGuests && !guestIdDisabled ? (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">{t("quickCreate.panelTitle")}</p>
              <p className="text-xs text-slate-600">{t("quickCreate.panelDescription")}</p>
            </div>
            {guestMutation.isPending && <span className="text-xs text-slate-500">{t("quickCreate.saving")}</span>}
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
            <input
              placeholder={t("quickCreate.firstNamePlaceholder")}
              value={form.first_name}
              onChange={(e) => onFormChange((prev) => ({ ...prev, first_name: e.target.value }))}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
            />
            <input
              placeholder={t("quickCreate.lastNamePlaceholder")}
              value={form.last_name}
              onChange={(e) => onFormChange((prev) => ({ ...prev, last_name: e.target.value }))}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
            />
            <input
              placeholder={t("quickCreate.emailPlaceholder")}
              value={form.email}
              onChange={(e) => onFormChange((prev) => ({ ...prev, email: e.target.value }))}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
            />
            <input
              placeholder={t("quickCreate.phonePlaceholder")}
              value={form.phone}
              onChange={(e) => onFormChange((prev) => ({ ...prev, phone: e.target.value }))}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
            />
            <label className="text-xs font-semibold text-slate-600">
              {t("quickCreate.documentTypeLabel")}
              <select
                aria-label={t("quickCreate.documentTypeLabel")}
                value={form.document_type}
                onChange={(e) =>
                  onFormChange((prev) => ({
                    ...prev,
                    document_type: e.target.value as NonNullable<GuestPayload["document_type"]>
                  }))
                }
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
              >
                <option value="DNI">{t("quickCreate.documentTypes.DNI")}</option>
                <option value="PASSPORT">{t("quickCreate.documentTypes.PASSPORT")}</option>
                <option value="CEDULA">{t("quickCreate.documentTypes.CEDULA")}</option>
              </select>
            </label>
            <input
              placeholder={t("quickCreate.documentNumberPlaceholder")}
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
              {t("quickCreate.createAndAssign")}
            </button>
            <span>{t("quickCreate.autoAssignHint")}</span>
            <button
              type="button"
              onClick={() => setShowQuickCreate(false)}
              data-testid="guest-quick-create-toggle"
              className="font-semibold text-brand-700 underline hover:text-brand-800"
            >
              {t("quickCreate.backToSearch")}
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
            placeholder={t("quickCreate.searchPlaceholder")}
            aria-label={t("quickCreate.searchAriaLabel")}
            data-testid="guest-search-input"
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
          />
          {debouncedQuery.length >= GUEST_SEARCH_MIN_LENGTH &&
            (searchQuery.isLoading ? (
              <p className="text-xs text-slate-500">{t("quickCreate.searching")}</p>
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
                    <p className="font-medium text-slate-900">{guestFullName(guest) || t("quickCreate.fallbackName", { id: guest.id })}</p>
                    <p className="text-xs text-slate-500">
                      {guest.document_number || t("quickCreate.noDocument")}
                      {guest.email ? ` · ${guest.email}` : ""}
                    </p>
                    <GuestRestrictionBadge guestId={guest.id} className="mt-1" />
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">{t("quickCreate.noResults", { query: debouncedQuery })}</p>
            ))}
          {!guestIdDisabled && canCreateGuests && (
            <button
              type="button"
              onClick={() => setShowQuickCreate(true)}
              data-testid="guest-quick-create-toggle"
              className="text-xs font-semibold text-brand-700 underline hover:text-brand-800"
            >
              {t("quickCreate.createNew")}
            </button>
          )}
          {!canViewGuests && !canCreateGuests && (
            <p className="text-xs text-slate-500">{t("quickCreate.noPermissions")}</p>
          )}
        </div>
      )}
    </div>
  );
}
