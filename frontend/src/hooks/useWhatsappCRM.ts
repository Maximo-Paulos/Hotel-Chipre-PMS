import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  assignWhatsAppConversation,
  createWhatsAppNote,
  fetchWhatsAppChannel,
  fetchWhatsAppConversations,
  fetchWhatsAppMessages,
  sendWhatsAppMessage,
} from "../api/whatsapp";
import { hasValidSession } from "../api/client";
import { invalidateQueriesInBackground } from "../api/queryInvalidation";
import { useSession } from "../state/session";

export function useWhatsAppChannel() {
  const { session } = useSession();
  const enabled = hasValidSession(session);
  return useQuery({
    queryKey: ["whatsapp-channel", session.hotelId],
    queryFn: () => fetchWhatsAppChannel(session), enabled, retry: false,
  });
}

export function useWhatsAppCRM(conversationId: number | null) {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const enabled = hasValidSession(session);
  const channel = useWhatsAppChannel();
  const conversations = useQuery({
    queryKey: ["whatsapp-conversations", session.hotelId],
    queryFn: () => fetchWhatsAppConversations(session),
    enabled,
    staleTime: 15_000,
  });
  const activeConversationId = conversations.data?.items.some((item) => item.id === conversationId)
    ? conversationId
    : conversations.data?.items[0]?.id ?? null;
  const conversationListKey = ["whatsapp-conversations", session.hotelId] as const;
  const messagesKey = ["whatsapp-conversations", session.hotelId, "messages", activeConversationId] as const;
  const messages = useInfiniteQuery({
    queryKey: messagesKey,
    queryFn: ({ pageParam }) => fetchWhatsAppMessages(activeConversationId!, pageParam, session),
    enabled: enabled && activeConversationId !== null,
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (lastPage, _pages, _lastPageParam, allPageParams) => {
      const cursor = lastPage.next_before_message_id;
      return lastPage.has_more && cursor !== null && !allPageParams.includes(cursor) ? cursor : undefined;
    },
    staleTime: 15_000,
  });
  const invalidateConversations = () => invalidateQueriesInBackground(queryClient, {
    queryKey: conversationListKey,
    exact: true,
  });
  const invalidateMessages = (id: number) => invalidateQueriesInBackground(queryClient, {
    queryKey: ["whatsapp-conversations", session.hotelId, "messages", id],
    exact: true,
  });
  const send = useMutation({
    mutationFn: ({ id, text }: { id: number; text: string }) => sendWhatsAppMessage(id, text, session),
    onSuccess: (message, variables) => {
      const key = ["whatsapp-conversations", session.hotelId, "messages", variables.id] as const;
      queryClient.setQueryData<typeof messages.data>(key, (current) => {
        if (!current) return current;
        const firstPage = current.pages[0];
        if (!firstPage || firstPage.items.some((item) => item.id === message.id)) return current;
        return {
          ...current,
          pages: [
            { ...firstPage, items: [...firstPage.items, message] },
            ...current.pages.slice(1),
          ],
        };
      });
      invalidateConversations();
      invalidateMessages(variables.id);
    },
  });
  const note = useMutation({
    mutationFn: ({ id, body }: { id: number; body: string }) => createWhatsAppNote(id, body, session),
    onSuccess: invalidateConversations,
  });
  const assign = useMutation({
    mutationFn: ({ id, userId }: { id: number; userId: number | null }) => assignWhatsAppConversation(id, userId, session),
    onSuccess: invalidateConversations,
  });
  return { channel, conversations, messages, send, note, assign };
}
