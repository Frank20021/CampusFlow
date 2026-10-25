import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ResourceList } from "./ResourceList";
import type { Resource } from "../../types/api";

function makeResource(overrides: Partial<Resource> = {}): Resource {
  return {
    id: "resource-1",
    group_id: "group-1",
    title: "Lecture slides",
    url: "https://example.edu/slides.pdf",
    description: null,
    created_by: "user-1",
    created_at: new Date(2026, 10, 1).toISOString(),
    creator: { id: "user-1", first_name: "Ada", last_name: "Lovelace", email: "ada@u.edu" },
    can_delete: false,
    ...overrides,
  };
}

describe("ResourceList", () => {
  it("says so when nothing has been shared", () => {
    render(<ResourceList resources={[]} deletingId={null} onDelete={vi.fn()} />);
    expect(screen.getByText(/no links shared yet/i)).toBeInTheDocument();
  });

  it("opens links in a new tab without leaking the opener", () => {
    render(<ResourceList resources={[makeResource()]} deletingId={null} onDelete={vi.fn()} />);

    const link = screen.getByRole("link", { name: "Lecture slides" });
    expect(link).toHaveAttribute("href", "https://example.edu/slides.pdf");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("shows the destination host so the name alone is not the only signal", () => {
    render(
      <ResourceList
        resources={[makeResource({ url: "https://www.evil.example/free-answers" })]}
        deletingId={null}
        onDelete={vi.fn()}
      />,
    );

    expect(screen.getByText("evil.example")).toBeInTheDocument();
  });

  it("credits whoever shared it", () => {
    render(<ResourceList resources={[makeResource()]} deletingId={null} onDelete={vi.fn()} />);
    expect(screen.getByText(/shared by ada lovelace/i)).toBeInTheDocument();
  });

  it("offers removal only when the viewer is allowed", () => {
    render(
      <ResourceList
        resources={[
          makeResource({ id: "mine", title: "Mine", can_delete: true }),
          makeResource({ id: "theirs", title: "Theirs", can_delete: false }),
        ]}
        deletingId={null}
        onDelete={vi.fn()}
      />,
    );

    expect(screen.getAllByRole("button", { name: /^remove/i })).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Remove Mine" })).toBeInTheDocument();
  });

  it("passes the resource to the delete handler", async () => {
    const onDelete = vi.fn();
    const resource = makeResource({ can_delete: true });
    render(<ResourceList resources={[resource]} deletingId={null} onDelete={onDelete} />);

    await userEvent.click(screen.getByRole("button", { name: /remove lecture slides/i }));
    expect(onDelete).toHaveBeenCalledWith(resource);
  });
});
