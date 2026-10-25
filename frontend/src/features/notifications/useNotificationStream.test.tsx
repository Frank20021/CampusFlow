import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import type { Notification } from "../../types/api";
import { useNotificationStream } from "./useNotificationStream";

vi.mock("../../api/client", () => ({ getStoredToken: () => "test-token" }));

type StreamHandle = {
  push: (chunk: string) => void;
  close: () => void;
};

function makeStream(): { body: ReadableStream<Uint8Array>; handle: StreamHandle } {
  const encoder = new TextEncoder();
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({
    start(streamController) {
      controller = streamController;
    },
  });
  return {
    body,
    handle: {
      push: (chunk: string) => controller.enqueue(encoder.encode(chunk)),
      close: () => controller.close(),
    },
  };
}

function frame(event: string, data: unknown, id?: string): string {
  const lines = id ? [`id: ${id}`] : [];
  lines.push(`event: ${event}`, `data: ${JSON.stringify(data)}`);
  return `${lines.join("\n")}\n\n`;
}

const notification: Notification = {
  id: "note-1",
  user_id: "user-2",
  actor_id: "user-1",
  group_id: "group-1",
  type: "task_assigned",
  title: "Task assigned to you",
  body: "Ada assigned you a task",
  href: "/app/groups/group-1/tasks",
  entity_id: "task-1",
  read_at: null,
  created_at: "2026-10-24T18:00:00Z",
  actor: { id: "user-1", first_name: "Ada", last_name: "Lovelace" },
};

let onNotification: Mock<(item: Notification) => void>;

beforeEach(() => {
  onNotification = vi.fn<(item: Notification) => void>();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useNotificationStream", () => {
  it("delivers created notifications", async () => {
    const { body, handle } = makeStream();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, body } as unknown as Response),
    );

    renderHook(() => useNotificationStream(true, { onNotification }));
    await waitFor(() => expect(fetch).toHaveBeenCalled());

    handle.push(frame("notification.created", notification, notification.id));
    await waitFor(() => expect(onNotification).toHaveBeenCalledWith(notification));
  });

  it("reassembles frames split across chunks", async () => {
    const { body, handle } = makeStream();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, body } as unknown as Response),
    );

    renderHook(() => useNotificationStream(true, { onNotification }));
    await waitFor(() => expect(fetch).toHaveBeenCalled());

    const whole = frame("notification.created", notification, notification.id);
    handle.push(whole.slice(0, 18));
    handle.push(whole.slice(18));

    await waitFor(() => expect(onNotification).toHaveBeenCalledWith(notification));
  });

  it("sends the bearer token in a header", async () => {
    const { body } = makeStream();
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, status: 200, body } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    renderHook(() => useNotificationStream(true, { onNotification }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/notifications/stream");
    expect(url).not.toContain("test-token");
    expect(init.headers.Authorization).toBe("Bearer test-token");
  });

  it("does not connect when disabled", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderHook(() => useNotificationStream(false, { onNotification }));
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("resumes from the last seen event after a drop", async () => {
    const first = makeStream();
    const second = makeStream();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, status: 200, body: first.body } as unknown as Response)
      .mockResolvedValue({ ok: true, status: 200, body: second.body } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    renderHook(() => useNotificationStream(true, { onNotification }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    first.handle.push(frame("notification.created", notification, notification.id));
    await waitFor(() => expect(onNotification).toHaveBeenCalled());
    first.handle.close();

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2), { timeout: 4000 });
    expect(fetchMock.mock.calls[1][1].headers["Last-Event-ID"]).toBe(notification.id);
  });
});
