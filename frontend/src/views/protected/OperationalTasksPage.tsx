import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { hasValidSession } from "../../api/client";
import {
  acknowledgeShiftHandoff,
  createOperationalTask,
  createShiftHandoff,
  listOperationalTaskHistory,
  listOperationalTasks,
  listShiftHandoffs,
  resolveOperationalTask,
  updateOperationalTask,
  type OperationalTaskCreate,
  type OperationalTaskPriority,
  type OperationalTaskStatus,
  type OperationalTaskType
} from "../../api/operationalTasks";
import { useGuardedMutation } from "../../hooks/useGuardedMutation";
import { useEffectivePermissions } from "../../hooks/usePermissions";
import { roomBlockReasonLabel, useRoomBlocks } from "../../hooks/useRoomBlocks";
import { useLatestCashCloseReport } from "../../hooks/useCashRegister";
import { useRooms } from "../../hooks/useRooms";
import { useSession } from "../../state/session";

const statusLabels: Record<OperationalTaskStatus, string> = {
  pending: "Pendiente",
  in_progress: "En curso",
  pending_review: "Pendiente de revisión",
  resolved: "Resuelta"
};

const priorityLabels: Record<OperationalTaskPriority, string> = {
  low: "Baja",
  medium: "Media",
  high: "Alta",
  critical: "Crítica"
};

const typeLabels: Record<OperationalTaskType, string> = {
  general: "General",
  reception: "Recepción",
  housekeeping: "Limpieza",
  maintenance: "Mantenimiento"
};

type TaskForm = {
  title: string;
  task_type: OperationalTaskType;
  priority: OperationalTaskPriority;
  description: string;
  room_id: string;
  room_block_id: string;
  due_at: string;
};

const emptyForm = (): TaskForm => ({
  title: "",
  task_type: "general",
  priority: "medium",
  description: "",
  room_id: "",
  room_block_id: "",
  due_at: ""
});

const formatDate = (value?: string | null) => {
  if (!value) return "Sin vencimiento";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Fecha no disponible" : date.toLocaleString("es-AR");
};

