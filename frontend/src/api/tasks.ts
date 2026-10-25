import type { MyTask, Paginated, Task, TaskPriority, TaskStatus } from "../types/api";
import { apiFetch } from "./client";

export type TaskCreateInput = {
  title: string;
  description?: string | null;
  assigned_to?: string | null;
  status?: TaskStatus;
  priority?: TaskPriority;
  due_date?: string | null;
};

export type TaskUpdateInput = Partial<TaskCreateInput>;

export function listTasks(
  groupId: string,
  params: { status?: TaskStatus; assignedTo?: string } = {},
) {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.assignedTo) query.set("assigned_to", params.assignedTo);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiFetch<Paginated<Task>>(`/api/groups/${groupId}/tasks${suffix}`);
}

export function createTask(groupId: string, input: TaskCreateInput) {
  return apiFetch<Task>(`/api/groups/${groupId}/tasks`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateTask(taskId: string, input: TaskUpdateInput) {
  return apiFetch<Task>(`/api/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function deleteTask(taskId: string) {
  return apiFetch<void>(`/api/tasks/${taskId}`, { method: "DELETE" });
}

export function listMyTasks(limit = 5) {
  return apiFetch<MyTask[]>(`/api/tasks/mine?limit=${limit}`);
}
