import type { Task, TaskStatus } from "../../types/api";
import { statusLabel } from "../../utils/format";
import { TaskCard } from "./TaskCard";

const COLUMNS: TaskStatus[] = ["TODO", "IN_PROGRESS", "DONE"];

type TaskBoardProps = {
  tasks: Task[];
  busyTaskId?: string | null;
  onMove: (task: Task, status: TaskStatus) => void;
  onEdit: (task: Task) => void;
  onDelete: (task: Task) => void;
};

/**
 * Presentational Kanban board.
 *
 * Chosen: columns rendered from task status, with movement driven by a
 * per-card status select. Alternative: pointer drag-and-drop (dnd-kit).
 * Tradeoff: dragging feels better with a mouse, but it needs a parallel
 * keyboard implementation and live-region announcements to stay accessible.
 * A select is usable by keyboard, touch, and screen readers on day one.
 *
 * Data fetching and mutations live in TasksPage so this component can be
 * rendered in tests with plain props.
 */
export function TaskBoard({ tasks, busyTaskId, onMove, onEdit, onDelete }: TaskBoardProps) {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {COLUMNS.map((status) => {
        const columnTasks = tasks.filter((task) => task.status === status);
        const headingId = `column-${status}`;
        return (
          <section
            key={status}
            aria-labelledby={headingId}
            className="rounded-lg border border-stone-200 bg-stone-50/60 p-3"
          >
            <div className="mb-3 flex items-baseline justify-between">
              <h3 id={headingId} className="text-sm font-semibold text-stone-900">
                {statusLabel(status)}
              </h3>
              <span className="text-xs text-stone-500">
                {columnTasks.length} {columnTasks.length === 1 ? "task" : "tasks"}
              </span>
            </div>
            {columnTasks.length === 0 ? (
              <p className="rounded-md border border-dashed border-stone-300 px-3 py-6 text-center text-xs text-stone-500">
                Nothing here yet.
              </p>
            ) : (
              <ul className="flex flex-col gap-3">
                {columnTasks.map((task) => (
                  <li key={task.id}>
                    <TaskCard
                      task={task}
                      busy={busyTaskId === task.id}
                      onMove={onMove}
                      onEdit={onEdit}
                      onDelete={onDelete}
                    />
                  </li>
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}