export function OperationalTasksPage() {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const { hasPermission, hasAnyPermission } = useEffectivePermissions();
  const enabled = hasValidSession(session);
  const canManage = hasPermission("operations:tasks:manage");
  const canHandoff = hasPermission("operations:handoff:manage");
  const { roomsQuery } = useRooms({ includeCategories: false });
  const { blocksQuery } = useRoomBlocks({ enabled: canManage });
  const latestCloseReportQuery = useLatestCashCloseReport({ enabled: canHandoff });
  const [form, setForm] = useState<TaskForm>(() => emptyForm());
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [historyTaskId, setHistoryTaskId] = useState<number | null>(null);
  const [includeLatestClose, setIncludeLatestClose] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const tasksQuery = useQuery({
    queryKey: ["operational-tasks", session.hotelId],
    queryFn: () => listOperationalTasks(session),
    enabled,
    staleTime: 15 * 1000
  });
  const handoffsQuery = useQuery({
    queryKey: ["operational-handoffs", session.hotelId],
    queryFn: () => listShiftHandoffs(session),
    enabled: enabled && canHandoff,
    staleTime: 15 * 1000
  });
  const historyQuery = useQuery({
    queryKey: ["operational-task-history", session.hotelId, historyTaskId],
    queryFn: () => listOperationalTaskHistory(historyTaskId as number, session),
    enabled: enabled && historyTaskId !== null,
    staleTime: 15 * 1000
  });

  const rooms = useMemo(() => roomsQuery.data ?? [], [roomsQuery.data]);
  const activeBlocks = useMemo(() => blocksQuery.data ?? [], [blocksQuery.data]);
  const taskTypeOptions = useMemo(() => {
    if (canManage || !session.baseRole) return Object.entries(typeLabels) as [OperationalTaskType, string][];
    if (session.baseRole === "housekeeping") {
      return [["housekeeping", typeLabels.housekeeping], ["maintenance", typeLabels.maintenance]] as [OperationalTaskType, string][];
    }
    if (session.baseRole === "receptionist") {
      return [["general", typeLabels.general], ["reception", typeLabels.reception]] as [OperationalTaskType, string][];
    }
    return Object.entries(typeLabels) as [OperationalTaskType, string][];
  }, [canManage, session.baseRole]);
  const selectedRoomId = Number(form.room_id) || null;
  const visibleBlocks = activeBlocks.filter((block) => !selectedRoomId || block.room_id === selectedRoomId);

  const taskPayload = (): OperationalTaskCreate => ({
    task_type: form.task_type,
    priority: form.priority,
    title: form.title,
    description: form.description.trim() || null,
    room_id: selectedRoomId,
    room_block_id: form.room_block_id ? Number(form.room_block_id) : null,
    due_at: form.due_at ? new Date(form.due_at).toISOString() : null
  });

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["operational-tasks", session.hotelId] });
    if (canHandoff) await queryClient.invalidateQueries({ queryKey: ["operational-handoffs", session.hotelId] });
  };

  const createMutation = useGuardedMutation({
    mutationFn: () => createOperationalTask(taskPayload(), session),
    onSuccess: async () => {
      await refresh();
      setForm(emptyForm());
      setMessage("Tarea agregada al turno.");
    }
  });
  const statusMutation = useGuardedMutation({
    mutationFn: ({ id, version, status }: { id: number; version: number; status: OperationalTaskStatus }) =>
      updateOperationalTask(id, { client_version: version, status }, session),
    onSuccess: refresh
  });
  const resolveMutation = useGuardedMutation({
    mutationFn: ({ id, version }: { id: number; version: number }) => resolveOperationalTask(id, version, undefined, session),
    onSuccess: refresh
  });
  const handoffMutation = useGuardedMutation({
    mutationFn: () => createShiftHandoff({
      task_ids: selectedIds,
      cash_close_report_id: includeLatestClose ? latestCloseReportQuery.data?.id ?? null : null
    }, session),
    onSuccess: async () => {
      await refresh();
      setSelectedIds([]);
      setIncludeLatestClose(false);
      setMessage("Pase de turno preparado.");
    }
  });
  const acknowledgeMutation = useGuardedMutation({
    mutationFn: ({ id, version }: { id: number; version: number }) => acknowledgeShiftHandoff(id, version, session),
    onSuccess: refresh
  });

  const tasks = useMemo(() => tasksQuery.data ?? [], [tasksQuery.data]);
  const handoffs = useMemo(() => handoffsQuery.data ?? [], [handoffsQuery.data]);
  const activeTasks = tasks.filter((task) => task.status !== "resolved");

  const run = async (action: () => Promise<unknown>, success?: string) => {
    setMessage(null);
    try {
      await action();
      if (success) setMessage(success);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo completar la acción.");
    }
  };

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void run(() => createMutation.mutateAsync(), "Tarea agregada al turno.");
  };

  const handleTaskTypeChange = (taskType: OperationalTaskType) => {
    setForm((current) => ({
      ...current,
      task_type: taskType,
      room_block_id: taskType === "maintenance" ? current.room_block_id : ""
    }));
  };

  const toggleSelected = (id: number) => {
    setSelectedIds((current) => (current.includes(id) ? current.filter((value) => value !== id) : [...current, id]));
  };

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
        <h1 className="text-2xl font-semibold text-slate-900">Tareas y pase de turno</h1>
        <p className="text-sm text-slate-600">Un mismo pendiente acompaña al hotel hasta que alguien lo revisa y resuelve.</p>
      </header>

      {message && <p role="status" className="rounded-lg bg-slate-100 px-4 py-3 text-sm text-slate-700">{message}</p>}
      {tasksQuery.isError && (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          No se pudieron cargar los pendientes.
          <button type="button" onClick={() => void tasksQuery.refetch()} className="ml-2 font-semibold underline">Reintentar</button>
        </div>
      )}

      {hasAnyPermission(["operations:tasks:report", "operations:tasks:manage"]) && (
        <form onSubmit={submit} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Agregar pendiente</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_180px_180px_220px] lg:items-end">
            <label className="text-sm text-slate-700">
              Título
              <input
                required
                value={form.title}
                onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                maxLength={200}
              />
            </label>
            <label className="text-sm text-slate-700">
              Área
              <select value={form.task_type} onChange={(event) => handleTaskTypeChange(event.target.value as OperationalTaskType)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2">
                {taskTypeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label className="text-sm text-slate-700">
              Prioridad
              <select value={form.priority} onChange={(event) => setForm((current) => ({ ...current, priority: event.target.value as OperationalTaskPriority }))} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2">
                {Object.entries(priorityLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label className="text-sm text-slate-700">
              Habitación (opcional)
              <select
                value={form.room_id}
                onChange={(event) => setForm((current) => ({
                  ...current,
                  room_id: event.target.value,
                  room_block_id: current.room_block_id && activeBlocks.some((block) => String(block.id) === current.room_block_id && String(block.room_id) === event.target.value) ? current.room_block_id : ""
                }))}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
              >
                <option value="">Sin habitación vinculada</option>
                {rooms.map((room) => <option key={room.id} value={room.id}>Habitación {room.room_number}</option>)}
              </select>
            </label>
            {canManage && form.task_type === "maintenance" && (
              <label className="text-sm text-slate-700">
                Bloqueo de mantenimiento (opcional)
                <select
                  value={form.room_block_id}
                  onChange={(event) => {
                    const blockId = event.target.value;
                    const block = activeBlocks.find((item) => String(item.id) === blockId);
                    setForm((current) => ({ ...current, room_block_id: blockId, room_id: block ? String(block.room_id) : current.room_id }));
                  }}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                >
                  <option value="">Sin bloqueo vinculado</option>
                  {visibleBlocks.map((block) => {
                    const room = rooms.find((item) => item.id === block.room_id);
                    return <option key={block.id} value={block.id}>Habitación {room?.room_number ?? "sin número"} · {roomBlockReasonLabel[block.reason_code]}</option>;
                  })}
                </select>
              </label>
            )}
            <label className="text-sm text-slate-700">
              Vencimiento (opcional)
              <input type="datetime-local" value={form.due_at} onChange={(event) => setForm((current) => ({ ...current, due_at: event.target.value }))} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
            </label>
            <label className="text-sm text-slate-700 md:col-span-2 lg:col-span-3">
              Comentario para el siguiente turno (opcional)
              <textarea value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} className="mt-1 min-h-20 w-full rounded-lg border border-slate-300 px-3 py-2" maxLength={5000} />
            </label>
            <button type="submit" disabled={createMutation.isPending} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
              {createMutation.isPending ? "Guardando…" : "Agregar"}
            </button>
          </div>
        </form>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="tasks-title">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 id="tasks-title" className="text-lg font-semibold text-slate-900">Pendientes compartidos</h2>
            <p className="text-sm text-slate-600">{activeTasks.length} abiertos · {tasks.length} registrados</p>
          </div>
          {canHandoff && (
            <div className="flex flex-wrap items-center justify-end gap-2">
              <label className="flex items-center gap-2 text-xs text-slate-600">
                <input
                  type="checkbox"
                  checked={includeLatestClose}
                  disabled={!latestCloseReportQuery.data || handoffMutation.isPending}
                  onChange={(event) => setIncludeLatestClose(event.target.checked)}
                  className="h-4 w-4"
                />
                Vincular último arqueo
              </label>
              <button
                type="button"
                disabled={!selectedIds.length || handoffMutation.isPending}
                onClick={() => void run(() => handoffMutation.mutateAsync(), "Pase de turno preparado.")}
                className="rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-sm font-semibold text-brand-800 disabled:opacity-50"
              >
                Preparar pase ({selectedIds.length})
              </button>
            </div>
          )}
        </div>
        {tasksQuery.isLoading ? <p role="status" className="mt-4 text-sm text-slate-500">Cargando pendientes…</p> : tasks.length === 0 ? (
          <p className="mt-4 rounded-lg bg-slate-50 p-4 text-sm text-slate-600">No hay pendientes registrados.</p>
        ) : (
          <div className="mt-4 space-y-3">
            {tasks.map((task) => (
              <article key={task.id} className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-start gap-3">
                  {canHandoff && task.status !== "resolved" && (
                    <input aria-label={`Incluir ${task.title} en el pase`} type="checkbox" checked={selectedIds.includes(task.id)} onChange={() => toggleSelected(task.id)} className="mt-1 h-4 w-4" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold text-slate-900">{task.title}</h3>
                      <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-700">{statusLabels[task.status]}</span>
                      <span className="rounded-full bg-amber-50 px-2 py-1 text-xs text-amber-800">{priorityLabels[task.priority]}</span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">{typeLabels[task.task_type]} · {task.room_number ? `Habitación ${task.room_number}` : "Sin habitación"} · {formatDate(task.due_at)}</p>
                  </div>
                  <div className="flex shrink-0 flex-wrap justify-end gap-2">
                    {task.status === "pending" && (
                      <button type="button" onClick={() => void run(() => statusMutation.mutateAsync({ id: task.id, version: task.version, status: "in_progress" }), "Tarea tomada por el turno.")} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700">Tomar</button>
                    )}
                    {task.status === "in_progress" && (
                      <button type="button" onClick={() => void run(() => statusMutation.mutateAsync({ id: task.id, version: task.version, status: "pending_review" }), "Tarea enviada a revisión.")} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700">Enviar a revisión</button>
                    )}
                    {canManage && task.status !== "resolved" && (
                      <button type="button" onClick={() => void run(() => resolveMutation.mutateAsync({ id: task.id, version: task.version }), "Tarea resuelta.")} className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white">Resolver</button>
                    )}
                    <button
                      type="button"
                      onClick={() => setHistoryTaskId((current) => current === task.id ? null : task.id)}
                      className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700"
                    >
                      {historyTaskId === task.id ? "Ocultar historial" : "Ver historial"}
                    </button>
                  </div>
                </div>
                {historyTaskId === task.id && (
                  <div className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
                    {historyQuery.isLoading ? <p role="status">Cargando historial…</p> : historyQuery.isError ? (
                      <p role="alert" className="text-rose-700">No se pudo cargar el historial. <button type="button" onClick={() => void historyQuery.refetch()} className="font-semibold underline">Reintentar</button></p>
                    ) : historyQuery.data?.length ? (
                      <ol className="space-y-2">
                        {historyQuery.data.map((event) => (
                          <li key={event.id}>
                            <span className="font-semibold">{statusLabels[event.to_status as OperationalTaskStatus] ?? "Actualización"}</span> · {formatDate(event.created_at)}{event.comment ? ` · ${event.comment}` : ""}
                          </li>
                        ))}
                      </ol>
                    ) : <p>No hay movimientos registrados.</p>}
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </section>

      {canHandoff && (
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="handoffs-title">
          <h2 id="handoffs-title" className="text-lg font-semibold text-slate-900">Pases recientes</h2>
          {handoffsQuery.isError ? <p role="alert" className="mt-3 text-sm text-rose-700">No se pudieron cargar los pases. <button type="button" className="font-semibold underline" onClick={() => void handoffsQuery.refetch()}>Reintentar</button></p> : handoffs.length === 0 ? <p className="mt-3 text-sm text-slate-600">Todavía no hay pases de turno.</p> : (
            <ul className="mt-3 space-y-2">
              {handoffs.map((handoff) => (
                <li key={handoff.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-3 text-sm">
                  <span><strong>{handoff.task_ids.length} pendientes</strong> · {formatDate(handoff.delivered_at)} · {handoff.status === "acknowledged" ? "Reconocido" : "Pendiente de reconocimiento"}</span>
                  {handoff.status === "pending_acknowledgement" && <button type="button" onClick={() => void run(() => acknowledgeMutation.mutateAsync({ id: handoff.id, version: handoff.version }), "Pase reconocido.")} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700">Reconocer</button>}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
