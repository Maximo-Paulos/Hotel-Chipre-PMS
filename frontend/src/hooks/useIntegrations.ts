import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchIntegrations,
  connectIntegration,
  revokeIntegration,
  refreshIntegration,
  finalizeIntegrationOAuth,
  type IntegrationStatus,
} from "../api/integrations";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

const integrationsKey = ["integrations"];

export const useIntegrations = () => {
  const { session } = useSession();
  return useQuery<IntegrationStatus>({
    queryKey: [...integrationsKey, session.hotelId, session.userId],
    queryFn: () => fetchIntegrations(session),
    enabled: hasValidSession(session),
  });
};

export const useConnectIntegration = () => {
  const client = useQueryClient();
  const { session } = useSession();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload?: Record<string, unknown> }) =>
      connectIntegration(id, payload, session),
    onSuccess: () => client.invalidateQueries({ queryKey: integrationsKey }),
  });
};

export const useRevokeIntegration = () => {
  const client = useQueryClient();
  const { session } = useSession();
  return useMutation({
    mutationFn: (id: number) => revokeIntegration(id, session),
    onSuccess: () => client.invalidateQueries({ queryKey: integrationsKey }),
  });
};

export const useRefreshIntegration = () => {
  const client = useQueryClient();
  const { session } = useSession();
  return useMutation({
    mutationFn: (id: number) => refreshIntegration(id, session),
    onSuccess: () => client.invalidateQueries({ queryKey: integrationsKey }),
  });
};

export const useFinalizeIntegrationOAuth = () => {
  const client = useQueryClient();
  const { session } = useSession();
  return useMutation({
    mutationFn: ({ id, code }: { id: number; code: string }) => finalizeIntegrationOAuth(id, code, session),
    onSuccess: () => client.invalidateQueries({ queryKey: integrationsKey }),
  });
};
