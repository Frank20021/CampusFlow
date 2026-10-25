import { useEffect, useRef } from "react";
import { getStoredToken } from "../../api/client";
import type { Notification } from "../../types/api";

/**
 * Same transport as group chat: `fetch` + `ReadableStream`, not `EventSource`.
 * The JWT stays in an Authorization header, and Last-Event-ID is sent by us
 * so a dropped connection can replay what landed while we were away.
 */

type Handlers = {
  onNotification: (notification: Notification) => void;
};

const SILENCE_TIMEOUT_MS = 50_000;
const MAX_BACKOFF_MS = 30_000;

function apiBase(): string {
  return import.meta.env.VITE_API_URL ?? "http://localhost:8000";
}

function backoffDelay(attempt: number): number {
  const exponential = Math.min(1000 * 2 ** (attempt - 1), MAX_BACKOFF_MS);
  return exponential / 2 + Math.random() * (exponential / 2);
}

function parseFrame(raw: string): { id?: string; event?: string; data?: string } {
  const frame: { id?: string; event?: string; data?: string } = {};
  for (const line of raw.split("\n")) {
    if (line.startsWith(":")) continue;
    const separator = line.indexOf(":");
    if (separator === -1) continue;
    const field = line.slice(0, separator);
    const value = line.slice(separator + 1).replace(/^ /, "");
    if (field === "id") frame.id = value;
    else if (field === "event") frame.event = value;
    else if (field === "data") frame.data = (frame.data ?? "") + value;
  }
  return frame;
}

export function useNotificationStream(enabled: boolean, handlers: Handlers): void {
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;
    let attempt = 0;
    let lastEventId: string | null = null;
    let currentAbort: AbortController | null = null;

    const abortCurrent = () => currentAbort?.abort();
    const goOffline = () => abortCurrent();
    const goOnline = () => {
      attempt = 0;
      abortCurrent();
    };

    window.addEventListener("offline", goOffline);
    window.addEventListener("online", goOnline);

    const readStream = async (body: ReadableStream<Uint8Array>, abort: AbortController) => {
      const reader = body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let silenceTimer = window.setTimeout(() => abort.abort(), SILENCE_TIMEOUT_MS);

      try {
        for (;;) {
          const { done, value } = await reader.read();
          if (done || cancelled) break;

          window.clearTimeout(silenceTimer);
          silenceTimer = window.setTimeout(() => abort.abort(), SILENCE_TIMEOUT_MS);

          buffer += decoder.decode(value, { stream: true });
          let boundary = buffer.indexOf("\n\n");
          while (boundary !== -1) {
            const raw = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);
            const frame = parseFrame(raw);
            if (frame.id) lastEventId = frame.id;
            if (frame.event === "notification.created" && frame.data) {
              handlersRef.current.onNotification(JSON.parse(frame.data) as Notification);
            }
            boundary = buffer.indexOf("\n\n");
          }
        }
      } finally {
        window.clearTimeout(silenceTimer);
        reader.cancel().catch(() => undefined);
      }
    };

    const run = async () => {
      while (!cancelled) {
        if (typeof navigator !== "undefined" && navigator.onLine === false) {
          await new Promise((resolve) => window.setTimeout(resolve, 1000));
          continue;
        }

        const abort = new AbortController();
        currentAbort = abort;

        try {
          const headers: Record<string, string> = { Accept: "text/event-stream" };
          const token = getStoredToken();
          if (token) headers.Authorization = `Bearer ${token}`;
          if (lastEventId) headers["Last-Event-ID"] = lastEventId;

          const response = await fetch(`${apiBase()}/api/notifications/stream`, {
            headers,
            signal: abort.signal,
          });

          if (response.status === 401 || response.status === 403) return;
          if (!response.ok || !response.body) {
            throw new Error(`Stream failed with ${response.status}`);
          }

          attempt = 0;
          await readStream(response.body, abort);
        } catch {
          // Dropped connection; the loop retries with backoff.
        }

        if (cancelled) return;
        attempt += 1;
        await new Promise((resolve) => window.setTimeout(resolve, backoffDelay(attempt)));
      }
    };

    void run();

    return () => {
      cancelled = true;
      abortCurrent();
      window.removeEventListener("offline", goOffline);
      window.removeEventListener("online", goOnline);
    };
  }, [enabled]);
}
