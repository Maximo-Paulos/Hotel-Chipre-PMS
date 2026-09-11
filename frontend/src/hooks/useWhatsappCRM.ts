import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  assignWhatsAppConversation,
  createWhatsAppNote,
  fetchWhatsAppChannel,
  fetchWhatsAppConversations,
  sendWhatsAppMessage,
} from "../api/whatsapp";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

export function useWhatsAppCRM() {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const enabled = hasValidSession(session);
  const channel = useQuery({
    queryKey: ["whatsapp", "channel", session.hotelId],
    queryFn: () => fetchWhatsAppChannel(session), enabled, retry: false,
  });
  const conversations = useQuery({
    queryKey: ["whatsapp", "conversations", session.hotelId],
    queryFn: () => fetchWhatsAppConversations(session), enabled, refetchInterval: enabled ? 15_000 : false,
  });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["whatsapp"] });
  const send = useMutation({ mutationFn: ({ id, text }: { id: number; text: string }) => sendWhatsAppMessage(id, text, session), onSuccess: invalidate });
  const note = useMutation({ mutationFn: ({ id, body }: { id: number; body: string }) => createWhatsAppNote(id, body, session), onSuccess: invalidate });
  const assign = useMutation({ mutationFn: ({ id, userId }: { id: number; userId: number | null }) => assignWhatsAppConversation(id, userId, session), onSuccess: invalidate });
  return { channel, conversations, send, note, assign };
}
