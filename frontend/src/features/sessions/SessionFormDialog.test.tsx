import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SessionFormDialog } from "./SessionFormDialog";
import type { StudySession } from "../../types/api";

function makeSession(overrides: Partial<StudySession> = {}): StudySession {
  return {
    id: "session-1",
    group_id: "group-1",
    title: "Chapter 7 review",
    description: "Bring the practice set",
    location: "Library room 4",
    start_time: new Date(2026, 10, 12, 18, 0).toISOString(),
    end_time: new Date(2026, 10, 12, 20, 0).toISOString(),
    created_by: "user-1",
    created_at: new Date(2026, 10, 1).toISOString(),
    updated_at: new Date(2026, 10, 1).toISOString(),
    creator: { id: "user-1", first_name: "Ada", last_name: "Lovelace", email: "ada@u.edu" },
    rsvp_counts: { going: 1, maybe: 0, declined: 0 },
    my_rsvp: "going",
    can_manage: true,
    ...overrides,
  };
}

const baseProps = {
  open: true,
  session: null,
  onClose: () => {},
};

describe("SessionFormDialog", () => {
  it("requires a title", async () => {
    const onSubmit = vi.fn();
    render(<SessionFormDialog {...baseProps} onSubmit={onSubmit} />);

    await userEvent.click(screen.getByRole("button", { name: "Schedule session" }));

    expect(screen.getByText("Give the session a title")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits a new session with ISO timestamps", async () => {
    const onSubmit = vi.fn();
    render(<SessionFormDialog {...baseProps} onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText("Title"), "Problem set");
    await userEvent.click(screen.getByRole("button", { name: "Schedule session" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const input = onSubmit.mock.calls[0][0];
    expect(input.title).toBe("Problem set");
    // Sent as instants, so the server never has to guess a time zone.
    expect(new Date(input.start_time).toISOString()).toBe(input.start_time);
    expect(new Date(input.end_time).getTime()).toBeGreaterThan(
      new Date(input.start_time).getTime(),
    );
  });

  it("prefills when editing an existing session", () => {
    render(<SessionFormDialog {...baseProps} session={makeSession()} onSubmit={vi.fn()} />);

    expect(screen.getByLabelText("Title")).toHaveValue("Chapter 7 review");
    expect(screen.getByLabelText("Location")).toHaveValue("Library room 4");
    expect(screen.getByLabelText("Details")).toHaveValue("Bring the practice set");
    expect(screen.getByRole("button", { name: "Save changes" })).toBeInTheDocument();
  });

  it("rejects an end time that is not after the start", async () => {
    const onSubmit = vi.fn();
    render(<SessionFormDialog {...baseProps} onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText("Title"), "Backwards");
    await userEvent.clear(screen.getByLabelText("Ends"));
    await userEvent.type(screen.getByLabelText("Ends"), "2026-11-12T09:00");
    await userEvent.clear(screen.getByLabelText("Starts"));
    await userEvent.type(screen.getByLabelText("Starts"), "2026-11-12T18:00");
    // Changing the start nudges the end along, so push it back again.
    await userEvent.clear(screen.getByLabelText("Ends"));
    await userEvent.type(screen.getByLabelText("Ends"), "2026-11-12T17:00");
    await userEvent.click(screen.getByRole("button", { name: "Schedule session" }));

    expect(screen.getByText("The end time must be after the start time")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("rejects a session longer than a day", async () => {
    const onSubmit = vi.fn();
    render(<SessionFormDialog {...baseProps} onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText("Title"), "Marathon");
    await userEvent.clear(screen.getByLabelText("Starts"));
    await userEvent.type(screen.getByLabelText("Starts"), "2026-11-12T09:00");
    await userEvent.clear(screen.getByLabelText("Ends"));
    await userEvent.type(screen.getByLabelText("Ends"), "2026-11-20T09:00");
    await userEvent.click(screen.getByRole("button", { name: "Schedule session" }));

    expect(screen.getByText(/cannot run longer than 24 hours/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("keeps the window valid by moving the end when the start moves past it", async () => {
    render(<SessionFormDialog {...baseProps} onSubmit={vi.fn()} />);

    const starts = screen.getByLabelText("Starts");
    const ends = screen.getByLabelText("Ends");
    await userEvent.clear(starts);
    await userEvent.type(starts, "2026-11-12T22:00");

    expect(new Date(String(ends.getAttribute("value") ?? "")).getTime()).toBeGreaterThan(0);
    expect((ends as HTMLInputElement).value > "2026-11-12T22:00").toBe(true);
  });

  it("surfaces a server-side rejection", () => {
    render(
      <SessionFormDialog {...baseProps} serverError="That room is taken" onSubmit={vi.fn()} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("That room is taken");
  });

  it("closes on Escape", async () => {
    const onClose = vi.fn();
    render(<SessionFormDialog {...baseProps} onClose={onClose} onSubmit={vi.fn()} />);

    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });
});
