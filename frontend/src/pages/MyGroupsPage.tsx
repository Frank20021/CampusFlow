import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createGroup, listGroups } from "../api/groups";
import { GroupCard } from "../features/groups/GroupCard";
import { GroupForm } from "../features/groups/GroupForm";
import { EmptyState, Spinner } from "../components/ui/Feedback";
import { PageHeader } from "../components/ui/Overlay";
import { ApiError } from "../api/client";

export function MyGroupsPage() {
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const groupsQuery = useQuery({
    queryKey: ["groups", { mine: true }],
    queryFn: () => listGroups({ mine: true, limit: 50 }),
  });
  const createMutation = useMutation({
    mutationFn: createGroup,
    onSuccess: async () => {
      setFormError(null);
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
    onError: (error) => {
      setFormError(error instanceof ApiError ? error.message : "Unable to create group");
    },
  });

  return (
    <div className="grid gap-10 lg:grid-cols-[1fr_20rem]">
      <div>
        <PageHeader
          title="My groups"
          description="Groups you own or have joined."
        />
        {groupsQuery.isLoading ? <Spinner label="Loading your groups" /> : null}
        {groupsQuery.data && groupsQuery.data.items.length === 0 ? (
          <EmptyState
            title="You have not joined a group yet"
            body="Create one on the right, or find an existing group on the Discover page."
          />
        ) : null}
        {groupsQuery.data && groupsQuery.data.items.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2">
            {groupsQuery.data.items.map((group) => (
              <GroupCard key={group.id} group={group} />
            ))}
          </div>
        ) : null}
      </div>
      <aside>
        <h2 className="mb-3 text-sm font-semibold text-stone-900">Create a group</h2>
        <div className="rounded-lg border border-stone-200 bg-white p-4">
          <GroupForm
            submitLabel="Create group"
            busy={createMutation.isPending}
            error={formError}
            onSubmit={async (input) => {
              await createMutation.mutateAsync(input);
            }}
          />
        </div>
      </aside>
    </div>
  );
}
