import { useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteGroup, getGroup, joinGroup, leaveGroup, updateGroup } from "../api/groups";
import { ApiError } from "../api/client";
import { GroupForm } from "../features/groups/GroupForm";
import { Alert, EmptyState, Spinner } from "../components/ui/Feedback";
import { Button } from "../components/ui/Button";
import { ConfirmDialog, PageHeader } from "../components/ui/Overlay";
import { formatDate, roleLabel } from "../utils/format";

export function StudyGroupPage() {
  const { groupId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [confirmLeave, setConfirmLeave] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const groupQuery = useQuery({
    queryKey: ["group", groupId],
    queryFn: () => getGroup(groupId),
    enabled: Boolean(groupId),
  });

  async function invalidate() {
    await queryClient.invalidateQueries({ queryKey: ["group", groupId] });
    await queryClient.invalidateQueries({ queryKey: ["groups"] });
    await queryClient.invalidateQueries({ queryKey: ["members", groupId] });
  }

  const joinMutation = useMutation({
    mutationFn: () => joinGroup(groupId),
    onSuccess: invalidate,
    onError: (error) => setActionError(error instanceof ApiError ? error.message : "Unable to join"),
  });
  const leaveMutation = useMutation({
    mutationFn: () => leaveGroup(groupId),
    onSuccess: async () => {
      setConfirmLeave(false);
      await invalidate();
    },
    onError: (error) => setActionError(error instanceof ApiError ? error.message : "Unable to leave"),
  });
  const deleteMutation = useMutation({
    mutationFn: () => deleteGroup(groupId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
      void navigate("/app/groups");
    },
    onError: (error) => setActionError(error instanceof ApiError ? error.message : "Unable to delete"),
  });
  const updateMutation = useMutation({
    mutationFn: (input: { name: string; description?: string; course_code?: string }) =>
      updateGroup(groupId, input),
    onSuccess: async () => {
      setEditing(false);
      await invalidate();
    },
    onError: (error) => setActionError(error instanceof ApiError ? error.message : "Unable to update"),
  });

  if (!groupId) return <Navigate to="/app/groups" replace />;
  if (groupQuery.isLoading) return <Spinner label="Loading group" />;
  if (groupQuery.error instanceof ApiError && groupQuery.error.status === 404) {
    return (
      <EmptyState
        title="Group not found"
        body="It may have been deleted, or the link is incorrect."
        action={
          <Link to="/app/discover" className="text-sm font-medium text-teal-800 hover:underline">
            Browse groups
          </Link>
        }
      />
    );
  }
  if (!groupQuery.data) return <Alert>Unable to load this group.</Alert>;

  const group = groupQuery.data;
  const canManage = group.my_role === "owner" || group.my_role === "admin";
  const isOwner = group.my_role === "owner";
  const isMember = Boolean(group.my_role);

  return (
    <div>
      <PageHeader
        title={group.name}
        description={group.course_code ? `${group.course_code}` : undefined}
        actions={
          <div className="flex flex-wrap gap-2">
            {isMember ? (
              <Link
                to={`/app/groups/${group.id}/messages`}
                className="inline-flex h-10 items-center rounded-md border border-stone-300 bg-white px-4 text-sm font-medium hover:bg-stone-50"
              >
                Chat
              </Link>
            ) : null}
            {isMember ? (
              <Link
                to={`/app/groups/${group.id}/tasks`}
                className="inline-flex h-10 items-center rounded-md border border-stone-300 bg-white px-4 text-sm font-medium hover:bg-stone-50"
              >
                Tasks
              </Link>
            ) : null}
            {isMember ? (
              <Link
                to={`/app/groups/${group.id}/sessions`}
                className="inline-flex h-10 items-center rounded-md border border-stone-300 bg-white px-4 text-sm font-medium hover:bg-stone-50"
              >
                Sessions
              </Link>
            ) : null}
            {isMember ? (
              <Link
                to={`/app/groups/${group.id}/resources`}
                className="inline-flex h-10 items-center rounded-md border border-stone-300 bg-white px-4 text-sm font-medium hover:bg-stone-50"
              >
                Resources
              </Link>
            ) : null}
            {isMember ? (
              <Link
                to={`/app/groups/${group.id}/members`}
                className="inline-flex h-10 items-center rounded-md border border-stone-300 bg-white px-4 text-sm font-medium hover:bg-stone-50"
              >
                Members
              </Link>
            ) : null}
            {!isMember ? (
              <Button onClick={() => joinMutation.mutate()} loading={joinMutation.isPending}>
                Join group
              </Button>
            ) : null}
            {isMember && !isOwner ? (
              <Button variant="secondary" onClick={() => setConfirmLeave(true)}>
                Leave
              </Button>
            ) : null}
            {isOwner ? (
              <Button variant="danger" onClick={() => setConfirmDelete(true)}>
                Delete group
              </Button>
            ) : null}
          </div>
        }
      />
      {actionError ? <Alert>{actionError}</Alert> : null}
      <dl className="mb-6 grid gap-4 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-stone-500">Your role</dt>
          <dd className="mt-1 font-medium">{roleLabel(group.my_role)}</dd>
        </div>
        <div>
          <dt className="text-stone-500">Members</dt>
          <dd className="mt-1 font-medium">{group.member_count}</dd>
        </div>
        <div>
          <dt className="text-stone-500">Created</dt>
          <dd className="mt-1 font-medium">{formatDate(group.created_at)}</dd>
        </div>
      </dl>
      {editing && canManage ? (
        <div className="max-w-xl rounded-lg border border-stone-200 bg-white p-5">
          <GroupForm
            initial={{
              name: group.name,
              description: group.description ?? undefined,
              course_code: group.course_code ?? undefined,
            }}
            submitLabel="Save changes"
            busy={updateMutation.isPending}
            onSubmit={async (input) => {
              await updateMutation.mutateAsync(input);
            }}
          />
          <Button variant="ghost" className="mt-2" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </div>
      ) : (
        <div className="rounded-lg border border-stone-200 bg-white p-5">
          <p className="text-sm leading-6 text-stone-700">
            {group.description || "No description yet."}
          </p>
          {canManage ? (
            <Button variant="secondary" size="sm" className="mt-4" onClick={() => setEditing(true)}>
              Edit group
            </Button>
          ) : null}
        </div>
      )}

      <ConfirmDialog
        open={confirmLeave}
        title="Leave this group?"
        body="You can join again later from Discover."
        confirmLabel="Leave group"
        busy={leaveMutation.isPending}
        onClose={() => setConfirmLeave(false)}
        onConfirm={() => leaveMutation.mutate()}
      />
      <ConfirmDialog
        open={confirmDelete}
        title="Delete this group?"
        body="This permanently removes the group and its memberships. This cannot be undone."
        confirmLabel="Delete group"
        danger
        busy={deleteMutation.isPending}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => deleteMutation.mutate()}
      />
    </div>
  );
}
