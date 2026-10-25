import { useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../api/client";
import { getGroup, listMembers } from "../api/groups";
import { createTask, deleteTask, listTasks, updateTask, type TaskCreateInput } from "../api/tasks";
import { useAuth } from "../features/auth/AuthContext";
import { TaskBoard } from "../features/tasks/TaskBoard";
import { TaskFormDialog } from "../features/tasks/TaskFormDialog";
import { Alert, EmptyState, Spinner } from "../components/ui/Feedback";
import { Button } from "../components/ui/Button";
import { ConfirmDialog, PageHeader } from "../components/ui/Overlay";
import { statusLabel } from "../utils/format";
import type { Paginated, Task, TaskStatus } from "../types/api";

export function TasksPage() {
  const { groupId = "" } = useParams();
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [mineOnly, setMineOnly] = useState(false);
  const [dialogTask, setDialogTask] = useState<Task | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<Task | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");

  const assignedTo = mineOnly ? user?.id : undefined;
  const tasksKey = ["tasks", groupId, assignedTo ?? "all"] as const;

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
  const tasksQuery = useQuery({
    queryKey: tasksKey,
    queryFn: () => listTasks(groupId, { assignedTo }),
    enabled: Boolean(groupId),
  });

  async function refreshTasks() {
    await queryClient.invalidateQueries({ queryKey: ["tasks", groupId] });
  }

  /**
   * Moving a card writes to the cache before the request resolves, then
   * rolls back if the API rejects it. Without this the card visibly jumps
   * back to its old column while the request is in flight.
   */
  const moveMutation = useMutation({
    mutationFn: ({ task, status }: { task: Task; status: TaskStatus }) =>
      updateTask(task.id, { status }),
    onMutate: async ({ task, status }) => {
      await queryClient.cancelQueries({ queryKey: tasksKey });
      const previous = queryClient.getQueryData<Paginated<Task>>(tasksKey);
      queryClient.setQueryData<Paginated<Task>>(tasksKey, (current) =>
        current
          ? {
              ...current,
              items: current.items.map((item) =>
                item.id === task.id ? { ...item, status } : item,
              ),
            }
          : current,
      );
      setAnnouncement(`${task.title} moved to ${statusLabel(status)}`);
      return { previous };
    },
    onError: (error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(tasksKey, context.previous);
      setAnnouncement("");
      setActionError(error instanceof ApiError ? error.message : "Unable to move task");
    },
    onSettled: refreshTasks,
  });

  const saveMutation = useMutation({
    mutationFn: (input: TaskCreateInput) =>
      dialogTask ? updateTask(dialogTask.id, input) : createTask(groupId, input),
    onSuccess: async () => {
      setDialogOpen(false);
      setDialogTask(null);
      setFormError(null);
      await refreshTasks();
    },
    onError: (error) => {
      setFormError(error instanceof ApiError ? error.message : "Unable to save task");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (task: Task) => deleteTask(task.id),
    onSuccess: async () => {
      setPendingDelete(null);
      await refreshTasks();
    },
    onError: (error) => {
      setPendingDelete(null);
      setActionError(error instanceof ApiError ? error.message : "Unable to delete task");
    },
  });

  if (!groupId) return <Navigate to="/app/groups" replace />;
  if (groupQuery.isLoading || tasksQuery.isLoading) return <Spinner label="Loading tasks" />;

  const forbidden =
    (tasksQuery.error instanceof ApiError && tasksQuery.error.status === 403) ||
    (groupQuery.error instanceof ApiError && groupQuery.error.status === 403);
  if (forbidden) {
    return (
      <EmptyState
        title="This board is for group members"
        body="Join this group to see and manage its tasks."
        action={
          <Link to={`/app/groups/${groupId}`} className="text-sm font-medium text-teal-800 hover:underline">
            Back to group
          </Link>
        }
      />
    );
  }
  if (!tasksQuery.data || !groupQuery.data) return <Alert>Unable to load this board.</Alert>;

  const tasks = tasksQuery.data.items;

  return (
    <div>
      <PageHeader
        title={`${groupQuery.data.name} tasks`}
        description="Move a task with its status control. Any member can add or edit tasks."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link
              to={`/app/groups/${groupId}`}
              className="inline-flex h-10 items-center rounded-md border border-stone-300 bg-white px-4 text-sm font-medium hover:bg-stone-50"
            >
              Back to group
            </Link>
            <Button
              onClick={() => {
                setDialogTask(null);
                setFormError(null);
                setDialogOpen(true);
              }}
            >
              New task
            </Button>
          </div>
        }
      />

      {actionError ? <Alert>{actionError}</Alert> : null}

      <div className="mb-4 flex items-center gap-2">
        <input
          id="mine-only"
          type="checkbox"
          className="h-4 w-4 rounded border-stone-300 accent-teal-800"
          checked={mineOnly}
          onChange={(event) => setMineOnly(event.target.checked)}
        />
        <label htmlFor="mine-only" className="text-sm text-stone-700">
          Only tasks assigned to me
        </label>
      </div>

      {/* Screen readers hear column moves that are otherwise purely visual. */}
      <p aria-live="polite" className="sr-only">
        {announcement}
      </p>

      {tasks.length === 0 ? (
        <EmptyState
          title={mineOnly ? "Nothing assigned to you" : "No tasks yet"}
          body={
            mineOnly
              ? "Clear the filter to see the whole board."
              : "Add the first task for this group — a reading, a problem set, or a deadline."
          }
        />
      ) : (
        <TaskBoard
          tasks={tasks}
          busyTaskId={moveMutation.isPending ? moveMutation.variables?.task.id : null}
          onMove={(task, status) => {
            setActionError(null);
            moveMutation.mutate({ task, status });
          }}
          onEdit={(task) => {
            setDialogTask(task);
            setFormError(null);
            setDialogOpen(true);
          }}
          onDelete={(task) => setPendingDelete(task)}
        />
      )}

      {dialogOpen ? (
        <TaskFormDialog
          key={dialogTask?.id ?? "new"}
          open
          task={dialogTask}
          members={membersQuery.data ?? []}
          busy={saveMutation.isPending}
          error={formError}
          onClose={() => {
            setDialogOpen(false);
            setDialogTask(null);
          }}
          onSubmit={async (input) => {
            await saveMutation.mutateAsync(input).catch(() => undefined);
          }}
        />
      ) : null}

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete this task?"
        body={pendingDelete ? `"${pendingDelete.title}" will be removed for everyone.` : ""}
        confirmLabel="Delete task"
        danger
        busy={deleteMutation.isPending}
        onClose={() => setPendingDelete(null)}
        onConfirm={() => {
          if (pendingDelete) deleteMutation.mutate(pendingDelete);
        }}
      />
    </div>
  );
}
