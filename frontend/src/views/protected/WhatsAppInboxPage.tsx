import { useMemo, useState } from "react";

import { useWhatsAppCRM } from "../../hooks/useWhatsappCRM";

export function WhatsAppInboxPage() {
  const { channel, conversations, send, note, assign } = useWhatsAppCRM();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [noteDraft, setNoteDraft] = useState("");
  const [assignee, setAssignee] = useState("");
  const items = useMemo(() => conversations.data?.items ?? [], [conversations.data?.items]);
  const selected = useMemo(() => items.find((item) => item.id === selectedId) ?? items[0], [items, selectedId]);

  if (channel.isLoading || conversations.isLoading) return <p>Cargando bandeja de WhatsApp...</p>;
  if (channel.isError || conversations.isError) return <p role="alert">No se pudo cargar WhatsApp. Verifica el plan y vuelve a intentar.</p>;
  if (channel.data?.status === "ready" && !channel.data.channel) return <p>WhatsApp está listo para conectar desde Configuración.</p>;

  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs uppercase tracking-wide text-slate-500">CRM humano</p>
        <h1 className="text-2xl font-semibold text-slate-900">Bandeja de WhatsApp</h1>
        <p className="text-sm text-slate-600">Los mensajes se encolan en el PMS y quedan auditados por hotel.</p>
      </div>
      <div className="grid min-h-[520px] gap-4 lg:grid-cols-[280px_1fr]">
        <section className="rounded-xl border border-slate-200 bg-white p-3">
          <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Conversaciones</h2><span className="text-xs text-slate-500">{items.length}</span></div>
          {items.length === 0 ? <p className="text-sm text-slate-500">No hay conversaciones todavía.</p> : items.map((item) => (
            <button key={item.id} type="button" onClick={() => setSelectedId(item.id)} className={`mb-2 w-full rounded-lg border p-3 text-left ${selected?.id === item.id ? "border-brand-500 bg-brand-50" : "border-slate-100"}`}>
              <p className="text-sm font-semibold">{item.contact.display_name || item.contact.normalized_phone}</p>
              <p className="text-xs text-slate-500">{item.status} · {item.assigned_to_user_id ? `Asignada a ${item.assigned_to_user_id}` : "Sin asignar"}</p>
            </button>
          ))}
        </section>
        <section className="flex flex-col rounded-xl border border-slate-200 bg-white p-4">
          {!selected ? <p className="text-sm text-slate-500">Selecciona una conversación.</p> : <>
            <div className="border-b border-slate-100 pb-3"><h2 className="font-semibold">{selected.contact.display_name || selected.contact.normalized_phone}</h2><p className="text-xs text-slate-500">Estado: {selected.status} · ventana: {selected.service_window_expires_at || "no informada"}</p></div>
            <div className="flex-1 space-y-2 overflow-auto py-4">{selected.messages.map((message) => <div key={message.id} className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${message.direction === "outbound" ? "ml-auto bg-brand-50" : "bg-slate-100"}`}><p>{message.text || `[${message.message_type}]`}</p><p className="mt-1 text-[10px] text-slate-500">{message.status}</p></div>)}</div>
            <div className="space-y-2 border-t border-slate-100 pt-3"><div className="flex gap-2"><input className="min-w-0 flex-1 rounded border px-3 py-2 text-sm" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Responder al huésped" /><button type="button" disabled={!draft.trim() || send.isPending} onClick={() => { send.mutate({ id: selected.id, text: draft.trim() }); setDraft(""); }} className="rounded bg-brand-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">Enviar</button></div><div className="flex gap-2"><input className="min-w-0 flex-1 rounded border px-3 py-2 text-sm" value={noteDraft} onChange={(event) => setNoteDraft(event.target.value)} placeholder="Nota interna" /><button type="button" disabled={!noteDraft.trim() || note.isPending} onClick={() => { note.mutate({ id: selected.id, body: noteDraft.trim() }); setNoteDraft(""); }} className="rounded border px-3 py-2 text-sm font-semibold">Guardar nota</button></div><div className="flex gap-2"><input className="w-40 rounded border px-3 py-2 text-sm" value={assignee} onChange={(event) => setAssignee(event.target.value)} placeholder="ID responsable" /><button type="button" onClick={() => assign.mutate({ id: selected.id, userId: assignee.trim() ? Number(assignee) : null })} className="rounded border px-3 py-2 text-sm font-semibold">Asignar</button></div></div>
          </>}
        </section>
      </div>
    </div>
  );
}
