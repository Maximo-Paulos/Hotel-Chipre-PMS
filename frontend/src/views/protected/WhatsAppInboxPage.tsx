import { useLayoutEffect, useMemo, useRef, useState } from "react";

import { useWhatsAppCRM } from "../../hooks/useWhatsappCRM";

export function WhatsAppInboxPage() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { channel, conversations, messages, send, note, assign } = useWhatsAppCRM(selectedId);
  const [draft, setDraft] = useState("");
  const [noteDraft, setNoteDraft] = useState("");
  const [assignee, setAssignee] = useState("");
  const messageListRef = useRef<HTMLDivElement>(null);
  const pendingScrollAdjustment = useRef<{
    conversationId: number;
    previousPageCount: number;
    previousHeight: number;
  } | null>(null);
  const items = useMemo(() => conversations.data?.items ?? [], [conversations.data?.items]);
  const selected = useMemo(() => items.find((item) => item.id === selectedId) ?? items[0], [items, selectedId]);
  const orderedMessages = useMemo(() => {
    const uniqueMessages = new Map((messages.data?.pages ?? []).flatMap((page) => page.items).map((message) => [message.id, message]));
    return [...uniqueMessages.values()].sort((first, second) => first.id - second.id);
  }, [messages.data?.pages]);
  // An empty box means "unassign"; anything else has to be a real user id.
  const assigneeUserId = assignee.trim() ? Number(assignee.trim()) : null;
  const assigneeIsValid = assigneeUserId === null || Number.isInteger(assigneeUserId);
  const failed = send.error ?? note.error ?? assign.error;
  const sendError = failed instanceof Error ? failed.message : failed ? "No se pudo completar la acción." : null;

  const loadOlderMessages = () => {
    const container = messageListRef.current;
    if (container && selected) {
      pendingScrollAdjustment.current = {
        conversationId: selected.id,
        previousPageCount: messages.data?.pages.length ?? 0,
        previousHeight: container.scrollHeight,
      };
    }
    void messages.fetchNextPage();
  };

  useLayoutEffect(() => {
    const container = messageListRef.current;
    const pending = pendingScrollAdjustment.current;
    if (!pending) return;
    if (pending.conversationId !== selected?.id) {
      pendingScrollAdjustment.current = null;
      return;
    }
    if (!container || (messages.data?.pages.length ?? 0) <= pending.previousPageCount) return;
    container.scrollTop += container.scrollHeight - pending.previousHeight;
    pendingScrollAdjustment.current = null;
  }, [messages.data?.pages.length, selected?.id]);

  if (channel.isLoading || conversations.isLoading) return <p>Cargando bandeja de WhatsApp...</p>;
  if (channel.isError || conversations.isError) return <p role="alert">No se pudo cargar WhatsApp. Verifica el plan y vuelve a intentar.</p>;
  if (channel.data?.status === "ready" && !channel.data.channel) return <p>WhatsApp está listo para conectar desde Configuración.</p>;

  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs uppercase tracking-wide text-slate-500">CRM humano</p>
        <h1 className="text-balance text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">Bandeja de WhatsApp</h1>
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
            <div
              ref={messageListRef}
              role="region"
              aria-label="Historial de mensajes"
              aria-busy={messages.isFetchingNextPage}
              tabIndex={0}
              className="flex-1 space-y-2 overflow-auto py-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
            >
              {messages.hasNextPage ? (
                <div className="pb-2 text-center">
                  <button
                    type="button"
                    disabled={messages.isFetchingNextPage}
                    onClick={loadOlderMessages}
                    className="rounded border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-brand-400 focus:ring-offset-2 disabled:opacity-50"
                  >
                    {messages.isFetchingNextPage ? "Cargando mensajes anteriores…" : "Cargar mensajes anteriores"}
                  </button>
                </div>
              ) : null}
              {messages.isLoading ? <p role="status" className="text-center text-sm text-slate-500">Cargando mensajes…</p> : null}
              {messages.isLoadingError ? (
                <div role="alert" className="text-center text-sm text-red-700">
                  <p>No se pudo cargar el historial de esta conversación.</p>
                  <button type="button" onClick={() => void messages.refetch()} className="mt-1 font-semibold underline">Reintentar</button>
                </div>
              ) : null}
              {messages.isFetchNextPageError ? (
                <div role="alert" className="text-center text-sm text-red-700">
                  <p>No se pudieron cargar los mensajes anteriores.</p>
                  <button type="button" onClick={loadOlderMessages} className="mt-1 font-semibold underline">Reintentar</button>
                </div>
              ) : null}
              {!messages.isLoading && !messages.isLoadingError && orderedMessages.length === 0 ? (
                <p className="text-center text-sm text-slate-500">Todavía no hay mensajes en esta conversación.</p>
              ) : null}
              {orderedMessages.map((message) => (
                <div key={message.id} className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${message.direction === "outbound" ? "ml-auto bg-brand-50" : "bg-slate-100"}`}>
                  <p>{message.text || `[${message.message_type}]`}</p>
                  <p className="mt-1 text-[10px] text-slate-500">{message.status}</p>
                </div>
              ))}
              {messages.data && !messages.hasNextPage && orderedMessages.length > 0 ? (
                <p className="py-2 text-center text-xs text-slate-500">Inicio de la conversación</p>
              ) : null}
            </div>
            <div className="space-y-2 border-t border-slate-100 pt-3">
              <div className="flex gap-2">
                <input aria-label="Responder al huésped" className="min-w-0 flex-1 rounded border px-3 py-2 text-sm" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Responder al huésped" />
                {/* Clear the box only once the send lands: a failed request used
                    to wipe what the operator had typed. */}
                <button type="button" disabled={!draft.trim() || send.isPending} onClick={() => send.mutate({ id: selected.id, text: draft.trim() }, { onSuccess: () => setDraft("") })} className="rounded bg-brand-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">Enviar</button>
              </div>
              <div className="flex gap-2">
                <input aria-label="Nota interna" className="min-w-0 flex-1 rounded border px-3 py-2 text-sm" value={noteDraft} onChange={(event) => setNoteDraft(event.target.value)} placeholder="Nota interna" />
                <button type="button" disabled={!noteDraft.trim() || note.isPending} onClick={() => note.mutate({ id: selected.id, body: noteDraft.trim() }, { onSuccess: () => setNoteDraft("") })} className="rounded border px-3 py-2 text-sm font-semibold">Guardar nota</button>
              </div>
              <div className="flex gap-2">
                <input aria-label="ID del responsable" inputMode="numeric" className="w-40 rounded border px-3 py-2 text-sm" value={assignee} onChange={(event) => setAssignee(event.target.value)} placeholder="ID responsable" />
                {/* A non-numeric id used to reach the API as NaN, which serializes
                    to null and silently unassigned the conversation instead. */}
                <button type="button" disabled={!assigneeIsValid || assign.isPending} onClick={() => assign.mutate({ id: selected.id, userId: assigneeUserId }, { onSuccess: () => setAssignee("") })} className="rounded border px-3 py-2 text-sm font-semibold disabled:opacity-50">{assignee.trim() ? "Asignar" : "Quitar asignación"}</button>
              </div>
              {sendError ? <p role="alert" className="text-xs text-red-600">{sendError}</p> : null}
            </div>
          </>}
        </section>
      </div>
    </div>
  );
}
