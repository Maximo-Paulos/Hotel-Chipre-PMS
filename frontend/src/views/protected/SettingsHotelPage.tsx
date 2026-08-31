import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getHotelConfig, updateHotelConfig, type HotelConfig } from "../../api/config";
import {
  createRoomCategory,
  updateRoomCategory,
  createRoom,
  updateRoom,
  deleteRoom,
  type RoomDeleteBlockedDetail,
  type RoomDeleteBlockingReservation,
  type RoomCategory,
  type RoomStatus
} from "../../api/rooms";
import { moveReservationRoom } from "../../api/reservations";
import { useSession } from "../../state/session";
import { ApiError, hasValidSession } from "../../api/client";
import { useTimezones } from "../../hooks/useTimezones";
import { useRooms } from "../../hooks/useRooms";
import { refreshAfterMutation, refreshRoomState } from "../../api/queryInvalidation";
import { usePaymentSurcharges, usePaymentSurchargeMutations } from "../../hooks/usePaymentSurcharges";
import { type PaymentSurchargeType } from "../../api/paymentSurcharges";
import { useEffectivePermissions } from "../../hooks/usePermissions";
import { useGuardedMutation } from "../../hooks/useGuardedMutation";
import { useCollaborativeResource } from "../../hooks/useCollaborativeResource";
import { moveBlockedReason, requiredMovePermission } from "../../utils/roomMove";

const roomStatuses: RoomStatus[] = ["available", "occupied", "maintenance", "blocked", "cleaning"];

type RoomDeleteState = {
  roomId: number;
  blockingReservations: RoomDeleteBlockingReservation[];
  requiresFinalConfirmation: boolean;
};

type RoomMovePermissionBlocker = {
  confirmationCode: string;
  missingPermissions: Array<{ code: string; reason: string }>;
};

function isRoomDeleteBlockedDetail(value: unknown): value is RoomDeleteBlockedDetail {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<RoomDeleteBlockedDetail>;
  return (
    typeof candidate.message === "string" &&
    Array.isArray(candidate.reservations) &&
    candidate.reservations.every(
      (reservation) =>
        reservation &&
        typeof reservation.id === "number" &&
        typeof reservation.confirmation_code === "string" &&
        typeof reservation.guest_name === "string" &&
        typeof reservation.check_in_date === "string" &&
        typeof reservation.check_out_date === "string" &&
        typeof reservation.status === "string" &&
        typeof reservation.category_id === "number"
    )
  );
}

function getRoomDeleteBlockedDetail(error: unknown): RoomDeleteBlockedDetail | null {
  if (!(error instanceof ApiError) || error.status !== 400 || !error.payload || typeof error.payload !== "object") {
    return null;
  }
  const detail = (error.payload as { detail?: unknown }).detail;
  return isRoomDeleteBlockedDetail(detail) ? detail : null;
}

const paymentMethodConfigOptions: Array<{ key: keyof HotelConfig; label: string; helper: string }> = [
  { key: "enable_cash", label: "Efectivo", helper: "Se registra en caja." },
  { key: "enable_debit_card", label: "Tarjeta de débito", helper: "Cobro manual con tarjeta." },
  { key: "enable_credit_card", label: "Tarjeta de crédito", helper: "Cobro manual con tarjeta." },
  { key: "enable_mercado_pago", label: "Mercado Pago", helper: "Links y confirmación por webhook." },
  { key: "enable_bank_transfer", label: "Transferencia", helper: "Requiere comprobante y aprobación." },
  { key: "enable_paypal", label: "PayPal", helper: "Gateway externo." }
];

const surchargeMethodOptions: { value: string; label: string }[] = [
  { value: "cash", label: "Efectivo" },
  { value: "mercado_pago", label: "MercadoPago" },
  { value: "credit_card", label: "Tarjeta de crédito" },
  { value: "debit_card", label: "Tarjeta de débito" },
  { value: "bank_transfer", label: "Transferencia" },
  { value: "paypal", label: "PayPal" }
];
const surchargeMethodLabel = (value: string) =>
  surchargeMethodOptions.find((o) => o.value === value)?.label ?? value;

