import type {
  MySession,
  Paginated,
  RsvpStatus,
  SessionAttendee,
  StudySession,
} from "../types/api";
import { apiFetch } from "./client";

export type SessionInput = {
  title: string;
  description?: string | null;
  location?: string | null;
  start_time: string;
  end_time: string;
};

export type SessionListParams = {
  upcoming?: boolean;
  startsAfter?: string;
  startsBefore?: string;
  limit?: number;
};

export function listSessions(groupId: string, params: SessionListParams = {}) {
  const query = new URLSearchParams();
  if (params.upcoming) query.set("upcoming", "true");
  if (params.startsAfter) query.set("starts_after", params.startsAfter);
  if (params.startsBefore) query.set("starts_before", params.startsBefore);
  query.set("limit", String(params.limit ?? 100));
  return apiFetch<Paginated<StudySession>>(
    `/api/groups/${groupId}/sessions?${query.toString()}`,
  );
}

export function createSession(groupId: string, input: SessionInput) {
  return apiFetch<StudySession>(`/api/groups/${groupId}/sessions`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateSession(sessionId: string, input: Partial<SessionInput>) {
  return apiFetch<StudySession>(`/api/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function deleteSession(sessionId: string) {
  return apiFetch<void>(`/api/sessions/${sessionId}`, { method: "DELETE" });
}

export function setRsvp(sessionId: string, status: RsvpStatus) {
  return apiFetch<StudySession>(`/api/sessions/${sessionId}/rsvp`, {
    method: "PUT",
    body: JSON.stringify({ status }),
  });
}

export function clearRsvp(sessionId: string) {
  return apiFetch<StudySession>(`/api/sessions/${sessionId}/rsvp`, { method: "DELETE" });
}

export function listAttendees(sessionId: string) {
  return apiFetch<SessionAttendee[]>(`/api/sessions/${sessionId}/rsvps`);
}

export function listMySessions(limit = 5) {
  return apiFetch<MySession[]>(`/api/sessions/mine?limit=${limit}`);
}
