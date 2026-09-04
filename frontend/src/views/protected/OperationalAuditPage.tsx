import { useMemo, useState } from "react";

import { useOperationalAudit } from "../../hooks/useOperationalAudit";
import { useSession } from "../../state/session";
import { todayIso } from "../../utils/date";

const PAGE_SIZE = 50;

export function OperationalAuditPage() {
  const { session } = useSession();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState(() => todayIso());
  const [category, setCategory] = useState("");
  const [reservationId, setReservationId] = useState("");
  const [roomId, setRoomId] = useState("");
  const [actorUserId, setActorUserId] = useState("");
  const [action, setAction] = useState("");
  const [offset, setOffset] = useState(0);
  const filters = useMemo(() => ({
    limit: PAGE_SIZE,
    offset,
    from: from || undefined,
    to: to || undefined,
    category: category || undefined,
    reservation_id: reservationId ? Number(reservationId) : undefined,
    room_id: roomId ? Number(roomId) : undefined,
    actor_user_id: actorUserId ? Number(actorUserId) : undefined,
    action: action || undefined
  }), [action, actorUserId, category, from, offset, reservationId, roomId, to]);
  const auditQuery = useOperationalAudit(filters);
  const items = auditQuery.data?.items ?? [];

  return (
    <div className="space-y-6" data-testid="operational-audit-page">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
        <h1 className="text-2xl font-semibold text-slate-900">Auditoría integral</h1>
        <p className="text-sm text-slate-600">Actividad material del hotel, con actor, contexto y cambios relevantes.</p>
      </header>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="grid gap-3 md:grid-cols-4 lg:grid-cols-7">
          <label className="space-y-1 text-sm"><span>Desde</span><input type="date" value={from} onChange={(event) => { setFrom(event.target.value); setOffset(0); }} className="w-full rounded-lg border border-slate-300 px-3 py-2" /></label>
          <label className="space-y-1 text-sm"><span>Hasta</span><input type="date" value={to} onChange={(event) => { setTo(event.target.value); setOffset(0); }} className="w-full rounded-lg border border-slate-300 px-3 py-2" /></label>
          <label className="space-y-1 text-sm"><span>Área</span><select value={category} onChange={(event) => { setCategory(event.target.value); setOffset(0); }} className="w-full rounded-lg border border-slate-300 px-3 py-2"><option value="">Todas</option><option value="reservations">Reservas</option><option value="rooms">Habitaciones</option><option value="payments">Pagos</option><option value="cash">Caja</option><option value="guests">Huéspedes</option><option value="inventory">Inventario</option><option value="laundry">Lavandería</option><option value="commercial">Tarifas y promociones</option><option value="users">Usuarios</option><option value="permissions">Permisos</option><option value="configuration">Configuración</option><option value="security">Seguridad</option></select></label>
          <label className="space-y-1 text-sm"><span>Reserva</span><input inputMode="numeric" value={reservationId} onChange={(event) => { setReservationId(event.target.value.replace(/\D/g, "")); setOffset(0); }} placeholder="ID" className="w-full rounded-lg border border-slate-300 px-3 py-2" /></label>
          <label className="space-y-1 text-sm"><span>Habitación</span><input inputMode="numeric" value={roomId} onChange={(event) => { setRoomId(event.target.value.replace(/\D/g, "")); setOffset(0); }} placeholder="ID" className="w-full rounded-lg border border-slate-300 px-3 py-2" /></label>
          <label className="space-y-1 text-sm"><span>Usuario</span><input inputMode="numeric" value={actorUserId} onChange={(event) => { setActorUserId(event.target.value.replace(/\D/g, "")); setOffset(0); }} placeholder="ID" className="w-full rounded-lg border border-slate-300 px-3 py-2" /></label>
          <label className="space-y-1 text-sm"><span>Acción</span><input value={action} onChange={(event) => { setAction(event.target.value); setOffset(0); }} placeholder="Ej. room.move" className="w-full rounded-lg border border-slate-300 px-3 py-2" /></label>
        </div>
        <p className="mt-3 text-xs text-slate-500">Hotel #{session.hotelId} · Los datos sensibles permanecen redactados.</p>
      </section>

      {auditQuery.isError ? <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">No se pudo cargar la auditoría: {(auditQuery.error as Error).message}</div> : null}
      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-4 py-3"><h2 className="font-semibold text-slate-900">Actividad</h2><p className="text-xs text-slate-500">{auditQuery.data?.total ?? 0} registros encontrados</p></div>
        {auditQuery.isLoading ? <p className="p-5 text-sm text-slate-500">Cargando actividad...</p> : items.length === 0 ? <p className="p-5 text-sm text-slate-500">No hay actividad para estos filtros.</p> : (
          <div className="divide-y divide-slate-100">
            {items.map((item) => <article key={`${item.source}-${item.source_id}`} className="grid gap-2 px-4 py-4 md:grid-cols-[150px_1fr_auto]">
              <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{item.area}</p><p className="text-xs text-slate-500">{new Date(item.occurred_at).toLocaleString("es-AR")}</p></div>
              <div><p className="font-semibold text-slate-900">{item.summary}</p><p className="text-sm text-slate-600">{item.action} · {item.actor_name}</p>{item.reason_code ? <p className="text-xs text-slate-500">Motivo: {item.reason_code}{item.reason_note ? ` · ${item.reason_note}` : ""}</p> : null}{item.origin_room_disposition ? <p className="text-xs text-brand-700">Habitación origen: {item.origin_room_disposition} ({item.origin_room_status_before ?? "?"} → {item.origin_room_status_after ?? "?"})</p> : null}</div>
              <div className="text-right">{item.amount !== null && item.amount !== undefined ? <p className="font-semibold text-slate-900">{Number(item.amount).toLocaleString("es-AR", { style: "currency", currency: item.currency_code ?? "ARS" })}</p> : null}<p className="text-xs text-slate-500">#{item.source_id}</p></div>
            </article>)}
          </div>
        )}
        <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3"><button type="button" disabled={offset === 0 || auditQuery.isFetching} onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:opacity-40">Anterior</button><span className="text-xs text-slate-500">Página {Math.floor(offset / PAGE_SIZE) + 1}</span><button type="button" disabled={!auditQuery.data?.has_more || auditQuery.isFetching} onClick={() => setOffset((value) => value + PAGE_SIZE)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:opacity-40">Siguiente</button></div>
      </section>
    </div>
  );
}
