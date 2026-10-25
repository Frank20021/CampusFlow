import type { Task, TaskStatus } from "../../types/api";
import { Button } from "../../components/ui/Button";
import { cn, formatDueDate, fullName, isOverdue, priorityLabel, statusLabel } from "../../utils/format";

const STATUSES: TaskStatus[] = ["TODO", "IN_PROGRESS", "DONE"];

const priorityStyles: Record<Task["priority"], string> = {
  HIGH: "bg-red-50 text-red-900 border-red-200",
  MEDIUM: "bg-stone-100 text-stone-700 border-stone-200",
  LOW: "bg-stone-50 text-stone-600 border-stone-200",
};

type TaskCardProps = {
  task: Task;
  busy?: boolean;
  onMove: (task: Task, status: TaskStatus) => void;
  onEdit: (task: Task) => void;
  onDelete: (task: Task) => void;
};

export function TaskCard({ task, busy = false, onMove, onEdit, onDelete }: TaskCardProps) {
  const overdue = isOverdue(task.due_date, task.status);

  return (
    <article
      className={cn(
        "rounded-lg border border-stone-200 bg-white p-3",
        busy && "opacity-60",
      )}
      aria-busy={busy || undefined}
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-sm font-medium leading-5 text-stone-900">{task.title}</h4>
        <span
          className={cn(
            "shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium",
            priorityStyles[task.priority],
          )}
        >
          {priorityLabel(task.priority)}
        </span>
      </div>

      {task.description ? (
        <p className="mt-1.5 line-clamp-2 text-xs leading-5 text-stone-600">{task.description}</p>
      ) : null}

      <dl className="mt-2.5 space-y-1 text-xs">
        <div className="flex gap-1.5">
          <dt className="text-stone-500">Assignee</dt>
          <dd className="text-stone-800">
            {task.assignee ? fullName(task.assignee) : "Unassigned"}
          </dd>
        </div>
        {task.due_date ? (
          <div className="flex gap-1.5">
            <dt className="text-stone-500">Due</dt>
            <dd className={cn(overdue ? "font-medium text-red-800" : "text-stone-800")}>
              {formatDueDate(task.due_date)}
              {overdue ? " (overdue)" : ""}
            </dd>
          </div>
        ) : null}
      </dl>

      <div className="mt-3 flex items-center gap-2">
        {/* A labelled select is the keyboard- and screen-reader-friendly way
            to move a card between columns. See TaskBoard for the tradeoff
            against pointer drag-and-drop. */}
        <label className="sr-only" htmlFor={`status-${task.id}`}>
          Status for {task.title}
        </label>
        <select
          id={`status-${task.id}`}
          className="h-8 flex-1 rounded-md border border-stone-300 bg-white px-2 text-xs text-stone-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-800"
          value={task.status}
          disabled={busy}
          onChange={(event) => onMove(task, event.target.value as TaskStatus)}
        >
          {STATUSES.map((status) => (
            <option key={status} value={status}>
              {statusLabel(status)}
            </option>
          ))}
        </select>
        <Button variant="ghost" size="sm" onClick={() => onEdit(task)}>
          Edit
          <span className="sr-only"> task {task.title}</span>
        </Button>
        {task.can_delete ? (
          <Button variant="ghost" size="sm" onClick={() => onDelete(task)}>
            Delete
            <span className="sr-only"> task {task.title}</span>
          </Button>
        ) : null}
      </div>
    </article>
  );
}
