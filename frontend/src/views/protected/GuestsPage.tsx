import React, { useEffect, useMemo, useState } from "react";

import { type GuestCompanionPayload, type GuestUpdatePayload } from "../../api/guests";
import { useGuestCompanionAdd, useGuestUpdate, useGuests } from "../../hooks/useGuests";

const DOCUMENT_TYPES = ["DNI", "PASSPORT", "CEDULA"] as const;

const emptyForm: GuestUpdatePayload = {
  first_name: "",
  last_name: "",
  date_of_birth: "",
  email: "",
  phone: "",
  document_type: "",
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

export function GuestsPage() {
  const [search, setSearch] = useState("");
  const [selectedGuestId, setSelectedGuestId] = useState<number | null>(null);
  const [formValues, setFormValues] = useState<GuestUpdatePayload>(emptyForm);
  const [companionValues, setCompanionValues] = useState<GuestCompanionPayload>(emptyCompanion);
  const [formMessage, setFormMessage] = useState<string | null>(null);
  const [companionMessage, setCompanionMessage] = useState<string | null>(null);
  const guestsQuery = useGuests(search);
  const updateGuestMutation = useGuestUpdate();
  const addCompanionMutation = useGuestCompanionAdd();
  const guests = useMemo(() => guestsQuery.data ?? [], [guestsQuery.data]);

  const selectedGuest = useMemo(
    () => guests.find((guest) => guest.id === selectedGuestId) ?? guests[0] ?? null,
    [guests, selectedGuestId]
  );

  useEffect(() => {
    if (!selectedGuest) {
      setSelectedGuestId(null);
      setFormValues(emptyForm);
      setCompanionValues(emptyCompanion);
      return;
    }

    setSelectedGuestId(selectedGuest.id);
    setFormValues({
      first_name: selectedGuest.first_name,
      last_name: selectedGuest.last_name,
      date_of_birth: selectedGuest.date_of_birth ?? "",
      email: selectedGuest.email ?? "",
      phone: selectedGuest.phone ?? "",
      document_type: selectedGuest.document_type ?? "",
      document_number: selectedGuest.document_number ?? "",
      nationality: selectedGuest.nationality ?? "",
      city: selectedGuest.city ?? "",
      country: selectedGuest.country ?? "",
      address_line1: selectedGuest.address_line1 ?? "",
      observations: selectedGuest.observations ?? ""
    });
    setCompanionValues(emptyCompanion);
  }, [selectedGuest]);

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
      setFormMessage("Guest saved.");
    } catch (error) {
      setFormMessage(error instanceof Error ? error.message : "Could not save guest.");
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
      setCompanionMessage("Companion saved.");
      setCompanionValues(emptyCompanion);
      await guestsQuery.refetch();
    } catch (error) {
      setCompanionMessage(error instanceof Error ? error.message : "Could not save companion.");
    }
  };

  const companions = selectedGuest?.companions ?? [];

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Guests</p>
          <h1 className="text-2xl font-semibold text-slate-900">Guest ledger</h1>
          <p className="text-sm text-slate-600">
            Search guests by name, document, or email and keep the operational record up to date.
          </p>
        </div>
        <div className="w-full max-w-sm">
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by name, document, or email"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
          />
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-4 py-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">List</p>
            <h2 className="text-lg font-semibold text-slate-900">Hotel guests</h2>
          </div>
          <div className="max-h-[65vh] overflow-y-auto">
            {guestsQuery.isLoading ? (
              <p className="px-4 py-3 text-sm text-slate-500">Loading guests...</p>
            ) : guests.length === 0 ? (
              <p className="px-4 py-3 text-sm text-slate-500">No guests match the current filters.</p>
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
                          <p className="font-semibold text-slate-900">{fullName || `Guest #${guest.id}`}</p>
                          <p className="text-xs text-slate-500">
                            {guest.document_number || guest.email || guest.phone || "No document or contact"}
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
        </section>

        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          {selectedGuest ? (
            <>
              <form className="space-y-4" onSubmit={handleSubmit}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">Operational file</p>
                    <h2 className="text-lg font-semibold text-slate-900">
                      {selectedGuest.first_name} {selectedGuest.last_name}
                    </h2>
                    <p className="text-xs text-slate-500">
                      Updated {selectedGuest.updated_at ? new Date(selectedGuest.updated_at).toLocaleString("es-AR") : "no date"}
                    </p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                    ID {selectedGuest.id}
                  </span>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">First name</span>
                    <input
                      value={formValues.first_name ?? ""}
                      onChange={(e) => handleChange("first_name", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Last name</span>
                    <input
                      value={formValues.last_name ?? ""}
                      onChange={(e) => handleChange("last_name", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Date of birth</span>
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
                    <span className="text-slate-600">Phone</span>
                    <input
                      value={formValues.phone ?? ""}
                      onChange={(e) => handleChange("phone", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Document type</span>
                    <select
                      value={formValues.document_type ?? ""}
                      onChange={(e) => handleChange("document_type", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    >
                      <option value="">Select</option>
                      {DOCUMENT_TYPES.map((type) => (
                        <option key={type} value={type}>
                          {type}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Document number</span>
                    <input
                      value={formValues.document_number ?? ""}
                      onChange={(e) => handleChange("document_number", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Nationality</span>
                    <input
                      value={formValues.nationality ?? ""}
                      onChange={(e) => handleChange("nationality", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">City</span>
                    <input
                      value={formValues.city ?? ""}
                      onChange={(e) => handleChange("city", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm md:col-span-2">
                    <span className="text-slate-600">Address</span>
                    <input
                      value={formValues.address_line1 ?? ""}
                      onChange={(e) => handleChange("address_line1", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm md:col-span-2">
                    <span className="text-slate-600">Observations</span>
                    <textarea
                      value={formValues.observations ?? ""}
                      onChange={(e) => handleChange("observations", e.target.value)}
                      rows={4}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                </div>

                {formMessage ? (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">{formMessage}</div>
                ) : null}

                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={updateGuestMutation.isLoading}
                    className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                  >
                    Save guest
                  </button>
                </div>
              </form>

              <section className="space-y-4 border-t border-slate-200 pt-4">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Companions</p>
                  <h3 className="text-base font-semibold text-slate-900">Travel companions</h3>
                </div>

                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  {companions.length > 0 ? (
                    <div className="space-y-2">
                      {companions.map((companion) => (
                        <div key={companion.id ?? `${companion.first_name}-${companion.last_name}`} className="rounded-md bg-white px-3 py-2 text-sm shadow-sm">
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-semibold text-slate-900">
                              {companion.first_name} {companion.last_name}
                            </p>
                            <span className="text-xs text-slate-500">{companion.relationship_to_guest || "relationship pending"}</span>
                          </div>
                          <p className="text-xs text-slate-500">
                            {companion.document_type || "No document"} {companion.document_number ? `- ${companion.document_number}` : ""}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">No companions recorded yet.</p>
                  )}
                </div>

                <form className="grid gap-4 md:grid-cols-2" onSubmit={handleCompanionSubmit}>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">First name</span>
                    <input
                      value={companionValues.first_name ?? ""}
                      onChange={(e) => handleCompanionChange("first_name", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Last name</span>
                    <input
                      value={companionValues.last_name ?? ""}
                      onChange={(e) => handleCompanionChange("last_name", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Date of birth</span>
                    <input
                      type="date"
                      value={companionValues.date_of_birth ?? ""}
                      onChange={(e) => handleCompanionChange("date_of_birth", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Relationship</span>
                    <input
                      value={companionValues.relationship_to_guest ?? ""}
                      onChange={(e) => handleCompanionChange("relationship_to_guest", e.target.value)}
                      placeholder="child, spouse, guardian..."
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Document type</span>
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
                    <span className="text-slate-600">Document number</span>
                    <input
                      value={companionValues.document_number ?? ""}
                      onChange={(e) => handleCompanionChange("document_number", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm md:col-span-2">
                    <span className="text-slate-600">Nationality</span>
                    <input
                      value={companionValues.nationality ?? ""}
                      onChange={(e) => handleCompanionChange("nationality", e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>

                  {companionMessage ? (
                    <div className="md:col-span-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                      {companionMessage}
                    </div>
                  ) : null}

                  <div className="md:col-span-2 flex justify-end">
                    <button
                      type="submit"
                      disabled={addCompanionMutation.isLoading}
                      className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                    >
                      Add companion
                    </button>
                  </div>
                </form>
              </section>
            </>
          ) : (
            <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-500">
              Select a guest to open the file.
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
