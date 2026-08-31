import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../api/client";
import {
  collaborationWebSocketUrl,
  createCollaborationTicket,
  patchCollaborativeResource,
  type CollaborationResourceType,
  type CollaborationWsMessage
} from "../api/collaboration";
import { refreshAfterMutation } from "../api/queryInvalidation";
import { useSession } from "../state/session";

export type CollaborationStatus = "idle" | "connecting" | "connected" | "reconnecting" | "degraded" | "saving" | "conflict";

export type CollaborationConflict = {
  field: string;
  localValue: unknown;
  remoteValue: unknown;
};

export type CollaborationPeer = {
  connectionId: string;
  userId: number;
  fields: string[];
};

type Options = {
  resourceType: CollaborationResourceType;
  resourceId?: number | null;
  initialValues?: Record<string, unknown> | null;
  enabled?: boolean;
};

const MAX_RECONNECT_DELAY_MS = 30_000;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const parseWsMessage = (value: unknown): CollaborationWsMessage | null => {
  if (!isRecord(value) || typeof value.type !== "string") return null;
  return value as unknown as CollaborationWsMessage;
};

const resourceDomains = (resourceType: CollaborationResourceType) => {
  if (resourceType === "reservation") return ["reservations", "rooms", "analytics"] as const;
  if (resourceType === "guest") return ["guests", "reservations", "analytics"] as const;
  if (resourceType === "room") return ["rooms", "reservations", "analytics"] as const;
  if (resourceType === "cash_session") return ["cash", "payments", "analytics"] as const;
  if (resourceType === "settings") return ["settings", "security", "analytics"] as const;
  return ["stock", "analytics"] as const;
};

