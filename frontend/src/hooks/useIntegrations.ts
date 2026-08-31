import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchIntegrations,
  connectIntegration,
  revokeIntegration,
  refreshIntegration,
  finalizeIntegrationOAuth,
  type IntegrationStatus
} from "../api/integrations";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";
import { queryKeys } from "../api/queryKeys";
import { refreshSettingsState } from "../api/queryInvalidation";

import { useGuardedMutation } from "./useGuardedMutation";

export const useIntegrations = () => {
  const { session } = useSession();
  return useQuery<IntegrationStatus>({
    queryKey: [...queryKeys.integrations(session.hotelId), session.userId],
    queryFn: () => fetchIntegrations(session),
    enabled: hasValidSession(session)
  });
};

export const useConnectIntegration = () => {
  const client = useQueryClient();
  const { session } = useSession();
  return useGuardedMutation({
    mutationFn: ({ id, payload }: { id: number; payload?: Record<string, unknown> }) =>
      connectIntegration(id, payload, session),
    onSuccess: async () => refreshSettingsState(client, session.hotelId)
  });
};

export const useRevokeIntegration = () => {
  const client = useQueryClient();
  const { session } = useSession();
  return useGuardedMutation({
    mutationFn: (id: number) => revokeIntegration(id, session),
    onSuccess: async () => refreshSettingsState(client, session.hotelId)
  });
};

export const useRefreshIntegration = () => {
  const client = useQueryClient();
  const { session } = useSession();
  return useGuardedMutation({
    mutationFn: (id: number) => refreshIntegration(id, session),
    onSuccess: async () => refreshSettingsState(client, session.hotelId)
  });
};

export const useFinalizeIntegrationOAuth = () => {
  const client = useQueryClient();
  const { session } = useSession();
  return useGuardedMutation({
    mutationFn: ({ id, code }: { id: number; code: string }) => finalizeIntegrationOAuth(id, code, session),
    onSuccess: async () => refreshSettingsState(client, session.hotelId)
  });
};
