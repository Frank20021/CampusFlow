import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TaskFormDialog } from "./TaskFormDialog";
import type { GroupMember, Task } from "../../types/api";

const members: GroupMember[] = [
  {
    user_id: "user-2",
    first_name: "Alan",
    last_name: "Turing",
    email: "alan@u.edu",
    university: null,
    major: null,
    role: "member",
    joined_at: "2026-09-01T10:00:00Z",
  },
];

const existingTask: Task = {
  id: "task-1",
  group_id: "group-1",
  title: "Read chapter 4",
  description: "Sections 4.1 to 4.3",
  assigned_to: "user-2",
  created_by: "user-1",
  status: "IN_PROGRESS",
  priority: "HIGH",
  due_date: null,
  created_at: "2026-09-01T10:00:00Z",
  updated_at: "2026-09-01T10:00:00Z",
  assignee: null,
  creator: null,
  can_delete: true,
};

describe("TaskFormDialog", () => {
  it("requires a title before submitting", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(
      <TaskFormDialog
        open
        task={null}
        members={members}
        onClose={() => {}}
        onSubmit={onSubmit}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Create task" }));
    expect(await screen.findByText("Title is required")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits a new task with the chosen assignee and priority", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <TaskFormDialog
        open
        task={null}
        members={members}
        onClose={() => {}}
        onSubmit={onSubmit}
      />,
    );

    await user.type(screen.getByLabelText("Title"), "Finish problem set");
    await user.selectOptions(screen.getByLabelText("Assignee"), "user-2");
    await user.selectOptions(screen.getByLabelText("Priority"), "HIGH");
    await user.click(screen.getByRole("button", { name: "Create task" }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Finish problem set",
        assigned_to: "user-2",
        priority: "HIGH",
        status: "TODO",
        due_date: null,
      }),
    );
  });

  it("prefills fields when editing an existing task", () => {
    render(
      <TaskFormDialog
        open
        task={existingTask}
        members={members}
        onClose={() => {}}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByRole("dialog", { name: "Edit task" })).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toHaveValue("Read chapter 4");
    expect(screen.getByLabelText("Status")).toHaveValue("IN_PROGRESS");
    expect(screen.getByLabelText("Priority")).toHaveValue("HIGH");
    expect(screen.getByLabelText("Assignee")).toHaveValue("user-2");
  });

  it("closes on Escape", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <TaskFormDialog open task={null} members={members} onClose={onClose} onSubmit={vi.fn()} />,
    );
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });
});