export function useCollaborativeResource({
  resourceType,
  resourceId,
  initialValues,
  enabled = true
}: Options) {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const resourceKey = `${resourceType}:${resourceId ?? "none"}`;
  const socketRef = useRef<WebSocket | null>(null);
  const retryTimerRef = useRef<number | null>(null);
  const cancelledRef = useRef(false);
  const reconnectAttemptRef = useRef(0);
  const connectionIdRef = useRef<string | null>(null);
  const revisionRef = useRef<string | null>(null);
  const baseValuesRef = useRef<Record<string, unknown>>(initialValues ?? {});
  const draftValuesRef = useRef<Record<string, unknown>>(initialValues ?? {});
  const dirtyFieldsRef = useRef<Set<string>>(new Set());
  const focusedFieldsRef = useRef<Set<string>>(new Set());
  const initializedResourceRef = useRef<string | null>(null);
  const lastInitialValuesSignatureRef = useRef<string | null>(null);
  const savingRef = useRef(false);

  // Parents commonly create the initial-values object inline. Track its
  // content, not its object identity, so a normal rerender cannot overwrite a
  // remote draft that was just applied to a clean field.
  const initialValuesSignature = JSON.stringify(initialValues ?? {});

  const [baseValues, setBaseValues] = useState<Record<string, unknown>>(initialValues ?? {});
  const [draftValues, setDraftValues] = useState<Record<string, unknown>>(initialValues ?? {});
  const [dirtyFields, setDirtyFields] = useState<Set<string>>(new Set());
  const [conflicts, setConflicts] = useState<Record<string, CollaborationConflict>>({});
  const [peers, setPeers] = useState<Record<string, CollaborationPeer>>({});
  const [status, setStatus] = useState<CollaborationStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const send = useCallback((payload: Record<string, unknown>) => {
    const socket = socketRef.current;
    if (socket?.readyState !== WebSocket.OPEN) return false;
    socket.send(JSON.stringify(payload));
    return true;
  }, []);

  const sendPresence = useCallback(() => {
    send({ type: "presence", fields: Array.from(focusedFieldsRef.current).sort() });
  }, [send]);

  const resendDirtyDraft = useCallback(() => {
    const dirtyFields = Array.from(dirtyFieldsRef.current);
    if (dirtyFields.length === 0) return;
    send({
      type: "draft_patch",
      base_revision: revisionRef.current ?? "pending",
      changes: Object.fromEntries(dirtyFields.map((field) => [field, draftValuesRef.current[field]]))
    });
  }, [send]);

  useEffect(() => {
    if (initializedResourceRef.current === resourceKey) return;
    initializedResourceRef.current = resourceKey;
    const next = initialValues ?? {};
    baseValuesRef.current = next;
    draftValuesRef.current = next;
    dirtyFieldsRef.current = new Set();
    revisionRef.current = null;
    lastInitialValuesSignatureRef.current = initialValuesSignature;
    setBaseValues(next);
    setDraftValues(next);
    setDirtyFields(new Set());
    setConflicts({});
    setPeers({});
  }, [initialValues, initialValuesSignature, resourceKey]);

  useEffect(() => {
    if (initializedResourceRef.current !== resourceKey || lastInitialValuesSignatureRef.current === initialValuesSignature) return;
    lastInitialValuesSignatureRef.current = initialValuesSignature;
    if (dirtyFieldsRef.current.size > 0 || savingRef.current) return;
    const next = initialValues ?? {};
    baseValuesRef.current = next;
    draftValuesRef.current = next;
    revisionRef.current = null;
    setBaseValues(next);
    setDraftValues(next);
  }, [initialValues, initialValuesSignature, resourceKey]);

  useEffect(() => {
    cancelledRef.current = false;
    if (!enabled || import.meta.env.VITE_REALTIME_EVENTS_ENABLED === "false" || !resourceId || !session.hotelId || !session.userId) {
      setStatus("idle");
      return () => {
        cancelledRef.current = true;
      };
    }

    let retryDelay = 500;
    const connect = async () => {
      if (cancelledRef.current) return;
      setStatus(reconnectAttemptRef.current > 0 ? "reconnecting" : "connecting");
      try {
        const ticket = await createCollaborationTicket(resourceType, resourceId, session);
        if (cancelledRef.current) return;
        const socket = new WebSocket(collaborationWebSocketUrl());
        socketRef.current = socket;
        socket.onopen = () => {
          socket.send(JSON.stringify({ ticket: ticket.ticket, hotel_id: session.hotelId }));
        };
        socket.onmessage = (event) => {
          let parsed: unknown;
          try {
            parsed = JSON.parse(event.data as string);
          } catch {
            return;
          }
          const message = parseWsMessage(parsed);
          if (!message) return;
          if (message.type === "ready") {
            connectionIdRef.current = message.connection_id;
            reconnectAttemptRef.current = 0;
            retryDelay = 500;
            setStatus("connected");
            setError(null);
            sendPresence();
            // A reconnect can complete after the operator edited a field
            // while the socket was unavailable. Replay only the current safe
            // draft so the other editor does not miss that transient change.
            resendDirtyDraft();
            return;
          }
          if (message.type === "presence") {
            setPeers((previous) => {
              if (message.event === "left") {
                const next = { ...previous };
                delete next[message.connection_id];
                return next;
              }
              return {
                ...previous,
                [message.connection_id]: {
                  connectionId: message.connection_id,
                  userId: message.user_id,
                  fields: message.fields
                }
              };
            });
            return;
          }
          if (message.type === "draft_patch" && message.connection_id !== connectionIdRef.current) {
            const nextDraft = { ...draftValuesRef.current };
            const nextBase = { ...baseValuesRef.current };
            const nextDirty = new Set(dirtyFieldsRef.current);
            const remoteConflicts: CollaborationConflict[] = [];
            Object.entries(message.changes).forEach(([field, remoteValue]) => {
              if (nextDirty.has(field) && !Object.is(nextDraft[field], remoteValue)) {
                remoteConflicts.push({ field, localValue: nextDraft[field], remoteValue });
                return;
              }
              nextDraft[field] = remoteValue;
              nextBase[field] = remoteValue;
              nextDirty.delete(field);
            });
            draftValuesRef.current = nextDraft;
            baseValuesRef.current = nextBase;
            dirtyFieldsRef.current = nextDirty;
            setDraftValues(nextDraft);
            setBaseValues(nextBase);
            setDirtyFields(nextDirty);
            if (remoteConflicts.length) {
              setConflicts((previous) => {
                const next = { ...previous };
                remoteConflicts.forEach((conflict) => {
                  next[conflict.field] = conflict;
                });
                return next;
              });
              setStatus("conflict");
            }
          }
        };
        socket.onerror = () => {
          setStatus("degraded");
        };
        socket.onclose = () => {
          if (cancelledRef.current) return;
          socketRef.current = null;
          connectionIdRef.current = null;
          reconnectAttemptRef.current += 1;
          setStatus(reconnectAttemptRef.current >= 3 ? "degraded" : "reconnecting");
          const delay = Math.min(retryDelay, MAX_RECONNECT_DELAY_MS) + Math.floor(Math.random() * 250);
          retryDelay = Math.min(retryDelay * 2, MAX_RECONNECT_DELAY_MS);
          retryTimerRef.current = window.setTimeout(() => void connect(), delay);
        };
      } catch (cause) {
        if (cancelledRef.current) return;
        setError(cause instanceof Error ? cause.message : "No se pudo conectar la colaboración");
        reconnectAttemptRef.current += 1;
        setStatus(reconnectAttemptRef.current >= 3 ? "degraded" : "reconnecting");
        const delay = Math.min(retryDelay, MAX_RECONNECT_DELAY_MS) + Math.floor(Math.random() * 250);
        retryDelay = Math.min(retryDelay * 2, MAX_RECONNECT_DELAY_MS);
        retryTimerRef.current = window.setTimeout(() => void connect(), delay);
      }
    };
    void connect();

    return () => {
      cancelledRef.current = true;
      if (retryTimerRef.current !== null) window.clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
      socketRef.current?.close();
      socketRef.current = null;
      setPeers({});
    };
  }, [enabled, resendDirtyDraft, resourceId, resourceKey, resourceType, sendPresence, session]);

  const setField = useCallback(
    (field: string, value: unknown) => {
      const nextDraft = { ...draftValuesRef.current, [field]: value };
      const nextDirty = new Set(dirtyFieldsRef.current);
      if (Object.is(baseValuesRef.current[field], value)) nextDirty.delete(field);
      else nextDirty.add(field);
      draftValuesRef.current = nextDraft;
      dirtyFieldsRef.current = nextDirty;
      setDraftValues(nextDraft);
      setDirtyFields(nextDirty);
      setConflicts((previous) => {
        const next = { ...previous };
        if (next[field]) next[field] = { ...next[field], localValue: value };
        return next;
      });
      send({
        type: "draft_patch",
        base_revision: revisionRef.current ?? "pending",
        changes: { [field]: value }
      });
    },
    [send]
  );

  const focusField = useCallback(
    (field: string) => {
      focusedFieldsRef.current.add(field);
      sendPresence();
    },
    [sendPresence]
  );

  const blurField = useCallback(
    (field: string) => {
      focusedFieldsRef.current.delete(field);
      sendPresence();
    },
    [sendPresence]
  );

  const keepMine = useCallback(
    (field: string) => {
      setConflicts((previous) => {
        const next = { ...previous };
        delete next[field];
        return next;
      });
      dirtyFieldsRef.current = new Set(dirtyFieldsRef.current).add(field);
      setDirtyFields(new Set(dirtyFieldsRef.current));
    },
    []
  );

  const useRemote = useCallback(
    (field: string) => {
      const conflict = conflicts[field];
      if (!conflict) return;
      const nextDraft = { ...draftValuesRef.current, [field]: conflict.remoteValue };
      draftValuesRef.current = nextDraft;
      const nextDirty = new Set(dirtyFieldsRef.current).add(field);
      dirtyFieldsRef.current = nextDirty;
      setDraftValues(nextDraft);
      setDirtyFields(nextDirty);
      setConflicts((previous) => {
        const next = { ...previous };
        delete next[field];
        return next;
      });
    },
    [conflicts]
  );

  const save = useCallback(async () => {
    if (!resourceId || savingRef.current || dirtyFieldsRef.current.size === 0) return null;
    savingRef.current = true;
    setStatus("saving");
    setError(null);
    const changes = Object.fromEntries(
      Array.from(dirtyFieldsRef.current).map((field) => [field, draftValuesRef.current[field]])
    );
    const base = Object.fromEntries(
      Array.from(dirtyFieldsRef.current).map((field) => [field, baseValuesRef.current[field]])
    );
    try {
      const response = await patchCollaborativeResource(
        resourceType,
        resourceId,
        {
          base_revision: revisionRef.current ?? "pending",
          changes,
          base_values: base
        },
        session
      );
      baseValuesRef.current = response.resource;
      draftValuesRef.current = response.resource;
      dirtyFieldsRef.current = new Set();
      revisionRef.current = response.revision;
      setBaseValues(response.resource);
      setDraftValues(response.resource);
      setDirtyFields(new Set());
      setConflicts({});
      setStatus("connected");
      await refreshAfterMutation(queryClient, session.hotelId, resourceDomains(resourceType));
      return response;
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409 && isRecord(cause.payload)) {
        const detail = cause.payload.detail;
        if (isRecord(detail) && detail.code === "COLLABORATION_CONFLICT") {
          const serverResource = isRecord(detail.server_resource) ? detail.server_resource : {};
          const fields = Array.isArray(detail.conflicting_fields)
            ? detail.conflicting_fields.filter((field): field is string => typeof field === "string")
            : Object.keys(serverResource);
          const nextConflicts: Record<string, CollaborationConflict> = {};
          fields.forEach((field) => {
            nextConflicts[field] = {
              field,
              localValue: draftValuesRef.current[field],
              remoteValue: serverResource[field]
            };
          });
          baseValuesRef.current = serverResource;
          revisionRef.current = typeof detail.server_revision === "string" ? detail.server_revision : revisionRef.current;
          setBaseValues(serverResource);
          setConflicts(nextConflicts);
          setStatus("conflict");
        }
      }
      setError(cause instanceof Error ? cause.message : "No se pudo guardar el cambio");
      throw cause;
    } finally {
      savingRef.current = false;
      // Use the latest state rather than the value captured when save() was
      // created; a failed refresh must not leave the editor stuck on
      // "saving", while a structured conflict must remain visible.
      setStatus((current) => (current === "saving" ? "connected" : current));
    }
  }, [queryClient, resourceId, resourceType, session]);

  return {
    baseValues,
    draftValues,
    dirtyFields,
    conflicts,
    peers: Object.values(peers),
    status,
    error,
    setField,
    focusField,
    blurField,
    keepMine,
    useRemote,
    save,
    isDirty: dirtyFields.size > 0,
    isSaving: status === "saving"
  };
}
