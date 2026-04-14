import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { hasValidSession } from "../api/client";
import {
  archiveGemmaChatSession,
  applyGemmaDraft,
  approveGemmaAction,
  fetchGemmaChatHistory,
  fetchGemmaInsights,
  fetchGemmaChatSession,
  fetchGemmaRuntimeStatus,
  rejectGemmaAction,
  reviewGemmaDraft,
  sendGemmaChatMessage,
  type GemmaApplyDraftPayload,
  type GemmaApplyDraftResponse,
  type GemmaApproveActionPayload,
  type GemmaApproveActionResponse,
  type GemmaChatEnvelope,
  type GemmaChatSession,
  type GemmaChatMessagePayload,
  type GemmaInsight,
  type GemmaRejectActionPayload,
  type GemmaRejectActionResponse,
  type GemmaReviewDraftPayload,
  type GemmaReviewDraftResponse,
  type GemmaRuntimeStatus,
} from "../api/gemma";
import { useSession } from "../state/session";

const storageKey = (hotelId: number | null, userId: string | null) =>
  hotelId && userId ? `hotel-pms-gemma-session-${hotelId}-${userId}` : null;

const gemmaChatKey = (hotelId: number | null, sessionId: number | null) => ["gemma-chat", hotelId, sessionId];
const gemmaHistoryKey = (hotelId: number | null) => ["gemma-chat-history", hotelId];
const gemmaRuntimeKey = (hotelId: number | null) => ["gemma-runtime-status", hotelId];
const gemmaInsightsKey = (hotelId: number | null) => ["gemma-insights", hotelId];

