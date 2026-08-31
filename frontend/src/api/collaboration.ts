import { apiFetch, buildUrl, type SessionLike } from "./client";

export type CollaborationResourceType =
  | "reservation"
  | "guest"
  | "room"
  | "stock_item"
  | "linen_item"
  | "laundry_vendor"
  | "cash_session"
  | "settings";

export type CollaborationTicket = {
  ticket: string;
  expires_in: number;
  resource_type: CollaborationResourceType;
  resource_id: number;
};

export type CollaborationPatchResponse = {
  resource_type: CollaborationResourceType;
  resource_id: number;
  resource: Record<string, unknown>;
  revision: string;
  version?: number | null;
};

export type CollaborationWsMessage =
  | {
      type: "ready";
      connection_id: string;
      resource_type: CollaborationResourceType;
      resource_id: number;
    }
  | {
      type: "presence";
      event: "joined" | "updated" | "left";
      connection_id: string;
      user_id: number;
      fields: string[];
    }
  | {
      type: "draft_patch";
      connection_id: string;
      user_id: number;
      base_revision: string;
      changes: Record<string, unknown>;
    }
  | { type: "ping" | "pong" }
  | { type: "error"; code: string };

export async function createCollaborationTicket(
  resourceType: CollaborationResourceType,
  resourceId: number,
  session?: SessionLike
): Promise<CollaborationTicket> {
  return apiFetch<CollaborationTicket>("/api/collaboration/tickets", {
    method: "POST",
    data: { resource_type: resourceType, resource_id: resourceId },
    session
  });
}

export async function patchCollaborativeResource(
  resourceType: CollaborationResourceType,
  resourceId: number,
  payload: {
    base_revision: string;
    changes: Record<string, unknown>;
    base_values: Record<string, unknown>;
  },
  session?: SessionLike
): Promise<CollaborationPatchResponse> {
  return apiFetch<CollaborationPatchResponse>(
    `/api/collaboration/resources/${resourceType}/${resourceId}`,
    { method: "PATCH", data: payload, session }
  );
}

export function collaborationWebSocketUrl(): string {
  const httpUrl = buildUrl("/api/collaboration/ws");
  return httpUrl.replace(/^http:/i, "ws:").replace(/^https:/i, "wss:");
}

