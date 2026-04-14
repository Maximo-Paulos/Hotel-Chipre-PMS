import { apiFetch, type SessionLike } from "./client";

export type GemmaChatRole = "user" | "assistant" | "system";

export type GemmaChatSession = {
  id: number;
  mode?: string | null;
  status?: string | null;
  title?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  last_message_preview?: string | null;
  message_count?: number | null;
};

export type GemmaChatMessage = {
  id: number;
  session_id?: number | null;
  hotel_id?: number | null;
  role: GemmaChatRole;
  raw_text?: string | null;
  redacted_text?: string | null;
  text?: string | null;
  content?: string | null;
  intent_type?: string | null;
  created_at?: string | null;
};

export type GemmaChatEnvelope = {
  session: GemmaChatSession;
  messages: GemmaChatMessage[];
  answer?: string | null;
  summary?: string | null;
  mode?: string | null;
  intent_type?: string | null;
  requires_confirmation?: boolean | null;
  actions?: Array<{
    action_run_id?: number | null;
    action_type: string;
    label?: string | null;
    payload?: Record<string, unknown> | null;
    requires_confirmation?: boolean | null;
    status?: string | null;
    result?: Record<string, unknown> | null;
  }> | null;
  preview?: {
    title?: string | null;
    impact_summary?: string | null;
    rationale?: string[] | null;
    changed_weights?: Array<{ key: string; from: number; to: number }> | null;
    changed_constraints?: Array<{ key: string; from: boolean; to: boolean }> | null;
  } | null;
  confidence?: number | null;
  missing_information?: string[] | null;
  warnings?: string[] | null;
  metadata?: Record<string, unknown> | null;
};

export type GemmaChatMessagePayload = {
  session_id?: number | null;
  message: string;
};

export type GemmaApproveActionPayload = {
  session_id: number;
};

export type GemmaApproveActionResponse = {
  action_run_id: number;
  status: string;
  created_suggestion_id: number;
  profile_id: number;
};

export type GemmaRejectActionPayload = {
  session_id: number;
};

export type GemmaRejectActionResponse = {
  action_run_id: number;
  status: string;
};

export type GemmaReviewDraftPayload = {
  session_id: number;
};

export type GemmaReviewDraftResponse = {
  action_run_id: number;
  status: string;
  created_suggestion_id: number;
  suggestion_status: string;
  profile_id: number;
};

export type GemmaApplyDraftPayload = {
  session_id: number;
  publish?: boolean;
  prompt_summary?: string | null;
};

export type GemmaApplyDraftResponse = {
  action_run_id: number;
  status: string;
  created_suggestion_id: number;
  suggestion_status: string;
  created_version_id: number;
  version_number: number;
  is_published: boolean;
  profile_id: number;
};

export type GemmaRuntimeStatus = {
  enabled: boolean;
  configured: boolean;
  provider: string;
  model?: string | null;
  endpoint_url?: string | null;
  status: string;
  reachable: boolean;
  strict_json: boolean;
  timeout_seconds?: number | null;
  max_conversation_messages?: number | null;
  max_input_chars?: number | null;
  fallback_reason?: string | null;
  probe_error?: string | null;
};

export type GemmaInsight = {
  id: number;
  session_id: number;
  insight_type: string;
  summary: string;
  details?: Record<string, unknown> | null;
  created_at?: string | null;
};

export const fetchGemmaChatHistory = (session?: SessionLike) =>
  apiFetch<GemmaChatSession[]>("/api/gemma/chat/history", { session });

export const fetchGemmaInsights = (session?: SessionLike) =>
  apiFetch<GemmaInsight[]>("/api/gemma/chat/insights", { session });

export const fetchGemmaChatSession = (sessionId: number, session?: SessionLike) =>
  apiFetch<GemmaChatEnvelope>(`/api/gemma/chat/session/${sessionId}`, { session });

export const archiveGemmaChatSession = (sessionId: number, session?: SessionLike) =>
  apiFetch<GemmaChatSession>(`/api/gemma/chat/session/${sessionId}/archive`, {
    method: "POST",
    session,
  });

export const fetchGemmaRuntimeStatus = (session?: SessionLike) =>
  apiFetch<GemmaRuntimeStatus>("/api/gemma/chat/runtime-status", { session });

export const sendGemmaChatMessage = (payload: GemmaChatMessagePayload, session?: SessionLike) =>
  apiFetch<GemmaChatEnvelope>("/api/gemma/chat/message", {
    method: "POST",
    data: payload,
    session,
  });

export const approveGemmaAction = (actionRunId: number, payload: GemmaApproveActionPayload, session?: SessionLike) =>
  apiFetch<GemmaApproveActionResponse>(`/api/gemma/chat/actions/${actionRunId}/approve`, {
    method: "POST",
    data: payload,
    session,
  });

export const rejectGemmaAction = (actionRunId: number, payload: GemmaRejectActionPayload, session?: SessionLike) =>
  apiFetch<GemmaRejectActionResponse>(`/api/gemma/chat/actions/${actionRunId}/reject`, {
    method: "POST",
    data: payload,
    session,
  });

export const reviewGemmaDraft = (actionRunId: number, payload: GemmaReviewDraftPayload, session?: SessionLike) =>
  apiFetch<GemmaReviewDraftResponse>(`/api/gemma/chat/actions/${actionRunId}/review-draft`, {
    method: "POST",
    data: payload,
    session,
  });

export const applyGemmaDraft = (actionRunId: number, payload: GemmaApplyDraftPayload, session?: SessionLike) =>
  apiFetch<GemmaApplyDraftResponse>(`/api/gemma/chat/actions/${actionRunId}/apply-draft`, {
    method: "POST",
    data: payload,
    session,
  });