const readStoredSessionId = (key: string | null): number | null => {
  if (!key || typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(key);
  if (!raw) return null;
  const parsed = Number.parseInt(raw, 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
};

const writeStoredSessionId = (key: string | null, value: number | null) => {
  if (typeof window === "undefined" || !key) return;
  if (!value) {
    window.localStorage.removeItem(key);
    return;
  }
  window.localStorage.setItem(key, String(value));
};

export function useGemmaChat() {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const [sessionId, setSessionId] = useState<number | null>(null);
  const storage = useMemo(() => storageKey(session.hotelId, session.userId), [session.hotelId, session.userId]);

  useEffect(() => {
    setSessionId(readStoredSessionId(storage));
  }, [storage]);

  useEffect(() => {
    writeStoredSessionId(storage, sessionId);
  }, [sessionId, storage]);

  const sessionQuery = useQuery<GemmaChatEnvelope>({
    queryKey: gemmaChatKey(session.hotelId, sessionId),
    queryFn: () => fetchGemmaChatSession(sessionId!, session),
    enabled: hasValidSession(session) && Boolean(sessionId),
    staleTime: 1000 * 10,
  });

  const historyQuery = useQuery<GemmaChatSession[]>({
    queryKey: gemmaHistoryKey(session.hotelId),
    queryFn: () => fetchGemmaChatHistory(session),
    enabled: hasValidSession(session),
    staleTime: 1000 * 10,
  });

  const runtimeStatusQuery = useQuery<GemmaRuntimeStatus>({
    queryKey: gemmaRuntimeKey(session.hotelId),
    queryFn: () => fetchGemmaRuntimeStatus(session),
    enabled: hasValidSession(session),
    staleTime: 1000 * 15,
    refetchInterval: 1000 * 30,
  });

  const insightsQuery = useQuery<GemmaInsight[]>({
    queryKey: gemmaInsightsKey(session.hotelId),
    queryFn: () => fetchGemmaInsights(session),
    enabled: hasValidSession(session),
    staleTime: 1000 * 15,
  });

  const clearConversation = useCallback(() => {
    setSessionId(null);
    if (storage) {
      writeStoredSessionId(storage, null);
    }
    queryClient.removeQueries({ queryKey: ["gemma-chat", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: gemmaHistoryKey(session.hotelId) });
  }, [queryClient, session.hotelId, storage]);

  const sendMessageMutation = useMutation({
    mutationFn: (payload: GemmaChatMessagePayload) => sendGemmaChatMessage(payload, session),
    onSuccess: async (result, variables) => {
      if (result.session?.id) {
        setSessionId(result.session.id);
      }
      const key = gemmaChatKey(session.hotelId, result.session?.id ?? sessionId);
      queryClient.setQueryData(key, result);
      await queryClient.invalidateQueries({ queryKey: ["gemma-chat", session.hotelId] });
      await queryClient.invalidateQueries({ queryKey: gemmaHistoryKey(session.hotelId) });
      await queryClient.invalidateQueries({ queryKey: gemmaInsightsKey(session.hotelId) });
      if (!variables.session_id && result.session?.id && result.session.id !== sessionId) {
        setSessionId(result.session.id);
      }
    },
  });

  const approveActionMutation = useMutation({
    mutationFn: ({ actionRunId, payload }: { actionRunId: number; payload: GemmaApproveActionPayload }) =>
      approveGemmaAction(actionRunId, payload, session),
    onSuccess: async (_result: GemmaApproveActionResponse, variables) => {
      await queryClient.invalidateQueries({ queryKey: gemmaChatKey(session.hotelId, variables.payload.session_id) });
      await queryClient.invalidateQueries({ queryKey: gemmaHistoryKey(session.hotelId) });
    },
  });

  const rejectActionMutation = useMutation({
    mutationFn: ({ actionRunId, payload }: { actionRunId: number; payload: GemmaRejectActionPayload }) =>
      rejectGemmaAction(actionRunId, payload, session),
    onSuccess: async (_result: GemmaRejectActionResponse, variables) => {
      await queryClient.invalidateQueries({ queryKey: gemmaChatKey(session.hotelId, variables.payload.session_id) });
      await queryClient.invalidateQueries({ queryKey: gemmaHistoryKey(session.hotelId) });
    },
  });

  const reviewDraftMutation = useMutation({
    mutationFn: ({ actionRunId, payload }: { actionRunId: number; payload: GemmaReviewDraftPayload }) =>
      reviewGemmaDraft(actionRunId, payload, session),
    onSuccess: async (_result: GemmaReviewDraftResponse, variables) => {
      await queryClient.invalidateQueries({ queryKey: gemmaChatKey(session.hotelId, variables.payload.session_id) });
      await queryClient.invalidateQueries({ queryKey: gemmaHistoryKey(session.hotelId) });
    },
  });

  const applyDraftMutation = useMutation({
    mutationFn: ({ actionRunId, payload }: { actionRunId: number; payload: GemmaApplyDraftPayload }) =>
      applyGemmaDraft(actionRunId, payload, session),
    onSuccess: async (_result: GemmaApplyDraftResponse, variables) => {
      await queryClient.invalidateQueries({ queryKey: gemmaChatKey(session.hotelId, variables.payload.session_id) });
      await queryClient.invalidateQueries({ queryKey: gemmaHistoryKey(session.hotelId) });
    },
  });

  const archiveSessionMutation = useMutation({
    mutationFn: (targetSessionId: number) => archiveGemmaChatSession(targetSessionId, session),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: gemmaHistoryKey(session.hotelId) });
      if (result.id === sessionId) {
        setSessionId(null);
        queryClient.removeQueries({ queryKey: gemmaChatKey(session.hotelId, result.id) });
        sendMessageMutation.reset();
      }
    },
  });

  const resetTransientState = useCallback(() => {
    sendMessageMutation.reset();
    approveActionMutation.reset();
    rejectActionMutation.reset();
    reviewDraftMutation.reset();
    applyDraftMutation.reset();
    archiveSessionMutation.reset();
  }, [
    sendMessageMutation,
    approveActionMutation,
    rejectActionMutation,
    reviewDraftMutation,
    applyDraftMutation,
    archiveSessionMutation,
  ]);

  const selectSession = useCallback(
    (nextSessionId: number | null) => {
      setSessionId(nextSessionId);
      resetTransientState();
    },
    [resetTransientState],
  );

  const activeEnvelope = useMemo(() => {
    const mutationEnvelope = sendMessageMutation.data ?? null;
    if (!sessionId) {
      return mutationEnvelope?.session?.id ? null : mutationEnvelope;
    }
    if (sessionQuery.data?.session?.id === sessionId) {
      return sessionQuery.data;
    }
    if (mutationEnvelope?.session?.id === sessionId) {
      return mutationEnvelope;
    }
    return sessionQuery.data ?? null;
  }, [sendMessageMutation.data, sessionId, sessionQuery.data]);

  const sendMessage = useCallback(
    (message: string) => {
      const trimmed = message.trim();
      if (!trimmed) {
        return Promise.reject(new Error("El mensaje no puede estar vacio."));
      }
      return sendMessageMutation.mutateAsync({
        session_id: sessionId,
        message: trimmed,
      });
    },
    [sendMessageMutation, sessionId],
  );

  return {
    activeSessionId: sessionId,
    setActiveSessionId: selectSession,
    clearConversation: useCallback(() => {
      clearConversation();
      resetTransientState();
    }, [clearConversation, resetTransientState]),
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
    isReady: hasValidSession(session),
  };
}
