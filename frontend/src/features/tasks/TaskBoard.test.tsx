import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TaskBoard } from "./TaskBoard";
import type { Task } from "../../types/api";

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: "task-1",
    group_id: "group-1",
    title: "Read chapter 4",
    description: null,
    assigned_to: null,
    created_by: "user-1",
    status: "TODO",
    priority: "MEDIUM",
    due_date: null,
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-09-01T10:00:00Z",
    assignee: null,
    creator: { id: "user-1", first_name: "Ada", last_name: "Lovelace", email: "ada@u.edu" },
    can_delete: true,
    ...overrides,
  };
}

const noop = () => {};

describe("TaskBoard", () => {
  it("renders one column per status with counts", () => {
    render(
      <TaskBoard
        tasks={[
          makeTask({ id: "a", title: "Todo task" }),
          makeTask({ id: "b", title: "Active task", status: "IN_PROGRESS" }),
          makeTask({ id: "c", title: "Finished task", status: "DONE" }),
        ]}
        onMove={noop}
        onEdit={noop}
        onDelete={noop}
      />,
    );

    const todo = screen.getByRole("region", { name: "To do" });
    expect(within(todo).getByText("Todo task")).toBeInTheDocument();
    expect(within(todo).getByText("1 task")).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "In progress" })).getByText("Active task"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "Done" })).getByText("Finished task"),
    ).toBeInTheDocument();
  });

  it("shows an empty message for a column with no tasks", () => {
    render(<TaskBoard tasks={[]} onMove={noop} onEdit={noop} onDelete={noop} />);
    expect(screen.getAllByText("Nothing here yet.")).toHaveLength(3);
  });

  it("moves a task through its labelled status control", async () => {
    const user = userEvent.setup();
    const onMove = vi.fn();
    const task = makeTask();
    render(<TaskBoard tasks={[task]} onMove={onMove} onEdit={noop} onDelete={noop} />);

    await user.selectOptions(
      screen.getByLabelText("Status for Read chapter 4"),
      "IN_PROGRESS",
    );
    expect(onMove).toHaveBeenCalledWith(task, "IN_PROGRESS");
  });

  it("marks a past due date as overdue unless the task is done", () => {
    render(
      <TaskBoard
        tasks={[
          makeTask({ id: "late", title: "Late task", due_date: "2020-01-01T09:00:00Z" }),
          makeTask({
            id: "shipped",
            title: "Shipped task",
            status: "DONE",
            due_date: "2020-01-01T09:00:00Z",
          }),
        ]}
        onMove={noop}
        onEdit={noop}
        onDelete={noop}
      />,
    );
    expect(screen.getByText(/overdue/)).toBeInTheDocument();
    expect(screen.getAllByText(/overdue/)).toHaveLength(1);
  });

  it("hides the delete action when the API says the user may not delete", () => {
    render(
      <TaskBoard
        tasks={[makeTask({ can_delete: false })]}
        onMove={noop}
        onEdit={noop}
        onDelete={noop}
      />,
    );
    expect(screen.queryByRole("button", { name: /^Delete/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Edit/ })).toBeInTheDocument();
  });
});
