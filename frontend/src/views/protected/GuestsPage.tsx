import React, { useEffect, useMemo, useState } from "react";

import { type GuestUpdatePayload } from "../../api/guests";
import { useGuestUpdate, useGuests } from "../../hooks/useGuests";

const emptyForm: GuestUpdatePayload = {
  first_name: "",
  last_name: "",
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

export function GuestsPage() {
  const [search, setSearch] = useState("");
  const [selectedGuestId, setSelectedGuestId] = useState<number | null>(null);
  const [formValues, setFormValues] = useState<GuestUpdatePayload>(emptyForm);
  const [formMessage, setFormMessage] = useState<string | null>(null);
  const guestsQuery = useGuests(search);
  const updateGuestMutation = useGuestUpdate();
  const guests = guestsQuery.data ?? [];

  const selectedGuest = useMemo(
    () => guests.find((guest) => guest.id === selectedGuestId) ?? guests[0] ?? null,
    [guests, selectedGuestId]
  );

  useEffect(() => {
    if (!selectedGuest) {
      setSelectedGuestId(null);
      setFormValues(emptyForm);
      return;
    }
    setSelectedGuestId(selectedGuest.id);
    setFormValues({
      first_name: selectedGuest.first_name,
      last_name: selectedGuest.last_name,
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
  }, [selectedGuest]);

  const handleChange = (field: keyof GuestUpdatePayload, value: string) => {
    setFormValues((current) => ({ ...current, [field]: value }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedGuestId) return;
    setFormMessage(null);
    try {
      await updateGuestMutation.mutateAsync({ guestId: selectedGuestId, payload: formValues });
      setFormMessage("Ficha de huésped actualizada.");
    } catch (error) {
      setFormMessage(error instanceof Error ? error.message : "No se pudo actualizar el huésped.");
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Huéspedes</p>
          <h1 className="text-2xl font-semibold text-slate-900">Base de pasajeros</h1>
          <p className="text-sm text-slate-600">
            Buscá huéspedes por nombre, documento o email y corregí la ficha operativa sin salir del PMS.
          </p>
        </div>
        <div className="w-full max-w-sm">
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
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
              <p className="px-4 py-3 text-sm text-slate-500">No hay huéspedes para los filtros actuales.</p>
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
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          {selectedGuest ? (
            <form className="space-y-4" onSubmit={handleSubmit}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Ficha operativa</p>
                  <h2 className="text-lg font-semibold text-slate-900">
                    {selectedGuest.first_name} {selectedGuest.last_name}
                  </h2>
                  <p className="text-xs text-slate-500">
                    Actualizado {selectedGuest.updated_at ? new Date(selectedGuest.updated_at).toLocaleString("es-AR") : "sin fecha"}
                  </p>
                </div>
                <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                  ID {selectedGuest.id}
                </span>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Nombre</span>
                  <input value={formValues.first_name ?? ""} onChange={(e) => handleChange("first_name", e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2" />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Apellido</span>
                  <input value={formValues.last_name ?? ""} onChange={(e) => handleChange("last_name", e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2" />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Email</span>
                  <input value={formValues.email ?? ""} onChange={(e) => handleChange("email", e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2" />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Teléfono</span>
                  <input value={formValues.phone ?? ""} onChange={(e) => handleChange("phone", e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2" />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Documento</span>
                  <input value={formValues.document_number ?? ""} onChange={(e) => handleChange("document_number", e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2" />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Tipo documento</span>
                  <input value={formValues.document_type ?? ""} onChange={(e) => handleChange("document_type", e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2" />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Nacionalidad</span>
                  <input value={formValues.nationality ?? ""} onChange={(e) => handleChange("nationality", e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2" />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Ciudad</span>
                  <input value={formValues.city ?? ""} onChange={(e) => handleChange("city", e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2" />
                </label>
                <label className="space-y-1 text-sm md:col-span-2">
                  <span className="text-slate-600">Dirección</span>
                  <input value={formValues.address_line1 ?? ""} onChange={(e) => handleChange("address_line1", e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2" />
                </label>
                <label className="space-y-1 text-sm md:col-span-2">
                  <span className="text-slate-600">Observaciones</span>
                  <textarea value={formValues.observations ?? ""} onChange={(e) => handleChange("observations", e.target.value)} rows={4} className="w-full rounded-lg border border-slate-300 px-3 py-2" />
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
                  Guardar ficha
                </button>
              </div>
            </form>
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
