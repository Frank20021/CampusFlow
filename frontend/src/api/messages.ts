import type { Message, MessagePage } from "../types/api";
import { apiFetch } from "./client";

export function listMessages(groupId: string, params: { before?: string; limit?: number } = {}) {
  const query = new URLSearchParams();
  if (params.before) query.set("before", params.before);
  query.set("limit", String(params.limit ?? 30));
  return apiFetch<MessagePage>(`/api/groups/${groupId}/messages?${query.toString()}`);
}

export function postMessage(groupId: string, content: string) {
  return apiFetch<Message>(`/api/groups/${groupId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export function deleteMessage(messageId: string) {
  return apiFetch<void>(`/api/messages/${messageId}`, { method: "DELETE" });
}
