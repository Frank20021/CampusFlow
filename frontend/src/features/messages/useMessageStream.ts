import { useEffect, useRef, useState } from "react";
import { getStoredToken } from "../../api/client";
import type { Message } from "../../types/api";

/**
 * Consumes the group SSE stream with `fetch` rather than `EventSource`.
 *
 * `EventSource` cannot set request headers, so using it would mean putting the
 * JWT in the query string, where it lands in server logs, proxy logs and
 * browser history. Reading the response body as a stream keeps the bearer
 * token in an `Authorization` header, and lets us send `Last-Event-ID`
 * ourselves so a reconnect replays whatever was missed.
 *
 * The cost is that reconnection and backoff are ours to implement, which is
 * what most of this file is.
 */

export type ConnectionState =
  | "connecting"
  | "live"
  | "reconnecting"
  | "offline"
  | "denied";

type Handlers = {
  onMessage: (message: Message) => void;
  onDeleted: (messageId: string) => void;
};

// Comfortably longer than two server heartbeats (20s each). A TCP connection
// can stay "open" long after the network has gone away — silence is the only
// signal we get, so it has to be treated as a dead connection.
const SILENCE_TIMEOUT_MS = 50_000;
const MAX_BACKOFF_MS = 30_000;

function apiBase(): string {
  return import.meta.env.VITE_API_URL ?? "http://localhost:8000";
}

function backoffDelay(attempt: number): number {
  const exponential = Math.min(1000 * 2 ** (attempt - 1), MAX_BACKOFF_MS);
  // Jitter keeps every open tab from retrying in lockstep after an outage.
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

export function useMessageStream(groupId: string | undefined, handlers: Handlers): ConnectionState {
  const [state, setState] = useState<ConnectionState>("connecting");

  // Held in a ref so a new render does not tear down a healthy connection.
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    if (!groupId) return;

    let cancelled = false;
    let attempt = 0;
    let lastEventId: string | null = null;
    let currentAbort: AbortController | null = null;

    const abortCurrent = () => currentAbort?.abort();

    const goOffline = () => {
      if (cancelled) return;
      setState("offline");
      abortCurrent();
    };
    const goOnline = () => {
      if (cancelled) return;
      // Retry immediately instead of waiting out the backoff: the user just
      // watched their wifi icon come back and expects the chat to follow.
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

            if (frame.event === "message.created" && frame.data) {
              handlersRef.current.onMessage(JSON.parse(frame.data) as Message);
            } else if (frame.event === "message.deleted" && frame.data) {
              handlersRef.current.onDeleted((JSON.parse(frame.data) as { id: string }).id);
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
          setState("offline");
          await new Promise((resolve) => window.setTimeout(resolve, 1000));
          continue;
        }

        const abort = new AbortController();
        currentAbort = abort;
        setState(attempt === 0 ? "connecting" : "reconnecting");

        try {
          const headers: Record<string, string> = { Accept: "text/event-stream" };
          const token = getStoredToken();
          if (token) headers.Authorization = `Bearer ${token}`;
          if (lastEventId) headers["Last-Event-ID"] = lastEventId;

          const response = await fetch(`${apiBase()}/api/groups/${groupId}/stream`, {
            headers,
            signal: abort.signal,
          });

          if (response.status === 401 || response.status === 403 || response.status === 404) {
            // Retrying cannot fix "you are not a member" — stop and say so.
            if (!cancelled) setState("denied");
            return;
          }
          if (!response.ok || !response.body) {
            throw new Error(`Stream failed with ${response.status}`);
          }

          if (!cancelled) {
            setState("live");
            attempt = 0;
          }
          await readStream(response.body, abort);
        } catch {
          // Any failure here is a dropped connection; the loop retries.
        }

        if (cancelled) return;
        setState("reconnecting");
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
  }, [groupId]);

  return state;
}
