import { useState, type FormEvent } from "react";
import type { GroupMember, Task, TaskPriority, TaskStatus } from "../../types/api";
import type { TaskCreateInput } from "../../api/tasks";
import { Button } from "../../components/ui/Button";
import { SelectField, TextAreaField, TextField } from "../../components/ui/Field";
import { Modal } from "../../components/ui/Overlay";
import { fromDateTimeLocal, fullName, priorityLabel, statusLabel, toDateTimeLocal } from "../../utils/format";

const STATUSES: TaskStatus[] = ["TODO", "IN_PROGRESS", "DONE"];
const PRIORITIES: TaskPriority[] = ["LOW", "MEDIUM", "HIGH"];

type TaskFormDialogProps = {
  open: boolean;
  task: Task | null;
  members: GroupMember[];
  busy?: boolean;
  error?: string | null;
  onClose: () => void;
  onSubmit: (input: TaskCreateInput) => Promise<void>;
};

export function TaskFormDialog({
  open,
  task,
  members,
  busy = false,
  error,
  onClose,
  onSubmit,
}: TaskFormDialogProps) {
  const [title, setTitle] = useState(task?.title ?? "");
  const [description, setDescription] = useState(task?.description ?? "");
  const [assignedTo, setAssignedTo] = useState(task?.assigned_to ?? "");
  const [status, setStatus] = useState<TaskStatus>(task?.status ?? "TODO");
  const [priority, setPriority] = useState<TaskPriority>(task?.priority ?? "MEDIUM");
  const [dueDate, setDueDate] = useState(toDateTimeLocal(task?.due_date ?? null));
  const [titleError, setTitleError] = useState<string | undefined>();

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) {
      setTitleError("Title is required");
      return;
    }
    setTitleError(undefined);
    await onSubmit({
      title: title.trim(),
      description: description.trim() || null,
      assigned_to: assignedTo || null,
      status,
      priority,
      due_date: fromDateTimeLocal(dueDate),
    });
  }

  return (
    <Modal
      open={open}
      title={task ? "Edit task" : "New task"}
      description={
        task ? undefined : "Tasks belong to this group and can be assigned to any member."
      }
      onClose={onClose}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        {error ? (
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900" role="alert">
            {error}
          </p>
        ) : null}
        <TextField
          label="Title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          error={titleError}
          required
          autoFocus
        />
        <TextAreaField
          label="Description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectField
            label="Assignee"
            value={assignedTo}
            onChange={(event) => setAssignedTo(event.target.value)}
          >
            <option value="">Unassigned</option>
            {members.map((member) => (
              <option key={member.user_id} value={member.user_id}>
                {fullName(member)}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Priority"
            value={priority}
            onChange={(event) => setPriority(event.target.value as TaskPriority)}
          >
            {PRIORITIES.map((value) => (
              <option key={value} value={value}>
                {priorityLabel(value)}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Status"
            value={status}
            onChange={(event) => setStatus(event.target.value as TaskStatus)}
          >
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {statusLabel(value)}
              </option>
            ))}
          </SelectField>
          <TextField
            label="Due date"
            type="datetime-local"
            value={dueDate}
            onChange={(event) => setDueDate(event.target.value)}
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            {task ? "Save changes" : "Create task"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
