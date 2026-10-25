import type { GroupMember, Paginated, StudyGroup } from "../types/api";
import { apiFetch } from "./client";

export type GroupInput = {
  name: string;
  description?: string;
  course_code?: string;
};

export function listGroups(params: { mine?: boolean; search?: string; limit?: number; offset?: number } = {}) {
  const query = new URLSearchParams();
  if (params.mine) query.set("mine", "true");
  if (params.search) query.set("search", params.search);
  if (params.limit) query.set("limit", String(params.limit));
  if (params.offset) query.set("offset", String(params.offset));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiFetch<Paginated<StudyGroup>>(`/api/groups${suffix}`);
}

export function getGroup(groupId: string) {
  return apiFetch<StudyGroup>(`/api/groups/${groupId}`);
}

export function createGroup(input: GroupInput) {
  return apiFetch<StudyGroup>("/api/groups", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateGroup(groupId: string, input: Partial<GroupInput>) {
  return apiFetch<StudyGroup>(`/api/groups/${groupId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function deleteGroup(groupId: string) {
  return apiFetch<void>(`/api/groups/${groupId}`, { method: "DELETE" });
}

export function joinGroup(groupId: string) {
  return apiFetch<StudyGroup>(`/api/groups/${groupId}/join`, { method: "POST" });
}

export function leaveGroup(groupId: string) {
  return apiFetch<void>(`/api/groups/${groupId}/leave`, { method: "DELETE" });
}

export function listMembers(groupId: string) {
  return apiFetch<GroupMember[]>(`/api/groups/${groupId}/members`);
}

export function updateMemberRole(groupId: string, userId: string, role: "admin" | "member") {
  return apiFetch<GroupMember>(`/api/groups/${groupId}/members/${userId}`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
}

export function removeMember(groupId: string, userId: string) {
  return apiFetch<void>(`/api/groups/${groupId}/members/${userId}`, { method: "DELETE" });
}
