import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { hasValidSession } from "../../api/client";
import LocalizedDateField from "../../components/LocalizedDateField";
import {
  acknowledgeShiftHandoff,
  createOperationalTask,
  createShiftHandoff,
  getOperationalTaskAttachmentContent,
  listOperationalTaskAttachments,
  listOperationalTaskHistory,
  listOperationalTasks,
  listShiftHandoffs,
  resolveOperationalTask,
  uploadOperationalTaskAttachment,
  updateOperationalTask,
  type OperationalTask,
  type OperationalTaskAttachment,
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
  general: "Operaciones",
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

const emptyForm = (taskType: OperationalTaskType = "general"): TaskForm => ({
  title: "",
  task_type: taskType,
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
  const canWork = hasAnyPermission(["operations:tasks:report", "operations:tasks:manage"]);
  const defaultTaskType: OperationalTaskType = session.baseRole === "housekeeping" ? "housekeeping" : "general";
  const canHandoff = hasPermission("operations:handoff:manage");
  const { roomsQuery } = useRooms({ includeCategories: false });
  const { blocksQuery } = useRoomBlocks({ enabled: canManage });
  const latestCloseReportQuery = useLatestCashCloseReport({ enabled: canHandoff });
  const [form, setForm] = useState<TaskForm>(() => emptyForm(defaultTaskType));
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [historyTaskId, setHistoryTaskId] = useState<number | null>(null);
  const [attachmentsTaskId, setAttachmentsTaskId] = useState<number | null>(null);
  const [taskComments, setTaskComments] = useState<Record<number, string>>({});
  const [includeLatestClose, setIncludeLatestClose] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [actionErrors, setActionErrors] = useState<Record<string, string>>({});

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
  const attachmentsQuery = useQuery({
    queryKey: ["operational-task-attachments", session.hotelId, attachmentsTaskId],
    queryFn: () => listOperationalTaskAttachments(attachmentsTaskId as number, session),
    enabled: enabled && attachmentsTaskId !== null,
    staleTime: 15 * 1000
  });

  const rooms = useMemo(() => roomsQuery.data ?? [], [roomsQuery.data]);
  const activeBlocks = useMemo(() => blocksQuery.data ?? [], [blocksQuery.data]);
  const taskTypeOptions = useMemo(() => {
    if (canManage || !session.baseRole) return Object.entries(typeLabels) as [OperationalTaskType, string][];
    if (session.baseRole === "housekeeping") {
      return [
        ["general", typeLabels.general],
        ["housekeeping", typeLabels.housekeeping],
        ["maintenance", typeLabels.maintenance]
      ] as [OperationalTaskType, string][];
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
  const updateTaskSnapshot = (updatedTask: OperationalTask) => {
    queryClient.setQueryData<OperationalTask[]>(["operational-tasks", session.hotelId], (current) =>
      current?.map((task) => task.id === updatedTask.id ? updatedTask : task)
    );
  };

  const createMutation = useGuardedMutation({
    mutationFn: () => createOperationalTask(taskPayload(), session),
    onSuccess: async () => {
      await refresh();
      setForm(emptyForm(defaultTaskType));
      setMessage("Tarea agregada al turno.");
    }
  });
  const statusMutation = useGuardedMutation({
    mutationFn: ({ id, version, status }: { id: number; version: number; status: OperationalTaskStatus }) =>
      updateOperationalTask(id, { client_version: version, status }, session),
    onSuccess: async (updatedTask) => {
      updateTaskSnapshot(updatedTask);
      await refresh();
    }
  });
  const commentMutation = useGuardedMutation({
    mutationFn: ({ id, version, comment }: { id: number; version: number; comment: string }) =>
      updateOperationalTask(id, { client_version: version, comment }, session),
    onSuccess: async (updatedTask, variables) => {
      updateTaskSnapshot(updatedTask);
      setTaskComments((current) => ({ ...current, [variables.id]: "" }));
      await refresh();
      setMessage("Comentario agregado al historial.");
    }
  });
  const resolveMutation = useGuardedMutation({
    mutationFn: ({ id, version }: { id: number; version: number }) => resolveOperationalTask(id, version, undefined, session),
    onSuccess: async (updatedTask) => {
      updateTaskSnapshot(updatedTask);
      await refresh();
    }
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
  const attachmentMutation = useGuardedMutation({
    mutationFn: ({ taskId, fileName, contentType, contentBase64 }: {
      taskId: number;
      fileName: string;
      contentType: OperationalTaskAttachment["content_type"];
      contentBase64: string;
    }) => uploadOperationalTaskAttachment(taskId, {
      file_name: fileName,
      content_type: contentType,
      content_base64: contentBase64
    }, session),
    onSuccess: async (_attachment, variables) => {
      await queryClient.invalidateQueries({ queryKey: ["operational-task-attachments", session.hotelId, variables.taskId] });
    }
  });

  const tasks = useMemo(() => tasksQuery.data ?? [], [tasksQuery.data]);
  const handoffs = useMemo(() => handoffsQuery.data ?? [], [handoffsQuery.data]);
  const activeTasks = tasks.filter((task) => task.status !== "resolved");

  const run = async (action: () => Promise<unknown>, success: string | undefined, errorKey: string) => {
    setMessage(null);
    setActionErrors((current) => {
      const next = { ...current };
      delete next[errorKey];
      return next;
    });
    try {
      await action();
      if (success) setMessage(success);
    } catch (error) {
      setActionErrors((current) => ({
        ...current,
        [errorKey]: error instanceof Error ? error.message : "No se pudo completar la acción."
      }));
    }
  };

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void run(() => createMutation.mutateAsync(), "Tarea agregada al turno.", "create");
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

  const canOperateTask = (task: OperationalTask) => {
    if (canManage) return true;
    if (!canWork) return false;
    if (session.baseRole === "housekeeping") return task.task_type === "housekeeping" || task.task_type === "maintenance";
    if (session.baseRole === "receptionist") return task.task_type === "general" || task.task_type === "reception";
    return true;
  };

  const handleTaskPhotoUpload = async (taskId: number, file: File | undefined) => {
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      setActionErrors((current) => ({ ...current, [`photo-${taskId}`]: "La foto debe pesar como máximo 5 MB." }));
      return;
    }
    if (!(file.type === "image/jpeg" || file.type === "image/png" || file.type === "image/webp")) {
      setActionErrors((current) => ({ ...current, [`photo-${taskId}`]: "Usá una foto JPG, PNG o WebP." }));
      return;
    }
    setActionErrors((current) => {
      const next = { ...current };
      delete next[`photo-${taskId}`];
      return next;
    });
    try {
      const contentBase64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onerror = () => reject(new Error("No se pudo leer la foto."));
        reader.onload = () => typeof reader.result === "string"
          ? resolve(reader.result)
          : reject(new Error("No se pudo leer la foto."));
        reader.readAsDataURL(file);
      });
      await attachmentMutation.mutateAsync({
        taskId,
        fileName: file.name,
        contentType: file.type,
        contentBase64
      });
      setAttachmentsTaskId(taskId);
      setMessage("Foto privada adjuntada a la tarea.");
    } catch (error) {
      setActionErrors((current) => ({
        ...current,
        [`photo-${taskId}`]: error instanceof Error ? error.message : "No se pudo adjuntar la foto."
      }));
    }
  };

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
        <h1 className="text-balance text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">Tareas y pase de turno</h1>
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
          {actionErrors.create && <TaskMutationError error={actionErrors.create} onClose={() => setActionErrors((current) => { const next = { ...current }; delete next.create; return next; })} />}
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
            <LocalizedDateField
              id="operational-task-due-at"
              label="Vencimiento (opcional)"
              value={form.due_at}
              onChange={(value) => setForm((current) => ({ ...current, due_at: value }))}
              mode="datetime-local"
              className="text-sm text-slate-700"
              labelClassName="text-sm text-slate-700"
              inputClassName="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 pr-10"
              placeholder="DD/MM/AAAA HH:MM"
              chooseDateLabel="Elegir fecha y hora"
              invalidMessage="Ingresá una fecha y hora válidas con formato DD/MM/AAAA HH:MM."
            />
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
                onClick={() => void run(() => handoffMutation.mutateAsync(), "Pase de turno preparado.", "handoff-create")}
                className="rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-sm font-semibold text-brand-800 disabled:opacity-50"
              >
                Preparar pase ({selectedIds.length})
              </button>
            </div>
          )}
        </div>
        {actionErrors["handoff-create"] && <TaskMutationError error={actionErrors["handoff-create"]} onClose={() => setActionErrors((current) => { const next = { ...current }; delete next["handoff-create"]; return next; })} />}
        {tasksQuery.isLoading ? <p role="status" className="mt-4 text-sm text-slate-500">Cargando pendientes…</p> : tasksQuery.isError ? null : tasks.length === 0 ? (
          <p className="mt-4 rounded-lg bg-slate-50 p-4 text-sm text-slate-600">No hay pendientes registrados.</p>
        ) : (
          <div className="mt-4 space-y-3">
            {tasks.map((task) => (
              <article key={task.id} className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-start gap-3">
                  {canHandoff && task.status !== "resolved" && canOperateTask(task) && (
                    <input aria-label={`Incluir ${task.title} en el pase`} type="checkbox" checked={selectedIds.includes(task.id)} onChange={() => toggleSelected(task.id)} className="mt-1 h-4 w-4" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold text-slate-900">{task.title}</h3>
                      <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-700">{statusLabels[task.status]}</span>
                      <span className="rounded-full bg-amber-50 px-2 py-1 text-xs text-amber-800">{priorityLabels[task.priority]}</span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">{typeLabels[task.task_type]} · {task.room_number ? `Habitación ${task.room_number}` : "Sin habitación"} · Vence: {formatDate(task.due_at)}</p>
                    <p className="mt-1 text-xs text-slate-500">Creada por {task.created_by_name || "usuario interno"} · {formatDate(task.created_at)}</p>
                    {task.description && <p className="mt-3 whitespace-pre-wrap text-sm text-slate-700">{task.description}</p>}
                    {session.baseRole === "housekeeping" && task.task_type === "general" && (
                      <p className="mt-2 text-xs font-medium text-slate-500">Aviso de Operaciones · solo lectura para Limpieza.</p>
                    )}
                  </div>
                  <div className="flex shrink-0 flex-wrap justify-end gap-2">
                    {canOperateTask(task) && task.status === "pending" && (
                      <button type="button" onClick={() => void run(() => statusMutation.mutateAsync({ id: task.id, version: task.version, status: "in_progress" }), "Tarea tomada por el turno.", `task-${task.id}`)} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700">Tomar</button>
                    )}
                    {canOperateTask(task) && task.status === "in_progress" && (
                      <button type="button" onClick={() => void run(() => statusMutation.mutateAsync({ id: task.id, version: task.version, status: "pending_review" }), "Tarea enviada a revisión.", `task-${task.id}`)} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700">Enviar a revisión</button>
                    )}
                    {(canManage || (session.baseRole === "housekeeping" && canOperateTask(task))) && task.status !== "resolved" && (
                      <button type="button" onClick={() => void run(() => resolveMutation.mutateAsync({ id: task.id, version: task.version }), "Tarea resuelta.", `task-${task.id}`)} className="rounded-lg bg-brand-600 px-3 py-2 text-xs font-semibold text-white">Resolver</button>
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
                {actionErrors[`task-${task.id}`] && <TaskMutationError error={actionErrors[`task-${task.id}`]} onClose={() => setActionErrors((current) => { const next = { ...current }; delete next[`task-${task.id}`]; return next; })} />}
                {canOperateTask(task) && task.status !== "resolved" && (
                  <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-end">
                    <label className="min-w-0 flex-1 text-xs font-medium text-slate-600">
                      Comentario de seguimiento
                      <textarea
                        value={taskComments[task.id] ?? ""}
                        onChange={(event) => setTaskComments((current) => ({ ...current, [task.id]: event.target.value }))}
                        maxLength={2000}
                        rows={2}
                        aria-label={`Comentario para ${task.title}`}
                        className="mt-1 min-h-11 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal"
                      />
                    </label>
                    <button
                      type="button"
                      disabled={!taskComments[task.id]?.trim() || commentMutation.isPending}
                      onClick={() => void run(() => commentMutation.mutateAsync({ id: task.id, version: task.version, comment: taskComments[task.id].trim() }), undefined, `task-${task.id}`)}
                      className="min-h-11 rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 disabled:opacity-50"
                    >
                      {commentMutation.isPending ? "Guardando…" : "Agregar comentario"}
                    </button>
                  </div>
                )}
                {!canManage && session.baseRole !== "housekeeping" && task.status === "pending_review" && (
                  <p className="mt-2 text-xs text-slate-500">La gerencia revisa y cierra este pendiente.</p>
                )}
                <div className="mt-3">
                  <button
                    type="button"
                    onClick={() => setAttachmentsTaskId((current) => current === task.id ? null : task.id)}
                    className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700"
                  >
                    {attachmentsTaskId === task.id ? "Ocultar fotos" : "Fotos y evidencia"}
                  </button>
                  {attachmentsTaskId === task.id && (
                    <div className="mt-3 rounded-lg bg-slate-50 p-3">
                      {attachmentsQuery.isLoading ? <p role="status" className="text-xs text-slate-600">Cargando fotos…</p> : null}
                      {attachmentsQuery.isError ? (
                        <p role="alert" className="text-xs text-rose-700">No se pudieron cargar las fotos. <button type="button" onClick={() => void attachmentsQuery.refetch()} className="font-semibold underline">Reintentar</button></p>
                      ) : null}
                      {!attachmentsQuery.isLoading && !attachmentsQuery.isError && (attachmentsQuery.data?.length ?? 0) === 0 && (
                        <p className="text-xs text-slate-600">Todavía no hay fotos adjuntas.</p>
                      )}
                      {attachmentsQuery.data?.map((attachment) => (
                        <TaskPhotoPreview key={attachment.id} taskId={task.id} attachment={attachment} />
                      ))}
                      {canOperateTask(task) && (
                        <label className="mt-3 block text-xs font-medium text-slate-700">
                          Adjuntar foto (JPG, PNG o WebP; hasta 5 MB)
                          <input
                            type="file"
                            accept="image/jpeg,image/png,image/webp"
                            aria-label={`Adjuntar foto a ${task.title}`}
                            disabled={attachmentMutation.isPending}
                            onChange={(event) => {
                              void handleTaskPhotoUpload(task.id, event.currentTarget.files?.[0]);
                              event.currentTarget.value = "";
                            }}
                            className="mt-1 block min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                          />
                        </label>
                      )}
                      {actionErrors[`photo-${task.id}`] && <TaskMutationError error={actionErrors[`photo-${task.id}`]} onClose={() => setActionErrors((current) => { const next = { ...current }; delete next[`photo-${task.id}`]; return next; })} />}
                    </div>
                  )}
                </div>
                {historyTaskId === task.id && (
                  <div className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
                    {historyQuery.isLoading ? <p role="status">Cargando historial…</p> : historyQuery.isError ? (
                      <p role="alert" className="text-rose-700">No se pudo cargar el historial. <button type="button" onClick={() => void historyQuery.refetch()} className="font-semibold underline">Reintentar</button></p>
                    ) : historyQuery.data?.length ? (
                      <ol className="space-y-2">
                        {historyQuery.data.map((event) => (
                          <li key={event.id}>
                            <span className="font-semibold">{statusLabels[event.to_status as OperationalTaskStatus] ?? "Actualización"}</span> · {event.actor_name || "usuario interno"} · {formatDate(event.created_at)}{event.comment ? ` · ${event.comment}` : ""}
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
          {handoffsQuery.isLoading ? <p role="status" className="mt-3 text-sm text-slate-600">Cargando pases…</p> : handoffsQuery.isError ? <p role="alert" className="mt-3 text-sm text-rose-700">No se pudieron cargar los pases. <button type="button" className="font-semibold underline" onClick={() => void handoffsQuery.refetch()}>Reintentar</button></p> : handoffs.length === 0 ? <p className="mt-3 text-sm text-slate-600">Todavía no hay pases de turno.</p> : (
            <ul className="mt-3 space-y-2">
              {handoffs.map((handoff) => (
                <li key={handoff.id} className="rounded-lg bg-slate-50 px-3 py-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <span><strong>{handoff.task_ids.length} pendientes</strong> · Preparó {handoff.delivered_by_name || "usuario interno"} · {formatDate(handoff.delivered_at)} · {handoff.status === "acknowledged" ? `Reconocido por ${handoff.received_by_name || "usuario interno"}` : "Pendiente de reconocimiento"}</span>
                    {handoff.status === "pending_acknowledgement" && <button type="button" onClick={() => void run(() => acknowledgeMutation.mutateAsync({ id: handoff.id, version: handoff.version }), "Pase reconocido.", `handoff-${handoff.id}`)} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700">Reconocer</button>}
                  </div>
                  {actionErrors[`handoff-${handoff.id}`] && <TaskMutationError error={actionErrors[`handoff-${handoff.id}`]} onClose={() => setActionErrors((current) => { const next = { ...current }; delete next[`handoff-${handoff.id}`]; return next; })} />}
                  {handoff.notes && <p className="mt-2 whitespace-pre-wrap text-xs text-slate-700">{handoff.notes}</p>}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}

function TaskMutationError({ error, onClose }: { error: string; onClose: () => void }) {
  return (
    <div role="alert" className="mt-3 flex items-start justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
      <p>{error}</p>
      <button type="button" aria-label="Cerrar error" onClick={onClose} className="shrink-0 font-semibold underline">Cerrar</button>
    </div>
  );
}

function TaskPhotoPreview({ taskId, attachment }: { taskId: number; attachment: OperationalTaskAttachment }) {
  const { session } = useSession();
  const [isOpen, setIsOpen] = useState(false);
  const contentQuery = useQuery({
    queryKey: ["operational-task-attachment-content", session.hotelId, taskId, attachment.id],
    queryFn: () => getOperationalTaskAttachmentContent(taskId, attachment.id, session),
    enabled: isOpen && hasValidSession(session),
    staleTime: 4 * 60 * 1000,
    retry: false
  });

  return (
    <div className="mt-2 flex flex-wrap items-start gap-3 rounded-lg border border-slate-200 bg-white p-2">
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-semibold text-slate-800">{attachment.file_name}</p>
        <p className="mt-0.5 text-[11px] text-slate-500">
          {attachment.created_by_name || "Usuario interno"} · {formatDate(attachment.created_at)}
        </p>
        {isOpen && contentQuery.isLoading ? <p role="status" className="mt-2 text-xs text-slate-600">Abriendo foto…</p> : null}
        {isOpen && contentQuery.isError ? (
          <p role="alert" className="mt-2 text-xs text-rose-700">
            No se pudo abrir la foto. <button type="button" onClick={() => void contentQuery.refetch()} className="font-semibold underline">Reintentar</button>
          </p>
        ) : null}
        {isOpen && contentQuery.data ? (
          <img
            src={`data:${contentQuery.data.content_type};base64,${contentQuery.data.content_base64}`}
            alt={`Foto adjunta: ${attachment.file_name}`}
            loading="lazy"
            referrerPolicy="no-referrer"
            className="mt-2 max-h-64 max-w-full rounded-lg object-contain"
          />
        ) : null}
      </div>
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-expanded={isOpen}
        className="min-h-10 shrink-0 rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700"
      >
        {isOpen ? "Ocultar" : "Ver foto"}
      </button>
    </div>
  );
}
