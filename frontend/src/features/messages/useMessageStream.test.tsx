import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { useMessageStream } from "./useMessageStream";
import type { Message } from "../../types/api";

// Stubbed so these tests are about the stream protocol, not token storage.
vi.mock("../../api/client", () => ({ getStoredToken: () => "test-token" }));

/**
 * Exercises the hand-rolled SSE client: frame parsing, connection state, and
 * the reconnect handshake. These are the parts that only misbehave against a
 * real network, so they are worth pinning down here.
 */

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

const message: Message = {
  id: "message-1",
  group_id: "group-1",
  user_id: "user-1",
  content: "Hello",
  created_at: "2026-09-01T10:00:00Z",
  author: { id: "user-1", first_name: "Ada", last_name: "Lovelace" },
};

let handlers: {
  onMessage: Mock<(message: Message) => void>;
  onDeleted: Mock<(messageId: string) => void>;
};

beforeEach(() => {
  handlers = {
    onMessage: vi.fn<(message: Message) => void>(),
    onDeleted: vi.fn<(messageId: string) => void>(),
  };
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useMessageStream", () => {
  it("reports a live connection and delivers created messages", async () => {
    const { body, handle } = makeStream();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, body } as unknown as Response),
    );

    const { result } = renderHook(() => useMessageStream("group-1", handlers));

    await waitFor(() => expect(result.current).toBe("live"));

    handle.push(frame("ready", { group_id: "group-1" }));
    handle.push(frame("message.created", message, message.id));

    await waitFor(() => expect(handlers.onMessage).toHaveBeenCalledWith(message));
  });

  it("reassembles frames split across network chunks", async () => {
    const { body, handle } = makeStream();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, body } as unknown as Response),
    );

    renderHook(() => useMessageStream("group-1", handlers));
    await waitFor(() => expect(fetch).toHaveBeenCalled());

    const whole = frame("message.created", message, message.id);
    handle.push(whole.slice(0, 12));
    handle.push(whole.slice(12));

    await waitFor(() => expect(handlers.onMessage).toHaveBeenCalledWith(message));
  });

  it("forwards deletions", async () => {
    const { body, handle } = makeStream();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, body } as unknown as Response),
    );

    renderHook(() => useMessageStream("group-1", handlers));
    await waitFor(() => expect(fetch).toHaveBeenCalled());

    handle.push(frame("message.deleted", { id: "message-9", group_id: "group-1" }));

    await waitFor(() => expect(handlers.onDeleted).toHaveBeenCalledWith("message-9"));
  });

  it("ignores heartbeats", async () => {
    const { body, handle } = makeStream();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, body } as unknown as Response),
    );

    const { result } = renderHook(() => useMessageStream("group-1", handlers));
    await waitFor(() => expect(result.current).toBe("live"));

    handle.push(frame("ping", {}));

    await waitFor(() => expect(result.current).toBe("live"));
    expect(handlers.onMessage).not.toHaveBeenCalled();
  });

  it("sends the bearer token in a header rather than the URL", async () => {
    const { body } = makeStream();
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, status: 200, body } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    renderHook(() => useMessageStream("group-1", handlers));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).not.toContain("test-token");
    expect(init.headers.Authorization).toBe("Bearer test-token");
  });

  it("stops retrying when the group is off limits", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: false, status: 403, body: null } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useMessageStream("group-1", handlers));

    await waitFor(() => expect(result.current).toBe("denied"));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("resumes from the last seen event after a dropped connection", async () => {
    const first = makeStream();
    const second = makeStream();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, status: 200, body: first.body } as unknown as Response)
      .mockResolvedValue({ ok: true, status: 200, body: second.body } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useMessageStream("group-1", handlers));
    await waitFor(() => expect(result.current).toBe("live"));

    first.handle.push(frame("message.created", message, message.id));
    await waitFor(() => expect(handlers.onMessage).toHaveBeenCalled());

    first.handle.close();
    await waitFor(() => expect(result.current).toBe("reconnecting"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2), { timeout: 4000 });
    expect(fetchMock.mock.calls[1][1].headers["Last-Event-ID"]).toBe(message.id);
  });

  it("goes quiet when the browser reports it is offline", async () => {
    const { body } = makeStream();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, body } as unknown as Response),
    );

    const { result } = renderHook(() => useMessageStream("group-1", handlers));
    await waitFor(() => expect(result.current).toBe("live"));

    vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    window.dispatchEvent(new Event("offline"));

    await waitFor(() => expect(result.current).toBe("offline"));
  });
});
