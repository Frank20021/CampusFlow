import { useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../api/client";
import { getGroup } from "../api/groups";
import { createResource, deleteResource, listResources, type ResourceInput } from "../api/resources";
import { ResourceForm } from "../features/resources/ResourceForm";
import { ResourceList } from "../features/resources/ResourceList";
import { Alert, EmptyState, Spinner } from "../components/ui/Feedback";
import { TextField } from "../components/ui/Field";
import { ConfirmDialog, PageHeader } from "../components/ui/Overlay";
import type { Resource } from "../types/api";

export function ResourcesPage() {
  const { groupId = "" } = useParams();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Resource | null>(null);
  const [announcement, setAnnouncement] = useState("");

  const groupQuery = useQuery({
    queryKey: ["group", groupId],
    queryFn: () => getGroup(groupId),
    enabled: Boolean(groupId),
  });

  const resourcesQuery = useQuery({
    queryKey: ["resources", groupId, search],
    queryFn: () => listResources(groupId, { search: search || undefined }),
    enabled: Boolean(groupId),
  });

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ["resources", groupId] });
  }

  const createMutation = useMutation({
    mutationFn: (input: ResourceInput) => createResource(groupId, input),
    onSuccess: async (resource) => {
      setFormError(null);
      setAnnouncement(`${resource.title} shared.`);
      await refresh();
    },
    onError: (error) =>
      setFormError(error instanceof ApiError ? error.message : "Unable to share that link"),
  });

  const deleteMutation = useMutation({
    mutationFn: (resource: Resource) => deleteResource(resource.id),
    onSuccess: async () => {
      setAnnouncement(`${pendingDelete?.title ?? "Resource"} removed.`);
      setPendingDelete(null);
      await refresh();
    },
    onError: (error) => {
      setPendingDelete(null);
      setActionError(error instanceof ApiError ? error.message : "Unable to remove that link");
    },
  });

  if (!groupId) return <Navigate to="/app/groups" replace />;
  if (groupQuery.isLoading) return <Spinner label="Loading resources" />;

  const notAMember =
    (groupQuery.error instanceof ApiError && groupQuery.error.status === 403) ||
    (resourcesQuery.error instanceof ApiError && resourcesQuery.error.status === 403);

  if (notAMember) {
    return (
      <EmptyState
        title="Members only"
        body="Join this group to see and share its resources."
        action={
          <Link
            to={`/app/groups/${groupId}`}
            className="text-sm font-medium text-teal-800 hover:underline"
          >
            Go to the group
          </Link>
        }
      />
    );
  }
  if (groupQuery.error instanceof ApiError && groupQuery.error.status === 404) {
    return <EmptyState title="Group not found" body="It may have been deleted." />;
  }
  if (!groupQuery.data) return <Alert>Unable to load this group.</Alert>;

  const group = groupQuery.data;
  const resources = resourcesQuery.data?.items ?? [];

  return (
    <div>
      <PageHeader
        title={`${group.name} resources`}
        description="Links the group has collected."
        actions={
          <Link
            to={`/app/groups/${groupId}`}
            className="inline-flex h-10 items-center rounded-md border border-stone-300 bg-white px-4 text-sm font-medium hover:bg-stone-50"
          >
            Back to group
          </Link>
        }
      />

      <ResourceForm
        busy={createMutation.isPending}
        serverError={formError}
        onSubmit={(input) => createMutation.mutate(input)}
      />

      <div className="mt-6 max-w-sm">
        <TextField
          label="Search resources"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by name or description"
        />
      </div>

      <p aria-live="polite" className="sr-only">
        {announcement}
      </p>
      {actionError ? <Alert>{actionError}</Alert> : null}
      {resourcesQuery.error && !notAMember ? (
        <Alert>Resources could not be loaded. Check your connection and reload.</Alert>
      ) : null}

      <div className="mt-4">
        {resourcesQuery.isLoading ? (
          <Spinner label="Loading resources" />
        ) : search && resources.length === 0 ? (
          <p className="rounded-lg border border-stone-200 bg-white p-8 text-center text-sm text-stone-500">
            Nothing matches “{search}”.
          </p>
        ) : (
          <ResourceList
            resources={resources}
            deletingId={deleteMutation.isPending ? (pendingDelete?.id ?? null) : null}
            onDelete={setPendingDelete}
          />
        )}
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Remove this link?"
        body={`"${pendingDelete?.title ?? ""}" will no longer be shared with the group.`}
        confirmLabel="Remove link"
        danger
        busy={deleteMutation.isPending}
        onClose={() => setPendingDelete(null)}
        onConfirm={() => pendingDelete && deleteMutation.mutate(pendingDelete)}
      />
    </div>
  );
}
