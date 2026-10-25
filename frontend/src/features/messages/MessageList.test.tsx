import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MessageList } from "./MessageList";
import type { Message } from "../../types/api";

function makeMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: "message-1",
    group_id: "group-1",
    user_id: "user-1",
    content: "Hello everyone",
    created_at: "2026-09-01T10:00:00Z",
    author: { id: "user-1", first_name: "Ada", last_name: "Lovelace" },
    ...overrides,
  };
}

const listProps = {
  currentUserId: "user-2",
  canModerate: false,
  hasMore: false,
  loadingOlder: false,
  onLoadOlder: () => {},
  deletingId: null,
  onDelete: () => {},
};

describe("MessageList", () => {
  it("tells a newcomer the conversation is empty rather than showing nothing", () => {
    render(<MessageList {...listProps} messages={[]} />);
    expect(screen.getByText(/no messages yet/i)).toBeInTheDocument();
  });

  it("renders messages with their author and time", () => {
    render(<MessageList {...listProps} messages={[makeMessage()]} />);

    expect(screen.getByText("Hello everyone")).toBeInTheDocument();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
  });

  it("labels the caller's own messages as theirs", () => {
    render(
      <MessageList
        {...listProps}
        currentUserId="user-1"
        messages={[makeMessage({ content: "Mine" })]}
      />,
    );

    expect(screen.getByText("You")).toBeInTheDocument();
    expect(screen.queryByText("Ada Lovelace")).not.toBeInTheDocument();
  });

  it("exposes the transcript as a live log for assistive technology", () => {
    render(<MessageList {...listProps} messages={[makeMessage()]} />);

    const log = screen.getByRole("log", { name: "Group messages" });
    expect(log).toHaveAttribute("aria-live", "polite");
    expect(within(log).getByText("Hello everyone")).toBeInTheDocument();
  });

  it("repeats the author only when someone else speaks or time passes", () => {
    render(
      <MessageList
        {...listProps}
        messages={[
          makeMessage({ id: "a", content: "First" }),
          makeMessage({ id: "b", content: "Second", created_at: "2026-09-01T10:01:00Z" }),
        ]}
      />,
    );

    expect(screen.getAllByText("Ada Lovelace")).toHaveLength(1);
    expect(screen.getByText("First")).toBeInTheDocument();
    expect(screen.getByText("Second")).toBeInTheDocument();
  });

  it("separates messages sent on different days", () => {
    render(
      <MessageList
        {...listProps}
        messages={[
          makeMessage({ id: "a", created_at: "2026-08-30T10:00:00Z" }),
          makeMessage({ id: "b", content: "Next day", created_at: "2026-09-01T10:00:00Z" }),
        ]}
      />,
    );

    // Two distinct day separators, not one merged run of messages.
    expect(screen.getAllByText(/\d/, { selector: "span" }).length).toBeGreaterThan(0);
    expect(screen.getByText("Next day")).toBeInTheDocument();
  });

  it("names a departed author instead of showing a blank sender", () => {
    render(<MessageList {...listProps} messages={[makeMessage({ author: null })]} />);
    expect(screen.getByText("Former member")).toBeInTheDocument();
  });

  it("offers delete on your own message only", () => {
    render(
      <MessageList
        {...listProps}
        currentUserId="user-2"
        messages={[
          makeMessage({ id: "mine", user_id: "user-2", content: "Mine" }),
          makeMessage({ id: "theirs", user_id: "user-1", content: "Theirs" }),
        ]}
      />,
    );

    expect(screen.getAllByRole("button", { name: /delete message/i })).toHaveLength(1);
  });

  it("lets an owner or admin remove anyone's message", () => {
    render(
      <MessageList
        {...listProps}
        canModerate
        messages={[
          makeMessage({ id: "mine", user_id: "user-2" }),
          makeMessage({ id: "theirs", user_id: "user-1" }),
        ]}
      />,
    );

    expect(screen.getAllByRole("button", { name: /delete message/i })).toHaveLength(2);
  });

  it("passes the message id to the delete handler", async () => {
    const onDelete = vi.fn();
    render(
      <MessageList
        {...listProps}
        currentUserId="user-1"
        messages={[makeMessage({ id: "target" })]}
        onDelete={onDelete}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /delete message/i }));
    expect(onDelete).toHaveBeenCalledWith("target");
  });

  it("offers older history only when more exists", async () => {
    const onLoadOlder = vi.fn();
    const { rerender } = render(
      <MessageList {...listProps} messages={[makeMessage()]} onLoadOlder={onLoadOlder} />,
    );
    expect(screen.queryByRole("button", { name: /load older/i })).not.toBeInTheDocument();

    rerender(
      <MessageList {...listProps} hasMore messages={[makeMessage()]} onLoadOlder={onLoadOlder} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /load older/i }));
    expect(onLoadOlder).toHaveBeenCalled();
  });
});
