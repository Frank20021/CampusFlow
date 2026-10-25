import type { Notification, Paginated, UnreadCount } from "../types/api";
import { apiFetch } from "./client";

export function listNotifications(params: { unreadOnly?: boolean; limit?: number } = {}) {
  const query = new URLSearchParams();
  if (params.unreadOnly) query.set("unread_only", "true");
  query.set("limit", String(params.limit ?? 20));
  return apiFetch<Paginated<Notification>>(`/api/notifications?${query.toString()}`);
}

export function getUnreadCount() {
  return apiFetch<UnreadCount>("/api/notifications/unread-count");
}

export function markNotificationRead(notificationId: string) {
  return apiFetch<Notification>(`/api/notifications/${notificationId}/read`, {
    method: "PATCH",
  });
}

export function markAllNotificationsRead() {
  return apiFetch<UnreadCount>("/api/notifications/read-all", { method: "POST" });
}
