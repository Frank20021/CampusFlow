import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { joinGroup, listGroups } from "../api/groups";
import { GroupCard } from "../features/groups/GroupCard";
import { EmptyState, Spinner } from "../components/ui/Feedback";
import { PageHeader } from "../components/ui/Overlay";
import { TextField } from "../components/ui/Field";
import { Button } from "../components/ui/Button";
import { ApiError } from "../api/client";

export function DiscoverGroupsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [joinError, setJoinError] = useState<string | null>(null);

  const groupsQuery = useQuery({
    queryKey: ["groups", { mine: false, search: submitted }],
    queryFn: () => listGroups({ search: submitted || undefined, limit: 50 }),
  });

  const joinMutation = useMutation({
    mutationFn: joinGroup,
    onSuccess: async () => {
      setJoinError(null);
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
    onError: (error) => {
      setJoinError(error instanceof ApiError ? error.message : "Unable to join group");
    },
  });

  function onSearch(event: FormEvent) {
    event.preventDefault();
    setSubmitted(search.trim());
  }

  return (
    <div>
      <PageHeader
        title="Discover groups"
        description="Browse open study groups. Joining is immediate in Phase 1."
      />
      <form onSubmit={onSearch} className="mb-6 flex max-w-xl items-end gap-3">
        <div className="flex-1">
          <TextField
            label="Search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Name, course code, or description"
          />
        </div>
        <Button type="submit" variant="secondary">
          Search
        </Button>
      </form>
      {joinError ? (
        <p className="mb-4 text-sm text-red-800" role="alert">
          {joinError}
        </p>
      ) : null}
      {groupsQuery.isLoading ? <Spinner label="Loading groups" /> : null}
      {groupsQuery.data && groupsQuery.data.items.length === 0 ? (
        <EmptyState title="No groups found" body="Try a different search, or create a group of your own." />
      ) : null}
      {groupsQuery.data && groupsQuery.data.items.length > 0 ? (
        <ul className="grid gap-4 sm:grid-cols-2">
          {groupsQuery.data.items.map((group) => (
            <li key={group.id} className="flex flex-col">
              <GroupCard group={group} />
              {!group.my_role ? (
                <div className="mt-2">
                  <Button
                    size="sm"
                    onClick={() => joinMutation.mutate(group.id)}
                    loading={joinMutation.isPending && joinMutation.variables === group.id}
                  >
                    Join group
                  </Button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
