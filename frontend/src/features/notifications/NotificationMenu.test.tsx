import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Notification, Paginated } from "../../types/api";
import { NotificationMenu } from "./NotificationMenu";

const items: Notification[] = [
  {
    id: "note-1",
    user_id: "user-2",
    actor_id: "user-1",
    group_id: "group-1",
    type: "task_assigned",
    title: "Task assigned to you",
    body: "Ada Lovelace assigned you “Read chapter 4” in Algorithms Night",
    href: "/app/groups/group-1/tasks",
    entity_id: "task-1",
    read_at: null,
    created_at: "2026-10-24T18:00:00Z",
    actor: { id: "user-1", first_name: "Ada", last_name: "Lovelace" },
  },
];

const page: Paginated<Notification> = { items, total: 1, limit: 20, offset: 0 };

vi.mock("../../api/notifications", () => ({
  listNotifications: vi.fn(),
  getUnreadCount: vi.fn(),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
}));

vi.mock("./useNotificationStream", () => ({
  useNotificationStream: () => undefined,
}));

import {
  getUnreadCount,
  listNotifications,
  markAllNotificationsRead,
} from "../../api/notifications";

function renderMenu() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <NotificationMenu enabled />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("NotificationMenu", () => {
  beforeEach(() => {
    vi.mocked(listNotifications).mockReset();
    vi.mocked(getUnreadCount).mockReset();
    vi.mocked(markAllNotificationsRead).mockReset();
  });

  it("shows an unread count and the latest items", async () => {
    vi.mocked(listNotifications).mockResolvedValue(page);
    vi.mocked(getUnreadCount).mockResolvedValue({ unread: 1 });

    renderMenu();
    await userEvent.click(screen.getByRole("button", { name: /notifications/i }));

    expect(await screen.findByText("Task assigned to you")).toBeInTheDocument();
    expect(screen.getByText(/Read chapter 4/)).toBeInTheDocument();
    expect(screen.getByText("1 unread")).toBeInTheDocument();
  });

  it("explains an empty inbox instead of showing a blank panel", async () => {
    vi.mocked(listNotifications).mockResolvedValue({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    });
    vi.mocked(getUnreadCount).mockResolvedValue({ unread: 0 });

    renderMenu();
    await userEvent.click(screen.getByRole("button", { name: /notifications/i }));

    expect(await screen.findByText(/nothing yet/i)).toBeInTheDocument();
    expect(screen.queryByText("Mark all as read")).not.toBeInTheDocument();
  });

  it("can mark every notification as read", async () => {
    vi.mocked(listNotifications).mockResolvedValue(page);
    vi.mocked(getUnreadCount).mockResolvedValue({ unread: 1 });
    vi.mocked(markAllNotificationsRead).mockResolvedValue({ unread: 0 });

    renderMenu();
    await userEvent.click(screen.getByRole("button", { name: /notifications/i }));
    await userEvent.click(await screen.findByRole("button", { name: /mark all as read/i }));

    await waitFor(() => expect(markAllNotificationsRead).toHaveBeenCalled());
  });

  it("closes on Escape", async () => {
    vi.mocked(listNotifications).mockResolvedValue(page);
    vi.mocked(getUnreadCount).mockResolvedValue({ unread: 1 });

    renderMenu();
    await userEvent.click(screen.getByRole("button", { name: /notifications/i }));
    expect(await screen.findByRole("dialog", { name: "Notifications" })).toBeInTheDocument();

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Notifications" })).not.toBeInTheDocument();
  });
});
