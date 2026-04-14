import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import { ApiError } from "../../api/client";
import { useGemmaChat } from "../../hooks/useGemmaChat";
import { useSession } from "../../state/session";

const suggestedPrompts = [
  "Quiero reducir noches sueltas y proteger estadias largas.",
  "Explicame por que tengo menos reservas por Booking esta semana.",
  "Que configuracion me conviene para dejar libres ciertas habitaciones.",
  "Analiza si una restriccion me esta frenando ventas.",
];

const roleLabel: Record<string, string> = {
  owner: "Dueno",
  co_owner: "Co-dueno",
  manager: "Manager",
  housekeeping: "Housekeeping",
  receptionist: "Recepcionista",
};

const modeLabel: Record<string, string> = {
  query: "Consulta",
  analysis: "Analisis",
  proposal: "Propuesta",
  execution: "Ejecucion",
  learning: "Aprendizaje",
  clarify: "Aclaracion",
  unsupported: "No soportado",
};

const runtimeLabel: Record<string, string> = {
  ready: "Listo",
  disabled: "Deshabilitado",
  unconfigured: "Sin configurar",
  timeout: "Timeout",
  http_error: "Error HTTP",
  invalid_payload: "Payload invalido",
  unreachable: "Inalcanzable",
  unsupported_provider: "Provider no soportado",
  fallback_only: "Solo fallback",
  ok: "OK",
  unexpected_error: "Error inesperado",
};

const bubbleStyles: Record<string, string> = {
  user: "ml-auto border-slate-200 bg-slate-900 text-white",
  assistant: "border-emerald-100 bg-emerald-50 text-emerald-950",
  system: "border-amber-100 bg-amber-50 text-amber-950",
};

const displayMessageText = (message: {
  raw_text?: string | null;
  redacted_text?: string | null;
  text?: string | null;
  content?: string | null;
}) => message.redacted_text || message.raw_text || message.text || message.content || "";

const formatTimestamp = (value?: string | null) => {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString();
};