export function SettingsHotelPage() {
  const { session } = useSession();
  const { hasPermission, permissionsKnown } = useEffectivePermissions();
  const qc = useQueryClient();
  const timezonesQuery = useTimezones();
  const { categoriesQuery, roomsQuery } = useRooms({ includeCategories: true });
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
  const [roomDeleteState, setRoomDeleteState] = useState<RoomDeleteState | null>(null);
  const [roomMoveDestinations, setRoomMoveDestinations] = useState<Record<number, string>>({});
  const [movingReservationId, setMovingReservationId] = useState<number | null>(null);
  const editingRoom = useMemo(
    () => (roomsQuery.data ?? []).find((room) => room.id === editingRoomId) ?? null,
    [editingRoomId, roomsQuery.data]
  );
  const collaborativeRoom = useCollaborativeResource({
    resourceType: "room",
    resourceId: editingRoom?.id,
    initialValues: editingRoom
      ? {
          room_number: editingRoom.room_number,
          floor: editingRoom.floor,
          category_id: editingRoom.category_id,
          notes: editingRoom.notes ?? null
        }
      : null,
    enabled: Boolean(editingRoom && hasPermission("room:status_update"))
  });

  const invalidateRoomAndReservationQueries = () =>
    refreshAfterMutation(qc, session.hotelId, ["rooms", "reservations", "analytics"]);

  const configQuery = useQuery({
    queryKey: ["hotel-config", session.hotelId],
    enabled: hasValidSession(session),
    queryFn: () => getHotelConfig(session)
  });

  useEffect(() => {
    if (configQuery.data) setForm(configQuery.data);
  }, [configQuery.data]);

  const updateConfigMutation = useGuardedMutation({
    mutationFn: (payload: Partial<HotelConfig>) => updateHotelConfig(payload, session),
    onSuccess: async (data) => {
      setForm(data);
      setError(null);
      await refreshAfterMutation(qc, session.hotelId, ["settings", "reservations", "rooms", "analytics"]);
    },
    onError: (err: unknown) => setError(err instanceof Error ? err.message : "No se pudo guardar la configuración")
  });

  const createCategoryMutation = useGuardedMutation({
    mutationFn: (payload: Omit<RoomCategory, "id">) => createRoomCategory(payload, session),
    onSuccess: async () => {
      await refreshRoomState(qc, session.hotelId);
      setCategoryForm({ name: "", code: "", description: "", base_price_per_night: 0, max_occupancy: 1, amenities: "" });
      setError(null);
    },
    onError: (err: unknown) => setError(err instanceof Error ? err.message : "No se pudo crear la categoría")
  });

  const updateCategoryMutation = useGuardedMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<Omit<RoomCategory, "id">> }) => updateRoomCategory(id, payload, session),
    onSuccess: async () => {
      await refreshRoomState(qc, session.hotelId);
      setEditingCategoryId(null);
      setCategoryEdit({});
      setError(null);
    },
    onError: (err: unknown) => setError(err instanceof Error ? err.message : "No se pudo actualizar la categoría")
  });

  const createRoomMutation = useGuardedMutation({
    mutationFn: (payload: { room_number: string; floor: number; category_id: number; notes?: string }) =>
      createRoom({ ...payload, status: "available", is_active: true }, session),
    onSuccess: async () => {
      await refreshRoomState(qc, session.hotelId);
      setRoomForm({ room_number: "", floor: 1, category_id: 0, notes: "" });
      setError(null);
    },
    onError: (err: unknown) => setError(err instanceof Error ? err.message : "No se pudo crear la habitación")
  });

  const updateRoomMutation = useGuardedMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<{ room_number: string; floor: number; category_id: number; status: RoomStatus; is_active: boolean; notes?: string }> }) =>
      updateRoom(id, payload, session),
    onSuccess: async () => {
      await refreshRoomState(qc, session.hotelId);
      setEditingRoomId(null);
      setRoomEdit({});
      setError(null);
    },
    onError: (err: unknown) => setError(err instanceof Error ? err.message : "No se pudo actualizar la habitación")
  });

  const deleteRoomMutation = useGuardedMutation<void, unknown, number>({
    mutationFn: (roomId) => deleteRoom(roomId, session),
    onSuccess: async () => {
      await invalidateRoomAndReservationQueries();
      setRoomDeleteState(null);
      setRoomMoveDestinations({});
      setError(null);
    },
    onError: (err: unknown) => {
      const blocked = getRoomDeleteBlockedDetail(err);
      if (blocked) {
        setRoomDeleteState((current) =>
          current
            ? {
                ...current,
                blockingReservations: blocked.reservations,
                requiresFinalConfirmation: true
              }
            : current
        );
        setRoomMoveDestinations({});
        setError(null);
        return;
      }
      setError(err instanceof Error ? err.message : "No se pudo eliminar la habitación");
    }
  });

  const moveBlockingReservationMutation = useGuardedMutation<
    unknown,
    unknown,
    { reservationId: number; toRoomId: number }
  >({
    mutationFn: ({ reservationId, toRoomId }) =>
      moveReservationRoom(reservationId, { to_room_id: toRoomId, reason_code: "operational" }, session),
    onMutate: ({ reservationId }) => {
      setMovingReservationId(reservationId);
      setError(null);
    },
    onSuccess: async (_result, { reservationId }) => {
      await invalidateRoomAndReservationQueries();
      setRoomDeleteState((current) =>
        current
          ? {
              ...current,
              blockingReservations: current.blockingReservations.filter(
                (reservation) => reservation.id !== reservationId
              )
            }
          : current
      );
      setRoomMoveDestinations((current) => {
        const { [reservationId]: movedReservation, ...remaining } = current;
        void movedReservation;
        return remaining;
      });
    },
    onError: (err: unknown) =>
      setError(err instanceof Error ? err.message : "No se pudo reubicar la reserva"),
    onSettled: () => setMovingReservationId(null)
  });

  const roomDeleteMoveDestinations = useMemo(() => {
    if (!roomDeleteState) return [];
    return (roomsQuery.data ?? []).filter(
      (room) =>
        room.id !== roomDeleteState.roomId &&
        room.is_active &&
        room.status !== "maintenance" &&
        room.status !== "blocked"
    );
  }, [roomDeleteState, roomsQuery.data]);

  const roomCategoryById = useMemo(() => {
    const categories = new Map<number, { id: number; max_occupancy: number }>();
    (categoriesQuery.data ?? []).forEach((category) => {
      categories.set(category.id, { id: category.id, max_occupancy: category.max_occupancy });
    });
    return categories;
  }, [categoriesQuery.data]);

  const roomMovePermissionBlockers = useMemo<RoomMovePermissionBlocker[]>(() => {
    if (!roomDeleteState?.requiresFinalConfirmation) return [];

    return roomDeleteState.blockingReservations.flatMap((reservation) => {
      const from = roomCategoryById.get(reservation.category_id);
      const missingPermissions = roomDeleteMoveDestinations.flatMap((destination) => {
        const to = roomCategoryById.get(destination.category_id);
        const reason = moveBlockedReason(from, to, hasPermission);
        if (!reason || !from || !to) return [];
        return [{ code: requiredMovePermission(from, to), reason }];
      });
      const everyDestinationIsBlocked =
        roomDeleteMoveDestinations.length > 0 && missingPermissions.length === roomDeleteMoveDestinations.length;
      if (!everyDestinationIsBlocked) return [];
      const uniquePermissions = Array.from(
        new Map(missingPermissions.map((permission) => [permission.code, permission])).values()
      );
      return [{ confirmationCode: reservation.confirmation_code, missingPermissions: uniquePermissions }];
    });
  }, [hasPermission, roomCategoryById, roomDeleteMoveDestinations, roomDeleteState]);

  const handleChange = (key: keyof HotelConfig, value: unknown) => setForm((prev) => ({ ...prev, [key]: value }));
  const handleRoomEditField = (field: "room_number" | "floor" | "category_id" | "notes", value: unknown) => {
    setRoomEdit((current) => ({ ...current, [field]: value }));
    collaborativeRoom.setField(field, value);
  };
  const handleSaveRoom = async (roomId: number) => {
    if (editingRoomId !== roomId) return;
    if (Object.keys(collaborativeRoom.conflicts).length > 0) {
      setError("Hay conflictos en la habitación. Elegí qué valor conservar antes de guardar.");
      return;
    }
    try {
      const collaborationActive = collaborativeRoom.status !== "idle";
      if (collaborationActive && collaborativeRoom.isDirty) {
        await collaborativeRoom.save();
        const operationalChanges: typeof roomEdit = {};
        if (roomEdit.status !== undefined && roomEdit.status !== editingRoom?.status) {
          operationalChanges.status = roomEdit.status;
        }
        if (roomEdit.is_active !== undefined && roomEdit.is_active !== editingRoom?.is_active) {
          operationalChanges.is_active = roomEdit.is_active;
        }
        if (Object.keys(operationalChanges).length > 0) {
          await updateRoomMutation.mutateAsync({ id: roomId, payload: operationalChanges });
        } else {
          setEditingRoomId(null);
          setRoomEdit({});
          setError(null);
        }
        return;
      }
      if (collaborationActive) {
        // Editable metadata is owned by the collaboration resource. If this
        // editor is clean, sending the stale local fallback would overwrite a
        // remote change that arrived after the form was opened. Only persist
        // the intentionally non-mergeable operational fields here.
        const operationalChanges: typeof roomEdit = {};
        if (roomEdit.status !== undefined && roomEdit.status !== editingRoom?.status) {
          operationalChanges.status = roomEdit.status;
        }
        if (roomEdit.is_active !== undefined && roomEdit.is_active !== editingRoom?.is_active) {
          operationalChanges.is_active = roomEdit.is_active;
        }
        if (Object.keys(operationalChanges).length > 0) {
          await updateRoomMutation.mutateAsync({ id: roomId, payload: operationalChanges });
        } else {
          setEditingRoomId(null);
          setRoomEdit({});
          setError(null);
        }
        return;
      }
      await updateRoomMutation.mutateAsync({ id: roomId, payload: roomEdit });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo actualizar la habitación");
    }
  };
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await updateConfigMutation.mutateAsync(form);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo guardar la configuración");
    }
  };

  const ownerOnly = session.baseRole === "owner";
  const canDeleteRooms = permissionsKnown && hasPermission("hotel_settings:update");

  if (!hasValidSession(session)) return <p className="text-sm text-slate-600">Iniciá sesión con un hotel activo para editar la configuración.</p>;

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
              <input
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                value={form.hotel_timezone ?? ""}
                onChange={(e) => handleChange("hotel_timezone", e.target.value)}
                list="hotel-timezones"
              />
              <datalist id="hotel-timezones">
                {(timezonesQuery.data ?? []).map((timezone) => (
                  <option key={timezone} value={timezone} />
                ))}
              </datalist>
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
            <label className="text-sm font-semibold text-slate-700">
              Penalidad por cancelación (%)
              <input type="number" min={0} max={100} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" value={form.cancellation_penalty_percentage ?? 0} onChange={(e) => handleChange("cancellation_penalty_percentage", parseFloat(e.target.value || "0"))} />
            </label>
            <label className="text-sm font-semibold text-slate-700">
              Idiomas (separados por coma)
              <input className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" value={(form.languages ?? []).join(", ")} onChange={(e) => handleChange("languages", e.target.value.split(",").map((item) => item.trim()).filter(Boolean))} />
            </label>
            <label className="text-sm font-semibold text-slate-700">
              Jurisdicción
              <input maxLength={3} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm uppercase" value={form.jurisdiction_code ?? "AR"} onChange={(e) => handleChange("jurisdiction_code", e.target.value.toUpperCase())} />
            </label>
          </div>

          {ownerOnly && (
            <div className="rounded-lg border border-slate-200 p-4">
              <h3 className="text-sm font-semibold text-slate-800">Medios de pago habilitados</h3>
              <p className="mt-1 text-xs text-slate-500">
                Solo se muestran en reservas y cobros los medios activos. Transferencia exige comprobante; Mercado Pago se confirma por webhook.
              </p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {paymentMethodConfigOptions.map((option) => (
                  <label key={option.key} className="flex items-start gap-2 rounded-lg border border-slate-200 p-3 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={Boolean(form[option.key])}
                      onChange={(event) => handleChange(option.key, event.target.checked)}
                      className="mt-0.5"
                    />
                    <span>
                      <span className="block font-semibold text-slate-800">{option.label}</span>
                      <span className="block text-xs text-slate-500">{option.helper}</span>
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {ownerOnly && (
            <label className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-slate-700">
              <input type="checkbox" checked={Boolean(form.allow_overbooking)} onChange={(event) => handleChange("allow_overbooking", event.target.checked)} className="mt-0.5" />
              <span><span className="block font-semibold text-amber-900">Permitir sobreventa</span><span className="block text-xs text-amber-800">Si no hay habitaciones libres, la reserva queda explícitamente en lista de espera.</span></span>
            </label>
          )}

          {/* Categorías */}
          <div className="rounded-lg border border-slate-200 p-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-slate-800">Categorías de habitación</h3>
                <p className="text-xs text-slate-500">Agregar y editar categorías para este hotel. El precio efectivo prioriza tarifa diaria, luego precio por temporada y finalmente precio base.</p>
              </div>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Nombre" value={categoryForm.name} onChange={(e) => setCategoryForm((p) => ({ ...p, name: e.target.value }))} />
              <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Código" value={categoryForm.code} onChange={(e) => setCategoryForm((p) => ({ ...p, code: e.target.value }))} />
              <input type="number" min={1} className="rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Precio base" value={categoryForm.base_price_per_night} onChange={(e) => setCategoryForm((p) => ({ ...p, base_price_per_night: parseFloat(e.target.value || "0") }))} />
              <input type="number" min={1} className="rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Ocupación máx" value={categoryForm.max_occupancy} onChange={(e) => setCategoryForm((p) => ({ ...p, max_occupancy: parseInt(e.target.value || "1", 10) }))} />
              <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm md:col-span-2" placeholder="Amenidades" value={categoryForm.amenities ?? ""} onChange={(e) => setCategoryForm((p) => ({ ...p, amenities: e.target.value }))} />
              <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm md:col-span-3" placeholder="Descripción" value={categoryForm.description ?? ""} onChange={(e) => setCategoryForm((p) => ({ ...p, description: e.target.value }))} />
              <button type="button" className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60" disabled={createCategoryMutation.isPending || !categoryForm.name || !categoryForm.code || categoryForm.base_price_per_night <= 0 || categoryForm.max_occupancy <= 0} onClick={() => void createCategoryMutation.mutateAsync(categoryForm).catch(() => undefined)}>
                {createCategoryMutation.isPending ? "Guardando..." : "Agregar categoría"}
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
                        <button type="button" className="rounded-lg bg-brand-600 px-3 py-1 text-xs font-semibold text-white" onClick={() => void updateCategoryMutation.mutateAsync({ id: c.id, payload: categoryEdit }).catch(() => undefined)}>Guardar</button>
                        <button type="button" className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-700" onClick={() => { setEditingCategoryId(null); setCategoryEdit({}); }}>Cancelar</button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{c.name} ({c.code})</p>
                        <p className="text-xs text-slate-600">Ocupación: {c.max_occupancy} · Precio base: {c.base_price_per_night}</p>
                        <p className="text-xs font-medium text-emerald-700">Precio efectivo hoy: {c.current_rate ?? c.base_price_per_night} · gana {c.current_rate_source === "daily_rate" ? "tarifa diaria" : c.current_rate_source === "price_period" ? "precio por temporada" : "precio base"}</p>
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
              <button type="button" className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60 md:col-span-2" disabled={createRoomMutation.isPending || !roomForm.room_number || !roomForm.category_id} onClick={() => void createRoomMutation.mutateAsync(roomForm).catch(() => undefined)}>
                {createRoomMutation.isPending ? "Guardando..." : "Agregar habitación"}
              </button>
            </div>
            <div className="mt-4 grid gap-2 md:grid-cols-3">
              {(roomsQuery.data ?? []).map((r) => (
                <div key={r.id} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">
                  {editingRoomId === r.id ? (
                    <div className="space-y-2">
                      <input className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm" value={String(collaborativeRoom.draftValues.room_number ?? roomEdit.room_number ?? r.room_number)} onChange={(e) => handleRoomEditField("room_number", e.target.value)} onFocus={() => collaborativeRoom.focusField("room_number")} onBlur={() => collaborativeRoom.blurField("room_number")} />
                      <div className="grid grid-cols-2 gap-2">
                        <input type="number" className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm" value={Number(collaborativeRoom.draftValues.floor ?? roomEdit.floor ?? r.floor)} onChange={(e) => handleRoomEditField("floor", parseInt(e.target.value || "1", 10))} onFocus={() => collaborativeRoom.focusField("floor")} onBlur={() => collaborativeRoom.blurField("floor")} />
                        <select className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm" value={Number(collaborativeRoom.draftValues.category_id ?? roomEdit.category_id ?? r.category_id)} onChange={(e) => handleRoomEditField("category_id", parseInt(e.target.value, 10))} onFocus={() => collaborativeRoom.focusField("category_id")} onBlur={() => collaborativeRoom.blurField("category_id")}>
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
                      <input className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm" placeholder="Notas" value={String(collaborativeRoom.draftValues.notes ?? roomEdit.notes ?? r.notes ?? "")} onChange={(e) => handleRoomEditField("notes", e.target.value || null)} onFocus={() => collaborativeRoom.focusField("notes")} onBlur={() => collaborativeRoom.blurField("notes")} />
                      {collaborativeRoom.status !== "idle" && (
                        <div className="rounded-lg border border-sky-200 bg-sky-50 p-2 text-xs text-sky-900" role="status">
                          <p>
                            {collaborativeRoom.status === "connected"
                              ? `Coedición conectada${collaborativeRoom.peers.length ? ` · ${collaborativeRoom.peers.length} usuario(s) más` : ""}`
                              : collaborativeRoom.status === "saving"
                                ? "Guardando cambios..."
                                : collaborativeRoom.status === "conflict"
                                  ? "Conflicto pendiente"
                                  : collaborativeRoom.status === "degraded"
                                    ? "Coedición degradada"
                                    : "Conectando..."}
                          </p>
                          {collaborativeRoom.peers.filter((peer) => peer.fields.length > 0).map((peer) => (
                            <p key={peer.connectionId} className="mt-1">Otro usuario está editando: {peer.fields.join(", ")}</p>
                          ))}
                        </div>
                      )}
                      {Object.values(collaborativeRoom.conflicts).map((conflict) => (
                        <div key={conflict.field} className="rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-950" data-testid={`room-conflict-${conflict.field}`}>
                          <p className="font-semibold">Conflicto en {conflict.field}</p>
                          <p>Propio: {String(conflict.localValue ?? "(vacío)")}</p>
                          <p>Remoto: {String(conflict.remoteValue ?? "(vacío)")}</p>
                          <div className="mt-1 flex gap-2">
                            <button type="button" className="rounded border border-amber-300 bg-white px-2 py-1 font-semibold" onClick={() => collaborativeRoom.keepMine(conflict.field)}>Conservar el mío</button>
                            <button type="button" className="rounded border border-amber-300 bg-white px-2 py-1 font-semibold" onClick={() => collaborativeRoom.useRemote(conflict.field)}>Usar remoto</button>
                          </div>
                        </div>
                      ))}
                      <div className="flex gap-2">
                        <button type="button" className="rounded-lg bg-brand-600 px-3 py-1 text-xs font-semibold text-white" disabled={updateRoomMutation.isPending || collaborativeRoom.isSaving} onClick={() => void handleSaveRoom(r.id)}>Guardar</button>
                        <button type="button" className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-700" onClick={() => { setEditingRoomId(null); setRoomEdit({}); }}>Cancelar</button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-slate-900">Hab {r.room_number} · Piso {r.floor}</p>
                          {r.category && <p className="text-xs text-slate-600">Categoría: {r.category.name}</p>}
                          <p className="text-xs text-slate-500">Estado: {r.status}</p>
                          {r.notes && <p className="text-xs text-slate-500">Notas: {r.notes}</p>}
                        </div>
                        <div className="flex shrink-0 gap-2">
                          <button type="button" className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-700" onClick={() => { setEditingRoomId(r.id); setRoomEdit({}); }}>Editar</button>
                          {canDeleteRooms && (
                            <button
                              type="button"
                              className="rounded-lg border border-rose-200 px-3 py-1 text-xs font-semibold text-rose-700 hover:bg-rose-50"
                              onClick={() => {
                                setRoomDeleteState({ roomId: r.id, blockingReservations: [], requiresFinalConfirmation: false });
                                setRoomMoveDestinations({});
                                setError(null);
                              }}
                            >
                              Eliminar
                            </button>
                          )}
                        </div>
                      </div>

                      {roomDeleteState?.roomId === r.id && (
                        <div className="mt-3 space-y-3 rounded-lg border border-rose-200 bg-rose-50 p-3">
                          <div>
                            <p className="text-sm font-semibold text-rose-900">¿Eliminar la habitación {r.room_number}?</p>
                            <p className="mt-1 text-xs text-rose-800">El historial de reservas se conserva.</p>
                          </div>

                          {!roomDeleteState.requiresFinalConfirmation ? (
                            <div className="flex gap-2">
                              <button
                                type="button"
                                className="rounded-lg bg-rose-600 px-3 py-1 text-xs font-semibold text-white hover:bg-rose-700 disabled:opacity-60"
                                disabled={deleteRoomMutation.isPending}
                                onClick={() => void deleteRoomMutation.mutateAsync(r.id).catch(() => undefined)}
                              >
                                {deleteRoomMutation.isPending ? "Eliminando..." : "Sí, eliminar"}
                              </button>
                              <button
                                type="button"
                                className="rounded-lg border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700"
                                onClick={() => {
                                  setRoomDeleteState(null);
                                  setRoomMoveDestinations({});
                                  setError(null);
                                }}
                              >
                                Cancelar
                              </button>
                            </div>
                          ) : (
                            <div className="space-y-3">
                              {roomDeleteState.blockingReservations.length > 0 ? (
                                <p className="text-xs text-rose-800">No se puede eliminar hasta reubicar las reservas activas o futuras.</p>
                              ) : (
                                /* Every blocker was relocated in this panel: saying "no se puede"
                                   next to an enabled delete button contradicts itself. */
                                <p className="text-xs text-emerald-800">Ya no quedan reservas en esta habitación. Podés eliminarla.</p>
                              )}

                              <div className="space-y-2">
                                {roomDeleteState.blockingReservations.map((reservation) => {
                                  const fromCategory = roomCategoryById.get(reservation.category_id);
                                  const selectedDestination = roomDeleteMoveDestinations.find(
                                    (destination) => destination.id === Number(roomMoveDestinations[reservation.id])
                                  );
                                  const selectedDestinationBlockedReason = selectedDestination
                                    ? moveBlockedReason(
                                        fromCategory,
                                        roomCategoryById.get(selectedDestination.category_id),
                                        hasPermission
                                      )
                                    : null;

                                  return (
                                    <div key={reservation.id} className="space-y-2 rounded-lg border border-rose-200 bg-white p-3">
                                      <div>
                                        <p className="text-sm font-semibold text-slate-900">{reservation.confirmation_code} · {reservation.guest_name}</p>
                                        <p className="text-xs text-slate-600">{reservation.check_in_date} al {reservation.check_out_date}</p>
                                      </div>
                                      <div className="flex flex-wrap gap-2">
                                        <select
                                          className="min-w-48 flex-1 rounded-lg border border-slate-200 px-3 py-1 text-xs"
                                          value={roomMoveDestinations[reservation.id] ?? ""}
                                          disabled={movingReservationId === reservation.id}
                                          onChange={(event) => setRoomMoveDestinations((current) => ({
                                            ...current,
                                            [reservation.id]: event.target.value
                                          }))}
                                        >
                                          <option value="">Elegí una habitación destino</option>
                                          {roomDeleteMoveDestinations.map((destination) => {
                                            const blockedReason = moveBlockedReason(
                                              fromCategory,
                                              roomCategoryById.get(destination.category_id),
                                              hasPermission
                                            );
                                            return (
                                              <option key={destination.id} value={destination.id} disabled={Boolean(blockedReason)}>
                                                Hab {destination.room_number} · Piso {destination.floor}{blockedReason ? ` — ${blockedReason}` : ""}
                                              </option>
                                            );
                                          })}
                                        </select>
                                        <button
                                          type="button"
                                          className="rounded-lg bg-brand-600 px-3 py-1 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                                          disabled={
                                            movingReservationId === reservation.id ||
                                            !selectedDestination ||
                                            Boolean(selectedDestinationBlockedReason)
                                          }
                                          onClick={() => {
                                            if (!selectedDestination) {
                                              setError("Elegí una habitación destino para reubicar la reserva.");
                                              return;
                                            }
                                            if (selectedDestinationBlockedReason) {
                                              setError(selectedDestinationBlockedReason);
                                              return;
                                            }
                                            void moveBlockingReservationMutation.mutateAsync({
                                              reservationId: reservation.id,
                                              toRoomId: selectedDestination.id
                                            }).catch(() => undefined);
                                          }}
                                        >
                                          {movingReservationId === reservation.id ? "Reubicando..." : "Reubicar"}
                                        </button>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>

                              {roomMovePermissionBlockers.length > 0 && (
                                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                                  <p className="font-semibold">No tenés permisos para reubicar algunas reservas.</p>
                                  <ul className="mt-1 list-disc space-y-1 pl-4">
                                    {roomMovePermissionBlockers.map((blocker) => (
                                      <li key={blocker.confirmationCode}>
                                        Reserva {blocker.confirmationCode}: {blocker.missingPermissions.map((permission) => `${permission.reason} (${permission.code})`).join(", ")}. Necesitás que alguien con ese permiso la reubique.
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              {roomDeleteState.blockingReservations.length === 0 && (
                                <button
                                  type="button"
                                  className="rounded-lg bg-rose-600 px-3 py-1 text-xs font-semibold text-white hover:bg-rose-700 disabled:opacity-60"
                                  disabled={deleteRoomMutation.isPending}
                                  onClick={() => void deleteRoomMutation.mutateAsync(r.id).catch(() => undefined)}
                                >
                                  {deleteRoomMutation.isPending ? "Eliminando..." : "Eliminar habitación definitivamente"}
                                </button>
                              )}

                              <button
                                type="button"
                                className="rounded-lg border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700"
                                onClick={() => {
                                  setRoomDeleteState(null);
                                  setRoomMoveDestinations({});
                                  setError(null);
                                }}
                              >
                                Cancelar
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-end gap-3">
            {updateConfigMutation.isError && <p className="text-sm text-rose-700">No se pudo guardar.</p>}
            {updateConfigMutation.isSuccess && <p className="text-sm text-emerald-700">Cambios guardados.</p>}
            <button
              type="submit"
              formNoValidate
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
              disabled={updateConfigMutation.isPending}
            >
              Guardar cambios
            </button>
          </div>
        </form>
      )}

      <TarifasPromocionesPagosSection />
    </div>
  );
}

function TarifasPromocionesPagosSection() {
  return (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Tarifas, promociones y pagos</h2>
          <p className="text-sm text-slate-600">
            El calendario de tarifas y el generador de promociones sin código viven en pantallas propias; acá se
            configuran los recargos y descuentos por medio de pago que se aplican junto con ellas.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/operacion/tarifas"
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Ir a Tarifas
          </Link>
          <Link
            to="/operacion/promociones"
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
          >
            Ir a Promociones
          </Link>
        </div>
      </div>
      <PaymentSurchargesCard />
    </section>
  );
}

function PaymentSurchargesCard() {
  const surchargesQuery = usePaymentSurcharges();
  const { createMutation, deactivateMutation } = usePaymentSurchargeMutations();
  const [method, setMethod] = useState<string>("mercado_pago");
  const [type, setType] = useState<PaymentSurchargeType>("percentage");
  const [amount, setAmount] = useState<string>("");
  const [formError, setFormError] = useState<string | null>(null);

  const active = (surchargesQuery.data ?? []).filter((s) => s.is_active);

  const handleAdd = async () => {
    setFormError(null);
    const value = Number(amount);
    if (!Number.isFinite(value) || value < 0) {
      setFormError("Ingresá un valor válido.");
      return;
    }
    try {
      await createMutation.mutateAsync({ payment_method: method, surcharge_type: type, amount: value });
      setAmount("");
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "No se pudo guardar el recargo.");
    }
  };

  const handleDeactivate = async (id: number) => {
    try {
      await deactivateMutation.mutateAsync(id);
    } catch {
      // The shared mutation hook reports the API error to the surrounding UI.
    }
  };

  return (
    <div className="space-y-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Recargos por medio de pago</h2>
        <p className="text-sm text-slate-600">
          Se aplican sobre el monto del cobro (fijo o porcentaje) y quedan como línea separada. El cobro en efectivo
          se registra en la caja por el monto bruto.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-4 sm:items-end">
        <label className="text-sm font-semibold text-slate-700">
          Medio
          <select className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" value={method} onChange={(e) => setMethod(e.target.value)}>
            {surchargeMethodOptions.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
        <label className="text-sm font-semibold text-slate-700">
          Tipo
          <select className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" value={type} onChange={(e) => setType(e.target.value as PaymentSurchargeType)}>
            <option value="percentage">Porcentaje (%)</option>
            <option value="fixed">Monto fijo</option>
          </select>
        </label>
        <label className="text-sm font-semibold text-slate-700">
          {type === "percentage" ? "Porcentaje" : "Monto"}
          <input type="number" min={0} step="0.01" className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder={type === "percentage" ? "Ej. 10" : "Ej. 500"} />
        </label>
        <button type="button" onClick={handleAdd} disabled={createMutation.isPending} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60">
          {createMutation.isPending ? "Guardando..." : "Agregar recargo"}
        </button>
      </div>
      {formError && <p className="text-sm text-rose-700">{formError}</p>}

      <div className="space-y-2">
        {surchargesQuery.isLoading ? (
          <p className="text-sm text-slate-600">Cargando recargos...</p>
        ) : active.length === 0 ? (
          <p className="text-sm text-slate-500">No hay recargos configurados.</p>
        ) : (
          active.map((s) => (
            <div key={s.id} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm">
              <span className="text-slate-800">
                <strong>{surchargeMethodLabel(s.payment_method)}</strong>:{" "}
                {s.surcharge_type === "percentage" ? `${s.amount}%` : `$${s.amount}`}
              </span>
              <button type="button" onClick={() => void handleDeactivate(s.id)} disabled={deactivateMutation.isPending} className="rounded-lg border border-rose-200 px-3 py-1 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-60">
                Quitar
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default SettingsHotelPage;
