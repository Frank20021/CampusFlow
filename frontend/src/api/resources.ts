import type { Paginated, Resource } from "../types/api";
import { apiFetch } from "./client";

export type ResourceInput = {
  title: string;
  url: string;
  description?: string | null;
};

export function listResources(groupId: string, params: { search?: string } = {}) {
  const query = new URLSearchParams();
  if (params.search) query.set("search", params.search);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiFetch<Paginated<Resource>>(`/api/groups/${groupId}/resources${suffix}`);
}

export function createResource(groupId: string, input: ResourceInput) {
  return apiFetch<Resource>(`/api/groups/${groupId}/resources`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function deleteResource(resourceId: string) {
  return apiFetch<void>(`/api/resources/${resourceId}`, { method: "DELETE" });
}
