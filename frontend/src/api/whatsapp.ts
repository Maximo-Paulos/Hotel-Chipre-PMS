import { apiFetch, type SessionLike } from "./client";

export type WhatsAppMessage = {
  id: number;
  direction: string;
  status: string;
  message_type: string;
  text?: string | null;
  actor_user_id?: number | null;
  provider_message_id?: string | null;
  created_at: string;
  occurred_at?: string | null;
};

export type WhatsAppConversation = {
  id: number;
  hotel_id: number;
  status: "new" | "open" | "assigned" | "pending" | "closed";
  priority: string;
  assigned_to_user_id?: number | null;
  department?: string | null;
  shift_key?: string | null;
  human_active: boolean;
  service_window_expires_at?: string | null;
  last_inbound_at?: string | null;
  last_message_at?: string | null;
  contact: { id: number; normalized_phone: string; display_name?: string | null; guest_id?: number | null };
  messages: WhatsAppMessage[];
};

export type WhatsAppChannelStatus = {
  status: string;
  channel: { id: number; status: string; display_phone_number?: string | null; display_name?: string | null } | null;
};

export const fetchWhatsAppChannel = (session?: SessionLike) =>
  apiFetch<WhatsAppChannelStatus>("/api/whatsapp/channel", { session });

export const completeWhatsAppChannel = (payload: {
  waba_id: string;
  phone_number_id: string;
  display_phone_number?: string;
  display_name?: string;
}, session?: SessionLike) =>
  apiFetch("/api/whatsapp/channel/complete", { method: "POST", data: payload, session });

export const fetchWhatsAppConversations = (session?: SessionLike) =>
  apiFetch<{ items: WhatsAppConversation[] }>("/api/whatsapp/conversations?all=true", { session });

export const sendWhatsAppMessage = (conversationId: number, text: string, session?: SessionLike) =>
  apiFetch<WhatsAppMessage>(`/api/whatsapp/conversations/${conversationId}/messages`, {
    method: "POST", data: { text }, session
  });

export const createWhatsAppNote = (conversationId: number, body: string, session?: SessionLike) =>
  apiFetch<{ id: number }>(`/api/whatsapp/conversations/${conversationId}/notes`, {
    method: "POST", data: { body }, session
  });

export const assignWhatsAppConversation = (conversationId: number, assignedToUserId: number | null, session?: SessionLike) =>
  apiFetch<WhatsAppConversation>(`/api/whatsapp/conversations/${conversationId}/assignment`, {
    method: "POST", data: { assigned_to_user_id: assignedToUserId }, session
  });
