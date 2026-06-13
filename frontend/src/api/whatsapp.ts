import { buildUrl } from "./client";
import {
  connectIntegration,
  fetchIntegrations,
  refreshIntegration,
  revokeIntegration,
  type IntegrationConnection,
  type IntegrationStatus
} from "./integrations";
import {
  issueApiKey,
  listApiKeys,
  type HotelApiKey,
  type HotelApiKeyIssued,
  type IssueHotelApiKeyPayload
} from "./apiKeys";
import type { SessionLike } from "./client";

export type WhatsAppSettings = {
  integrationStatus: IntegrationStatus;
  connection?: IntegrationConnection;
  apiKeys: HotelApiKey[];
  hookBaseUrl: string;
  endpoints: Array<{ label: string; method: "GET" | "POST"; url: string }>;
};

const whatsappEndpoints: WhatsAppSettings["endpoints"] = [
  { label: "Disponibilidad", method: "GET", url: buildUrl("/api/public/whatsapp/availability") },
  { label: "Precios", method: "GET", url: buildUrl("/api/public/whatsapp/prices") },
  { label: "Opciones con precios", method: "GET", url: buildUrl("/api/public/whatsapp/options") },
  { label: "Crear reserva", method: "POST", url: buildUrl("/api/public/whatsapp/reservations") },
  { label: "Crear link de pago", method: "POST", url: buildUrl("/api/public/whatsapp/payment-links") },
  { label: "Confirmar pago", method: "POST", url: buildUrl("/api/public/whatsapp/payment-confirmation") }
];

export const fetchWhatsAppSettings = async (session?: SessionLike): Promise<WhatsAppSettings> => {
  const [integrationStatus, apiKeys] = await Promise.all([fetchIntegrations(session), listApiKeys(session)]);
  const connection = integrationStatus.connections.find((item) => item.integration.provider === "whatsapp");
  return {
    integrationStatus,
    connection,
    apiKeys: apiKeys.filter((key) => key.purpose === "whatsapp_bot"),
    hookBaseUrl: buildUrl("/api/public/whatsapp"),
    endpoints: whatsappEndpoints
  };
};

export const connectWhatsAppIntegration = (integrationId: number, payload: Record<string, string>, session?: SessionLike) =>
  connectIntegration(integrationId, payload, session);

export const revokeWhatsAppIntegration = (integrationId: number, session?: SessionLike) =>
  revokeIntegration(integrationId, session);

export const refreshWhatsAppIntegration = (integrationId: number, session?: SessionLike) =>
  refreshIntegration(integrationId, session);

export const issueWhatsAppApiKey = (
  payload: Omit<IssueHotelApiKeyPayload, "purpose">,
  session?: SessionLike
): Promise<HotelApiKeyIssued> =>
  issueApiKey(
    {
      ...payload,
      purpose: "whatsapp_bot"
    },
    session
  );
