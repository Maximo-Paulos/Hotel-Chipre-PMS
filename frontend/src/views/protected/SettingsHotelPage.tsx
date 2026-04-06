import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { getHotelConfig, updateHotelConfig, type HotelConfig } from "../../api/config";
import {
  listRoomCategories,
  listRooms,
  createRoomCategory,
  updateRoomCategory,
  createRoom,
  updateRoom,
  type RoomCategory,
  type Room,
  type RoomStatus
} from "../../api/rooms";
import { useSession } from "../../state/session";

const roomStatuses: RoomStatus[] = ["available", "occupied", "maintenance", "blocked", "cleaning"];

export function SettingsHotelPage() {
  const { session } = useSession();
  const qc = useQueryClient();
  const [form, setForm] = useState<Partial<HotelConfig>>({});
  const [error, setError] = useState<string | null>(null);

  const [categoryForm, setCategoryForm] = useState<Omit<RoomCategory, "id">>({
    name: "",
    code: "",
    description: "",
    base_price_per_night: 0,
    max_occupancy: 1,
    amenities: ""
  });
  const [editingCategoryId, setEditingCategoryId] = useState<number | null>(null);
  const [categoryEdit, setCategoryEdit] = useState<Partial<Omit<RoomCategory, "id">>>({});

  const [roomForm, setRoomForm] = useState<{ room_number: string; floor: number; category_id: number; notes?: string }>(
    { room_number: "", floor: 1, category_id: 0, notes: "" }
  );
  const [editingRoomId, setEditingRoomId] = useState<number | null>(null);
  const [roomEdit, setRoomEdit] = useState<Partial<{ room_number: string; floor: number; category_id: number; status: RoomStatus; is_active: boolean; notes?: string }>>({});

  const configQuery = useQuery({
    queryKey: ["hotel-config", session.hotelId],
    queryFn: () => getHotelConfig(session),
    onSuccess: (data) => setForm(data)
  });

  const categoriesQuery = useQuery({
    queryKey: ["room-categories", session.hotelId],
    queryFn: () => listRoomCategories(session)
  });

  const roomsQuery = useQuery({
    queryKey: ["rooms", session.hotelId],
    queryFn: () => listRooms(session)
  });

  const updateConfigMutation = useMutation({
    mutationFn: (payload: Partial<HotelConfig>) => updateHotelConfig(payload, session),
    onSuccess: (data) => {
      setForm(data);
      setError(null);
    },
    onError: (err: any) => setError(err?.message || "No se pudo guardar la configuración")
  });

  const createCategoryMutation = useMutation({
    mutationFn: (payload: Omit<RoomCategory, "id">) => createRoomCategory(payload, session),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["room-categories", session.hotelId] });
      setCategoryForm({ name: "", code: "", description: "", base_price_per_night: 0, max_occupancy: 1, amenities: "" });
      setError(null);
    },
    onError: (err: any) => setError(err?.message || "No se pudo crear la categoría")
  });

  const updateCategoryMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<Omit<RoomCategory, "id">> }) => updateRoomCategory(id, payload, session),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["room-categories", session.hotelId] });
      setEditingCategoryId(null);
      setCategoryEdit({});
      setError(null);
    },
    onError: (err: any) => setError(err?.message || "No se pudo actualizar la categoría")
  });

  const createRoomMutation = useMutation({
    mutationFn: (payload: { room_number: string; floor: number; category_id: number; notes?: string }) =>
      createRoom({ ...payload, status: "available", is_active: true }, session),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rooms", session.hotelId] });
      setRoomForm({ room_number: "", floor: 1, category_id: 0, notes: "" });
      setError(null);
    },
    onError: (err: any) => setError(err?.message || "No se pudo crear la habitación")
  });

  const updateRoomMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<{ room_number: string; floor: number; category_id: number; status: RoomStatus; is_active: boolean; notes?: string }> }) =>
      updateRoom(id, payload, session),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rooms", session.hotelId] });
      setEditingRoomId(null);
      setRoomEdit({});
      setError(null);
    },
    onError: (err: any) => setError(err?.message || "No se pudo actualizar la habitación")
  });

  const handleChange = (key: keyof HotelConfig, value: unknown) => setForm((prev) => ({ ...prev, [key]: value }));
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateConfigMutation.mutate(form);
  };

  const ownerOnly = session.baseRole === "owner";

  if (!session.hotelId) return <p className="text-sm text-rose-700">Seleccioná un hotel para editar su configuración.</p>;

  return (
    <div className="space-y-5">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Configuración</p>
        <h1 className="text-2xl font-semibold text-slate-900">Hotel</h1>
        <p className="text-sm text-slate-600">Hotel ID {session.hotelId}</p>
      </header>
      {error && <p className="rounded-md bg-rose-50 p-2 text-sm text-rose-700">{error}</p>}

      {configQuery.isLoading ? (
        <p className="text-sm text-slate-600">Cargando configuración...</p>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-sm font-semibold text-slate-700">
              Nombre del hotel
              <input className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" value={form.hotel_name ?? ""} onChange={(e) => handleChange("hotel_name", e.target.value)} />
            </label>
            <label className="text-sm font-semibold text-slate-700">
              Zona horaria
              <input className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" value={form.hotel_timezone ?? ""} onChange={(e) => handleChange("hotel_timezone", e.target.value)} />
            </label>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <label className="text-sm font-semibold text-slate-700">
              Moneda
              <input className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" value={form.default_currency ?? ""} onChange={(e) => handleChange("default_currency", e.target.value)} />
            </label>
            <label className="text-sm font-semibold text-slate-700">
              Depósito (%)
              <input type="number" min={0} max={100} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" value={form.deposit_percentage ?? 0} onChange={(e) => handleChange("deposit_percentage", parseFloat(e.target.value || "0"))} />
            </label>
            <label className="text-sm font-semibold text-slate-700">
              Cancelación gratis (horas)
              <input type="number" min={0} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" value={form.free_cancellation_hours ?? 0} onChange={(e) => handleChange("free_cancellation_hours", parseInt(e.target.value || "0", 10))} />
            </label>
          </div>

          {ownerOnly && (
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-lg border border-slate-200 p-4">
                <h3 className="text-sm font-semibold text-slate-800">Visibilidad y permisos</h3>
                <label className="text-sm font-semibold text-slate-700">
                  Días pasados visibles
                  <input type="range" min={0} max={90} value={form.receptionist_view_past_days ?? 0} onChange={(e) => handleChange("receptionist_view_past_days", parseInt(e.target.value, 10))} className="mt-1 w-full" />
                  <span className="text-xs text-slate-600">{form.receptionist_view_past_days ?? 0} días</span>
                </label>
                <label className="text-sm font-semibold text-slate-700">
                  Días futuros visibles
                  <input type="range" min={0} max={365} value={form.receptionist_view_future_days ?? 30} onChange={(e) => handleChange("receptionist_view_future_days", parseInt(e.target.value, 10))} className="mt-1 w-full" />
                  <span className="text-xs text-slate-600">{form.receptionist_view_future_days ?? 30} días</span>
                </label>
              </div>
              <div className="rounded-lg border border-slate-200 p-4">
                <h3 className="text-sm font-semibold text-slate-800">Alertas</h3>
                <label className="text-sm font-semibold text-slate-700">
                  Canales en stop-sell (JSON)
                  <textarea className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" rows={2} value={form.stop_sell_channels ?? ""} onChange={(e) => handleChange("stop_sell_channels", e.target.value)} />
                </label>
              </div>
            </div>
          )}

          {/* Categorías */}
          <div className="rounded-lg border border-slate-200 p-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-slate-800">Categorías de habitación</h3>
                <p className="text-xs text-slate-500">Agregar y editar categorías para este hotel.</p>
              </div>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Nombre" value={categoryForm.name} onChange={(e) => setCategoryForm((p) => ({ ...p, name: e.target.value }))} />
              <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Código" value={categoryForm.code} onChange={(e) => setCategoryForm((p) => ({ ...p, code: e.target.value }))} />
              <input type="number" min={1} className="rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Precio base" value={categoryForm.base_price_per_night} onChange={(e) => setCategoryForm((p) => ({ ...p, base_price_per_night: parseFloat(e.target.value || "0") }))} />
              <input type="number" min={1} className="rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Ocupación máx" value={categoryForm.max_occupancy} onChange={(e) => setCategoryForm((p) => ({ ...p, max_occupancy: parseInt(e.target.value || "1", 10) }))} />
              <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm md:col-span-2" placeholder="Amenidades" value={categoryForm.amenities ?? ""} onChange={(e) => setCategoryForm((p) => ({ ...p, amenities: e.target.value }))} />
              <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm md:col-span-3" placeholder="Descripción" value={categoryForm.description ?? ""} onChange={(e) => setCategoryForm((p) => ({ ...p, description: e.target.value }))} />
              <button type="button" className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60" disabled={createCategoryMutation.isLoading || !categoryForm.name || !categoryForm.code || categoryForm.base_price_per_night <= 0 || categoryForm.max_occupancy <= 0} onClick={() => createCategoryMutation.mutate(categoryForm)}>
                {createCategoryMutation.isLoading ? "Guardando..." : "Agregar categoría"}
              </button>
            </div>
            <div className="mt-4 grid gap-2 md:grid-cols-2">
              {(categoriesQuery.data ?? []).map((c) => (
                <div key={c.id} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">
                  {editingCategoryId === c.id ? (
                    <div className="space-y-2">
                      <input className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm" value={categoryEdit.name ?? c.name} onChange={(e) => setCategoryEdit((p) => ({ ...p, name: e.target.value }))} />
                      <input className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm" value={categoryEdit.code ?? c.code} onChange={(e) => setCategoryEdit((p) => ({ ...p, code: e.target.value }))} />
                      <div className="grid grid-cols-2 gap-2">
                        <input type="number" className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm" value={categoryEdit.base_price_per_night ?? c.base_price_per_night} onChange={(e) => setCategoryEdit((p) => ({ ...p, base_price_per_night: parseFloat(e.target.value || "0") }))} />
                        <input type="number" className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm" value={categoryEdit.max_occupancy ?? c.max_occupancy} onChange={(e) => setCategoryEdit((p) => ({ ...p, max_occupancy: parseInt(e.target.value || "1", 10) }))} />
                      </div>
                      <input className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm" placeholder="Amenidades" value={categoryEdit.amenities ?? c.amenities ?? ""} onChange={(e) => setCategoryEdit((p) => ({ ...p, amenities: e.target.value }))} />
                      <input className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm" placeholder="Descripción" value={categoryEdit.description ?? c.description ?? ""} onChange={(e) => setCategoryEdit((p) => ({ ...p, description: e.target.value }))} />
                      <div className="flex gap-2">
                        <button type="button" className="rounded-lg bg-brand-600 px-3 py-1 text-xs font-semibold text-white" onClick={() => updateCategoryMutation.mutate({ id: c.id, payload: categoryEdit })}>Guardar</button>
                        <button type="button" className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-700" onClick={() => { setEditingCategoryId(null); setCategoryEdit({}); }}>Cancelar</button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{c.name} ({c.code})</p>
                        <p className="text-xs text-slate-600">Ocupación: {c.max_occupancy} · Precio base: {c.base_price_per_night}</p>
                        {c.description && <p className="text-xs text-slate-600">{c.description}</p>}
                        {c.amenities && <p className="text-xs text-slate-500">Amenities: {c.amenities}</p>}
                      </div>
                      <button type="button" className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-700" onClick={() => { setEditingCategoryId(c.id); setCategoryEdit({}); }}>Editar</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Habitaciones */}
          <div className="rounded-lg border border-slate-200 p-4">
            <h3 className="text-sm font-semibold text-slate-800">Habitaciones</h3>
            <div className="mt-3 grid gap-3 md:grid-cols-4">
              <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Número" value={roomForm.room_number} onChange={(e) => setRoomForm((p) => ({ ...p, room_number: e.target.value }))} />
              <input type="number" className="rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Piso" value={roomForm.floor} onChange={(e) => setRoomForm((p) => ({ ...p, floor: parseInt(e.target.value || "1", 10) }))} />
              <select className="rounded-lg border border-slate-200 px-3 py-2 text-sm" value={roomForm.category_id || ""} onChange={(e) => setRoomForm((p) => ({ ...p, category_id: parseInt(e.target.value || "0", 10) }))}>
                <option value="">Categoría</option>
                {(categoriesQuery.data ?? []).map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm md:col-span-2" placeholder="Notas" value={roomForm.notes ?? ""} onChange={(e) => setRoomForm((p) => ({ ...p, notes: e.target.value }))} />
              <button type="button" className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60 md:col-span-2" disabled={createRoomMutation.isLoading || !roomForm.room_number || !roomForm.category_id} onClick={() => createRoomMutation.mutate(roomForm)}>
                {createRoomMutation.isLoading ? "Guardando..." : "Agregar habitación"}
              </button>
            </div>
            <div className="mt-4 grid gap-2 md:grid-cols-3">
              {(roomsQuery.data ?? []).map((r) => (
                <div key={r.id} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">
                  {editingRoomId === r.id ? (
                    <div className="space-y-2">
                      <input className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm" value={roomEdit.room_number ?? r.room_number} onChange={(e) => setRoomEdit((p) => ({ ...p, room_number: e.target.value }))} />
                      <div className="grid grid-cols-2 gap-2">
                        <input type="number" className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm" value={roomEdit.floor ?? r.floor} onChange={(e) => setRoomEdit((p) => ({ ...p, floor: parseInt(e.target.value || "1", 10) }))} />
                        <select className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm" value={roomEdit.category_id ?? r.category_id} onChange={(e) => setRoomEdit((p) => ({ ...p, category_id: parseInt(e.target.value, 10) }))}>
                          {(categoriesQuery.data ?? []).map((c) => (
                            <option key={c.id} value={c.id}>{c.name}</option>
                          ))}
                        </select>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <select className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm" value={roomEdit.status ?? r.status} onChange={(e) => setRoomEdit((p) => ({ ...p, status: e.target.value as RoomStatus }))}>
                          {roomStatuses.map((s) => (
                            <option key={s} value={s}>{s}</option>
                          ))}
                        </select>
                        <label className="flex items-center gap-2 text-xs text-slate-700">
                          <input type="checkbox" checked={roomEdit.is_active ?? r.is_active} onChange={(e) => setRoomEdit((p) => ({ ...p, is_active: e.target.checked }))} />
                          Activa
                        </label>
                      </div>
                      <input className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm" placeholder="Notas" value={roomEdit.notes ?? r.notes ?? ""} onChange={(e) => setRoomEdit((p) => ({ ...p, notes: e.target.value }))} />
                      <div className="flex gap-2">
                        <button type="button" className="rounded-lg bg-brand-600 px-3 py-1 text-xs font-semibold text-white" onClick={() => updateRoomMutation.mutate({ id: r.id, payload: roomEdit })}>Guardar</button>
                        <button type="button" className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-700" onClick={() => { setEditingRoomId(null); setRoomEdit({}); }}>Cancelar</button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">Hab {r.room_number} · Piso {r.floor}</p>
                        {r.category && <p className="text-xs text-slate-600">Categoría: {r.category.name}</p>}
                        <p className="text-xs text-slate-500">Estado: {r.status}</p>
                        {r.notes && <p className="text-xs text-slate-500">Notas: {r.notes}</p>}
                      </div>
                      <button type="button" className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-700" onClick={() => { setEditingRoomId(r.id); setRoomEdit({}); }}>Editar</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-end gap-3">
            {updateConfigMutation.isError && <p className="text-sm text-rose-700">No se pudo guardar.</p>}
            {updateConfigMutation.isSuccess && <p className="text-sm text-emerald-700">Cambios guardados.</p>}
            <button type="submit" className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60" disabled={updateConfigMutation.isPending}>
              Guardar cambios
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

export default SettingsHotelPage;