export function SettingsAssistantPage() {
  const { session } = useSession();
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const {
    activeSessionId,
    setActiveSessionId,
    clearConversation,
    activeEnvelope,
    historyQuery,
    insightsQuery,
    runtimeStatusQuery,
    sessionQuery,
    sendMessage,
    sendMessageMutation,
    approveActionMutation,
    rejectActionMutation,
    reviewDraftMutation,
    applyDraftMutation,
    archiveSessionMutation,
    isReady,
  } = useGemmaChat();

  const chatEnvelope = activeEnvelope;
  const messages = chatEnvelope?.messages ?? [];
  const history = historyQuery.data ?? [];
  const insights = insightsQuery.data ?? [];
  const runtime = runtimeStatusQuery.data ?? null;
  const isBusy = sessionQuery.isFetching || sendMessageMutation.isPending;
  const lastMode = chatEnvelope?.mode || (messages.length ? "query" : null);
  const lastIntent = chatEnvelope?.intent_type || messages[messages.length - 1]?.intent_type || null;
  const missingInformation = chatEnvelope?.missing_information ?? [];
  const warnings = chatEnvelope?.warnings ?? [];
  const proposalActions = chatEnvelope?.actions ?? [];
  const proposalPreview = chatEnvelope?.preview ?? null;
  const runtimeStatus = typeof chatEnvelope?.metadata?.runtime_status === "string" ? String(chatEnvelope.metadata.runtime_status) : runtime?.status || null;
  const fallbackUsed = chatEnvelope?.metadata?.fallback_used === true;

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length]);

  const statusTone = useMemo(() => {
    if (sessionQuery.isError || sendMessageMutation.isError) return "border-rose-200 bg-rose-50 text-rose-800";
    if (chatEnvelope?.requires_confirmation) return "border-amber-200 bg-amber-50 text-amber-800";
    if (chatEnvelope) return "border-emerald-200 bg-emerald-50 text-emerald-800";
    return "border-slate-200 bg-slate-50 text-slate-700";
  }, [chatEnvelope, sendMessageMutation.isError, sessionQuery.isError]);

  const error =
    sessionQuery.error ||
    historyQuery.error ||
    runtimeStatusQuery.error ||
    sendMessageMutation.error ||
    approveActionMutation.error ||
    rejectActionMutation.error ||
    reviewDraftMutation.error ||
    applyDraftMutation.error ||
    archiveSessionMutation.error;
  const errorMessage = error instanceof ApiError ? error.message : error instanceof Error ? error.message : null;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = draft.trim();
    if (!value) return;
    setDraft("");
    try {
      await sendMessage(value);
    } catch {
      // Managed by react-query state.
    }
  };

  const handleReset = () => {
    clearConversation();
    setDraft("");
  };

  const handleApproveAction = async (actionRunId?: number | null) => {
    if (!actionRunId || !activeSessionId) return;
    try {
      await approveActionMutation.mutateAsync({ actionRunId, payload: { session_id: activeSessionId } });
    } catch {
      // Managed by react-query state.
    }
  };

  const handleRejectAction = async (actionRunId?: number | null) => {
    if (!actionRunId || !activeSessionId) return;
    try {
      await rejectActionMutation.mutateAsync({ actionRunId, payload: { session_id: activeSessionId } });
    } catch {
      // Managed by react-query state.
    }
  };

  const handleReviewDraft = async (actionRunId?: number | null) => {
    if (!actionRunId || !activeSessionId) return;
    try {
      await reviewDraftMutation.mutateAsync({ actionRunId, payload: { session_id: activeSessionId } });
    } catch {
      // Managed by react-query state.
    }
  };

  const handleApplyDraft = async (actionRunId?: number | null) => {
    if (!actionRunId || !activeSessionId) return;
    try {
      await applyDraftMutation.mutateAsync({
        actionRunId,
        payload: { session_id: activeSessionId, publish: false },
      });
    } catch {
      // Managed by react-query state.
    }
  };

  const handleArchiveSession = async (sessionId?: number | null) => {
    if (!sessionId) return;
    try {
      await archiveSessionMutation.mutateAsync(sessionId);
    } catch {
      // Managed by react-query state.
    }
  };

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-64 bg-gradient-to-b from-amber-50 via-white to-transparent" />
      <div className="pointer-events-none absolute right-0 top-0 h-48 w-48 rounded-full bg-emerald-100/60 blur-3xl" />

      <div className="relative space-y-6">
        <header className="space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <span>Configuracion</span>
            <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-700">Gemma local</span>
            <span className="rounded-full bg-emerald-100 px-2 py-1 text-emerald-700">Hotel ID {session.hotelId ?? "-"}</span>
            {session.role && (
              <span className="rounded-full bg-amber-100 px-2 py-1 text-amber-700">
                {roleLabel[session.role] || session.role}
              </span>
            )}
          </div>
          <div className="max-w-3xl">
            <h1 className="text-3xl font-semibold tracking-tight text-slate-950">Asistente Gemma</h1>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Consulta, pide cambios y revisa contexto operativo sin salir del PMS. El historial queda separado por hotel y usuario.
            </p>
          </div>
        </header>

        <div className={`rounded-2xl border px-4 py-3 text-sm shadow-sm ${statusTone}`}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-semibold">Estado de la sesion</p>
              <p className="text-xs opacity-80">
                {chatEnvelope
                  ? `Sesion ${chatEnvelope.session?.id ?? activeSessionId ?? "activa"} · ${modeLabel[lastMode || "query"] || lastMode || "Consulta"}`
                  : "Sin sesion activa. Envia el primer mensaje para crear una conversacion."}
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-xs font-semibold">
              {lastIntent && <span className="rounded-full bg-white/70 px-2 py-1 text-slate-700">{lastIntent}</span>}
              {runtimeStatus && (
                <span className="rounded-full bg-white/70 px-2 py-1 text-slate-700">
                  Runtime: {runtimeLabel[runtimeStatus] || runtimeStatus}
                </span>
              )}
              {fallbackUsed && <span className="rounded-full bg-white/70 px-2 py-1 text-amber-800">Fallback</span>}
              {chatEnvelope?.requires_confirmation && (
                <span className="rounded-full bg-white/70 px-2 py-1 text-amber-800">Requiere confirmacion</span>
              )}
            </div>
          </div>
          {missingInformation.length > 0 && <p className="mt-2 text-xs">Faltan datos: {missingInformation.join(", ")}.</p>}
          {warnings.length > 0 && <p className="mt-2 text-xs">Advertencias: {warnings.join(", ")}.</p>}
        </div>

        {errorMessage && <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{errorMessage}</div>}

        {proposalPreview && (
          <section className="rounded-2xl border border-amber-200 bg-amber-50/70 p-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Preview controlado</p>
                <h2 className="mt-1 text-lg font-semibold text-slate-950">{proposalPreview.title || "Propuesta preparada"}</h2>
                <p className="mt-1 text-sm text-slate-700">{proposalPreview.impact_summary || "Gemma preparo una propuesta sin ejecutar cambios."}</p>
              </div>
              {chatEnvelope?.requires_confirmation && (
                <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-amber-800">Requiere confirmacion</span>
              )}
            </div>

            {proposalPreview.rationale && proposalPreview.rationale.length > 0 && (
              <div className="mt-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Razonamiento</p>
                <ul className="mt-2 space-y-1 text-sm text-slate-700">
                  {proposalPreview.rationale.map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              </div>
            )}

            {(proposalPreview.changed_weights?.length || proposalPreview.changed_constraints?.length) ? (
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div className="rounded-xl border border-white/70 bg-white/80 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Pesos</p>
                  {proposalPreview.changed_weights && proposalPreview.changed_weights.length > 0 ? (
                    <div className="mt-2 space-y-2 text-sm text-slate-700">
                      {proposalPreview.changed_weights.map((item) => (
                        <div key={item.key} className="flex items-center justify-between gap-4 rounded-lg bg-slate-50 px-3 py-2">
                          <span>{item.key}</span>
                          <span className="font-semibold text-slate-900">
                            {item.from} {"->"} {item.to}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-slate-500">Sin cambios de pesos.</p>
                  )}
                </div>

                <div className="rounded-xl border border-white/70 bg-white/80 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Restricciones</p>
                  {proposalPreview.changed_constraints && proposalPreview.changed_constraints.length > 0 ? (
                    <div className="mt-2 space-y-2 text-sm text-slate-700">
                      {proposalPreview.changed_constraints.map((item) => (
                        <div key={item.key} className="flex items-center justify-between gap-4 rounded-lg bg-slate-50 px-3 py-2">
                          <span>{item.key}</span>
                          <span className="font-semibold text-slate-900">
                            {String(item.from)} {"->"} {String(item.to)}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-slate-500">Sin cambios de restricciones.</p>
                  )}
                </div>
              </div>
            ) : null}

            {proposalActions.length > 0 && (
              <div className="mt-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Acciones sugeridas</p>
                <div className="mt-2 space-y-2">
                  {proposalActions.map((action) => (
                    <div
                      key={String(action.action_run_id || `${action.action_type}-${action.label || "action"}`)}
                      className="rounded-xl border border-white/70 bg-white/80 px-4 py-3 text-sm"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold text-slate-900">{action.label || action.action_type}</span>
                            <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-600">
                              {action.action_type}
                            </span>
                            {action.status && (
                              <span className="rounded-full bg-emerald-100 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-emerald-700">
                                {action.status}
                              </span>
                            )}
                          </div>
                          {action.result?.created_suggestion_id && (
                            <p className="text-xs text-emerald-800">Borrador creado: sugerencia #{String(action.result.created_suggestion_id)}</p>
                          )}
                          {action.result?.suggestion_status && (
                            <p className="text-xs text-slate-600">Estado del borrador: {String(action.result.suggestion_status)}</p>
                          )}
                          {action.result?.created_version_id && (
                            <p className="text-xs text-emerald-800">
                              Version creada: #{String(action.result.created_version_id)}
                              {action.result.version_number ? ` (v${String(action.result.version_number)})` : ""}
                            </p>
                          )}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => handleApproveAction(action.action_run_id)}
                            disabled={
                              approveActionMutation.isPending ||
                              !action.action_run_id ||
                              !["pending_confirmation", "draft"].includes(String(action.status)) ||
                              action.action_type !== "allocation_policy.update_preview"
                            }
                            className="rounded-xl bg-slate-900 px-3 py-2 text-xs font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {approveActionMutation.isPending ? "Confirmando..." : "Confirmar borrador"}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleRejectAction(action.action_run_id)}
                            disabled={
                              rejectActionMutation.isPending ||
                              !action.action_run_id ||
                              !["pending_confirmation", "draft"].includes(String(action.status))
                            }
                            className="rounded-xl border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {rejectActionMutation.isPending ? "Rechazando..." : "Rechazar"}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleReviewDraft(action.action_run_id)}
                            disabled={
                              reviewDraftMutation.isPending ||
                              !action.action_run_id ||
                              !["executed", "reviewed"].includes(String(action.status))
                            }
                            className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800 transition hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {reviewDraftMutation.isPending ? "Revisando..." : "Marcar revisado"}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleApplyDraft(action.action_run_id)}
                            disabled={
                              applyDraftMutation.isPending ||
                              !action.action_run_id ||
                              !["executed", "reviewed"].includes(String(action.status))
                            }
                            className="rounded-xl bg-emerald-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {applyDraftMutation.isPending ? "Aplicando..." : "Aplicar version"}
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
          <aside className="space-y-4">
            <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Capacidades</h2>
              <ul className="mt-3 space-y-2 text-sm text-slate-700">
                <li>- Traducir lenguaje natural a configuraciones validas.</li>
                <li>- Responder preguntas del hotel con datos reales.</li>
                <li>- Capturar feedback para aprender de overrides.</li>
                <li>- Mantener sesion y contexto por hotel y usuario.</li>
              </ul>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Runtime local</h2>
                  <p className="mt-1 text-sm text-slate-700">
                    {runtime ? `${runtimeLabel[runtime.status] || runtime.status} · ${runtime.provider}` : "Cargando diagnostico..."}
                  </p>
                </div>
                {runtime?.reachable ? (
                  <span className="rounded-full bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-700">Reachable</span>
                ) : (
                  <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">No probe</span>
                )}
              </div>
              <dl className="mt-4 space-y-3 text-sm">
                <div className="flex items-center justify-between gap-4 border-b border-slate-100 pb-2">
                  <dt className="text-slate-500">Modelo</dt>
                  <dd className="font-semibold text-slate-900">{runtime?.model || "Sin modelo"}</dd>
                </div>
                <div className="flex items-center justify-between gap-4 border-b border-slate-100 pb-2">
                  <dt className="text-slate-500">Timeout</dt>
                  <dd className="font-semibold text-slate-900">{runtime?.timeout_seconds ?? "-"}s</dd>
                </div>
                <div className="flex items-center justify-between gap-4 border-b border-slate-100 pb-2">
                  <dt className="text-slate-500">Contexto</dt>
                  <dd className="font-semibold text-slate-900">{runtime?.max_conversation_messages ?? "-"} mensajes</dd>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <dt className="text-slate-500">Input maximo</dt>
                  <dd className="font-semibold text-slate-900">{runtime?.max_input_chars ?? "-"} chars</dd>
                </div>
              </dl>
              {runtime?.fallback_reason && <p className="mt-3 text-xs text-amber-700">{runtime.fallback_reason}</p>}
              {runtime?.endpoint_url && <p className="mt-2 break-all text-[11px] text-slate-500">{runtime.endpoint_url}</p>}
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Sesion</h2>
                  <p className="mt-1 text-sm text-slate-700">
                    {chatEnvelope?.session?.title || (activeSessionId ? `Conversacion #${activeSessionId}` : "Sin conversacion guardada")}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleReset}
                  className="rounded-full border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-700 hover:border-slate-300 hover:bg-slate-50"
                >
                  Nueva
                </button>
              </div>
              {activeSessionId && (
                <button
                  type="button"
                  onClick={() => handleArchiveSession(activeSessionId)}
                  disabled={archiveSessionMutation.isPending}
                  className="mt-3 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800 hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {archiveSessionMutation.isPending ? "Archivando..." : "Archivar sesion"}
                </button>
              )}
              <dl className="mt-4 space-y-3 text-sm">
                <div className="flex items-center justify-between gap-4 border-b border-slate-100 pb-2">
                  <dt className="text-slate-500">Modo</dt>
                  <dd className="font-semibold text-slate-900">{modeLabel[lastMode || "query"] || "Consulta"}</dd>
                </div>
                <div className="flex items-center justify-between gap-4 border-b border-slate-100 pb-2">
                  <dt className="text-slate-500">Sesion activa</dt>
                  <dd className="font-semibold text-slate-900">{activeSessionId ?? "Sin ID"}</dd>
                </div>
                <div className="flex items-center justify-between gap-4 border-b border-slate-100 pb-2">
                  <dt className="text-slate-500">Mensajes</dt>
                  <dd className="font-semibold text-slate-900">{messages.length}</dd>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <dt className="text-slate-500">Listo para enviar</dt>
                  <dd className={`font-semibold ${isReady ? "text-emerald-700" : "text-amber-700"}`}>{isReady ? "Si" : "No"}</dd>
                </div>
              </dl>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Sesiones recientes</h2>
                {historyQuery.isFetching && <span className="text-xs text-slate-500">Actualizando...</span>}
              </div>
              <div className="mt-3 space-y-2">
                {history.length > 0 ? (
                  history.map((item) => {
                    const isActive = item.id === activeSessionId;
                    return (
                      <div
                        key={item.id}
                        className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                          isActive ? "border-emerald-200 bg-emerald-50" : "border-slate-200 bg-slate-50 hover:bg-white"
                        }`}
                      >
                        <button type="button" onClick={() => setActiveSessionId(item.id)} className="w-full text-left">
                          <div className="flex items-center justify-between gap-3">
                            <span className="text-sm font-semibold text-slate-900">{item.title || `Sesion #${item.id}`}</span>
                            <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                              {modeLabel[item.mode || "query"] || item.mode || "Consulta"}
                            </span>
                          </div>
                          <p className="mt-1 line-clamp-2 text-xs text-slate-600">{item.last_message_preview || "Sin preview"}</p>
                          <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
                            <span>{item.message_count || 0} mensajes</span>
                            <span>{formatTimestamp(item.updated_at)}</span>
                          </div>
                        </button>
                        <div className="mt-2 flex justify-end">
                          <button
                            type="button"
                            onClick={() => handleArchiveSession(item.id)}
                            disabled={archiveSessionMutation.isPending}
                            className="rounded-full border border-slate-200 px-2 py-1 text-[11px] font-semibold text-slate-600 hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            Archivar
                          </button>
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <p className="text-sm text-slate-500">Todavia no hay sesiones guardadas.</p>
                )}
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Insights recientes</h2>
                {insightsQuery.isFetching && <span className="text-xs text-slate-500">Actualizando...</span>}
              </div>
              <div className="mt-3 space-y-2">
                {insights.length > 0 ? (
                  insights.map((insight) => (
                    <div key={insight.id} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                          {modeLabel[insight.insight_type] || insight.insight_type}
                        </span>
                        <span className="text-[11px] text-slate-500">{formatTimestamp(insight.created_at)}</span>
                      </div>
                      <p className="mt-2 text-sm text-slate-800">{insight.summary}</p>
                      {typeof insight.details?.intent_type === "string" && (
                        <p className="mt-2 text-[11px] text-slate-500">Intento: {String(insight.details.intent_type)}</p>
                      )}
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">Todavia no hay insights guardados.</p>
                )}
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Sugerencias</h2>
              <div className="mt-3 flex flex-wrap gap-2">
                {suggestedPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => setDraft(prompt)}
                    className="rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-left text-xs font-medium text-slate-700 hover:border-emerald-200 hover:bg-emerald-50"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </section>
          </aside>

          <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 px-5 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">Conversacion</h2>
                  <p className="text-sm text-slate-600">
                    El historial queda acotado al hotel activo. Las respuestas nuevas se guardan automaticamente.
                  </p>
                </div>
                {isBusy && <span className="text-xs font-semibold text-slate-500">Procesando...</span>}
              </div>
            </div>

            <div className="max-h-[58vh] space-y-4 overflow-y-auto px-5 py-5">
              {messages.length > 0 ? (
                messages.map((message) => (
                  <article
                    key={message.id}
                    className={`max-w-3xl rounded-2xl border px-4 py-3 text-sm shadow-sm ${bubbleStyles[message.role] || bubbleStyles.system}`}
                  >
                    <div className="mb-2 flex items-center justify-between gap-3 text-[11px] font-semibold uppercase tracking-wide opacity-80">
                      <span>{message.role === "assistant" ? "Gemma" : message.role === "system" ? "Sistema" : "Tu mensaje"}</span>
                      <span>{formatTimestamp(message.created_at)}</span>
                    </div>
                    <p className="whitespace-pre-wrap leading-6">{displayMessageText(message) || "(sin contenido)"}</p>
                    {message.intent_type && (
                      <p className="mt-2 text-[11px] font-semibold uppercase tracking-wide opacity-80">Intento: {message.intent_type}</p>
                    )}
                  </article>
                ))
              ) : (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-sm text-slate-600">
                  Todavia no hay mensajes en esta sesion. Escribe una consulta para comenzar.
                </div>
              )}
              <div ref={scrollRef} />
            </div>

            <form onSubmit={handleSubmit} className="border-t border-slate-200 p-5">
              <label className="block text-sm font-semibold text-slate-700">
                Mensaje
                <textarea
                  className="mt-2 min-h-28 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-900 outline-none transition focus:border-emerald-300 focus:bg-white"
                  placeholder="Ej: Quiero reducir noches sueltas y priorizar estadias largas."
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                />
              </label>

              <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-slate-500">
                  Gemma responde dentro de los limites del PMS. Si falta contexto, te va a pedir aclaracion.
                </p>
                <div className="flex items-center gap-2">
                  {(approveActionMutation.isError ||
                    rejectActionMutation.isError ||
                    reviewDraftMutation.isError ||
                    applyDraftMutation.isError) && (
                    <span className="text-xs text-rose-700">
                      {approveActionMutation.error instanceof ApiError
                        ? approveActionMutation.error.message
                        : rejectActionMutation.error instanceof ApiError
                          ? rejectActionMutation.error.message
                          : reviewDraftMutation.error instanceof ApiError
                            ? reviewDraftMutation.error.message
                            : applyDraftMutation.error instanceof ApiError
                              ? applyDraftMutation.error.message
                              : "No se pudo completar la accion de Gemma."}
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => setDraft("")}
                    className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    Limpiar
                  </button>
                  <button
                    type="submit"
                    disabled={sendMessageMutation.isPending || !draft.trim()}
                    className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {sendMessageMutation.isPending ? "Enviando..." : "Enviar"}
                  </button>
                </div>
              </div>
            </form>
          </section>
        </div>
      </div>
    </div>
  );
}

export default SettingsAssistantPage;
