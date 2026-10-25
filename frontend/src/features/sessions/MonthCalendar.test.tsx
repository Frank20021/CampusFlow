import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MonthCalendar } from "./MonthCalendar";
import type { StudySession } from "../../types/api";

function makeSession(overrides: Partial<StudySession> = {}): StudySession {
  return {
    id: "session-1",
    group_id: "group-1",
    title: "Chapter 7 review",
    description: null,
    location: null,
    start_time: new Date(2026, 10, 12, 18, 0).toISOString(),
    end_time: new Date(2026, 10, 12, 20, 0).toISOString(),
    created_by: "user-1",
    created_at: new Date(2026, 10, 1).toISOString(),
    updated_at: new Date(2026, 10, 1).toISOString(),
    creator: { id: "user-1", first_name: "Ada", last_name: "Lovelace", email: "ada@u.edu" },
    rsvp_counts: { going: 1, maybe: 0, declined: 0 },
    my_rsvp: null,
    can_manage: false,
    ...overrides,
  };
}

const november = new Date(2026, 10, 1);

describe("MonthCalendar", () => {
  it("renders a table with a weekday header row", () => {
    render(
      <MonthCalendar month={november} sessions={[]} onMonthChange={vi.fn()} onSelect={vi.fn()} />,
    );

    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("columnheader")).toHaveLength(7);
  });

  it("names the month for screen readers and sighted users", () => {
    render(
      <MonthCalendar month={november} sessions={[]} onMonthChange={vi.fn()} onSelect={vi.fn()} />,
    );

    expect(screen.getByRole("table", { name: /november 2026/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3 })).toHaveTextContent("November 2026");
  });

  it("places a session on its day", () => {
    render(
      <MonthCalendar
        month={november}
        sessions={[makeSession()]}
        onMonthChange={vi.fn()}
        onSelect={vi.fn()}
      />,
    );

    const entry = screen.getByRole("button", { name: /chapter 7 review/i });
    const cell = entry.closest("td");
    expect(within(cell!).getByText("12")).toBeInTheDocument();
  });

  it("shows several sessions on the same day", () => {
    render(
      <MonthCalendar
        month={november}
        sessions={[
          makeSession({ id: "a", title: "Morning" }),
          makeSession({
            id: "b",
            title: "Evening",
            start_time: new Date(2026, 10, 12, 20, 0).toISOString(),
            end_time: new Date(2026, 10, 12, 21, 0).toISOString(),
          }),
        ]}
        onMonthChange={vi.fn()}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /morning/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /evening/i })).toBeInTheDocument();
  });

  it("reports the session a user picks", async () => {
    const onSelect = vi.fn();
    const session = makeSession();
    render(
      <MonthCalendar
        month={november}
        sessions={[session]}
        onMonthChange={vi.fn()}
        onSelect={onSelect}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /chapter 7 review/i }));
    expect(onSelect).toHaveBeenCalledWith(session);
  });

  it("steps between months", async () => {
    const onMonthChange = vi.fn();
    render(
      <MonthCalendar
        month={november}
        sessions={[]}
        onMonthChange={onMonthChange}
        onSelect={vi.fn()}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Next month" }));
    expect(onMonthChange.mock.calls[0][0].getMonth()).toBe(11);

    await userEvent.click(screen.getByRole("button", { name: "Previous month" }));
    expect(onMonthChange.mock.calls[1][0].getMonth()).toBe(9);
  });

  it("renders an empty month without sessions", () => {
    render(
      <MonthCalendar month={november} sessions={[]} onMonthChange={vi.fn()} onSelect={vi.fn()} />,
    );

    const table = screen.getByRole("table");
    expect(within(table).queryAllByRole("button")).toHaveLength(0);
  });
});
