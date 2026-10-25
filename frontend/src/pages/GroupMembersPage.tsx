import { useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getGroup, listMembers, removeMember, updateMemberRole } from "../api/groups";
import { ApiError } from "../api/client";
import { useAuth } from "../features/auth/AuthContext";
import { Alert, EmptyState, Spinner } from "../components/ui/Feedback";
import { Button } from "../components/ui/Button";
import { ConfirmDialog, PageHeader } from "../components/ui/Overlay";
import { formatDate, fullName, roleLabel } from "../utils/format";
import type { GroupMember } from "../types/api";

export function GroupMembersPage() {
  const { groupId = "" } = useParams();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [pendingRemove, setPendingRemove] = useState<GroupMember | null>(null);
  const [error, setError] = useState<string | null>(null);

  const groupQuery = useQuery({
    queryKey: ["group", groupId],
    queryFn: () => getGroup(groupId),
    enabled: Boolean(groupId),
  });
  const membersQuery = useQuery({
    queryKey: ["members", groupId],
    queryFn: () => listMembers(groupId),
    enabled: Boolean(groupId),
  });

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: "admin" | "member" }) =>
      updateMemberRole(groupId, userId, role),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["members", groupId] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Unable to update role"),
  });

  const removeMutation = useMutation({
    mutationFn: (userId: string) => removeMember(groupId, userId),
    onSuccess: async () => {
      setPendingRemove(null);
      await queryClient.invalidateQueries({ queryKey: ["members", groupId] });
      await queryClient.invalidateQueries({ queryKey: ["group", groupId] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Unable to remove member"),
  });

  if (!groupId) return <Navigate to="/app/groups" replace />;
  if (groupQuery.isLoading || membersQuery.isLoading) {
    return <Spinner label="Loading members" />;
  }
  if (membersQuery.error instanceof ApiError && membersQuery.error.status === 403) {
    return (
      <EmptyState
        title="Members are visible to group members"
        body="Join this group to see who else is in it."
        action={
          <Link to={`/app/groups/${groupId}`} className="text-sm font-medium text-teal-800 hover:underline">
            Back to group
          </Link>
        }
      />
    );
  }
  if (!groupQuery.data || !membersQuery.data) {
    return <Alert>Unable to load members.</Alert>;
  }

  const isOwner = groupQuery.data.my_role === "owner";
  const canRemove = groupQuery.data.my_role === "owner" || groupQuery.data.my_role === "admin";

  return (
    <div>
      <PageHeader
        title={`${groupQuery.data.name} members`}
        description="Owners can promote members to admin. Admins and owners can remove members."
        actions={
          <Link
            to={`/app/groups/${groupId}`}
            className="text-sm font-medium text-teal-800 hover:underline"
          >
            Back to group
          </Link>
        }
      />
      {error ? <Alert>{error}</Alert> : null}
      <div className="overflow-x-auto rounded-lg border border-stone-200 bg-white">
        <table className="w-full min-w-[40rem] text-left text-sm">
          <thead className="border-b border-stone-200 bg-stone-50 text-xs uppercase tracking-wide text-stone-500">
            <tr>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Role</th>
              <th className="px-4 py-3 font-medium">Joined</th>
              <th className="px-4 py-3 font-medium">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {membersQuery.data.map((member) => (
              <tr key={member.user_id} className="border-b border-stone-100 last:border-0">
                <td className="px-4 py-3">
                  <div className="font-medium text-stone-900">{fullName(member)}</div>
                  <div className="text-xs text-stone-500">{member.email}</div>
                </td>
                <td className="px-4 py-3">{roleLabel(member.role)}</td>
                <td className="px-4 py-3 text-stone-600">{formatDate(member.joined_at)}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap justify-end gap-2">
                    {isOwner && member.role === "member" ? (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => roleMutation.mutate({ userId: member.user_id, role: "admin" })}
                      >
                        Make admin
                      </Button>
                    ) : null}
                    {isOwner && member.role === "admin" ? (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => roleMutation.mutate({ userId: member.user_id, role: "member" })}
                      >
                        Make member
                      </Button>
                    ) : null}
                    {canRemove && member.role !== "owner" && member.user_id !== user?.id ? (
                      <Button size="sm" variant="ghost" onClick={() => setPendingRemove(member)}>
                        Remove
                      </Button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ConfirmDialog
        open={Boolean(pendingRemove)}
        title="Remove this member?"
        body={
          pendingRemove
            ? `${fullName(pendingRemove)} will lose access to this group until they join again.`
            : ""
        }
        confirmLabel="Remove member"
        danger
        busy={removeMutation.isPending}
        onClose={() => setPendingRemove(null)}
        onConfirm={() => {
          if (pendingRemove) removeMutation.mutate(pendingRemove.user_id);
        }}
      />
    </div>
  );
}
