import { cn } from "../../utils/format";
import type { ConnectionState } from "./useMessageStream";

const COPY: Record<ConnectionState, { label: string; hint: string; dot: string }> = {
  connecting: {
    label: "Connecting…",
    hint: "Opening the live connection.",
    dot: "bg-amber-500",
  },
  live: {
    label: "Live",
    hint: "New messages appear as they are sent.",
    dot: "bg-emerald-600",
  },
  reconnecting: {
    label: "Reconnecting…",
    hint: "Messages sent while you are away will appear once reconnected.",
    dot: "bg-amber-500",
  },
  offline: {
    label: "Offline",
    hint: "You appear to be offline. Reconnecting automatically.",
    dot: "bg-stone-400",
  },
  denied: {
    label: "Not connected",
    hint: "Live updates are unavailable. Reload the page to try again.",
    dot: "bg-red-600",
  },
};

/**
 * Chat that has silently stopped updating looks identical to chat where
 * nobody is talking, so connection state is shown rather than inferred.
 */
export function ConnectionStatus({ state }: { state: ConnectionState }) {
  const copy = COPY[state];
  return (
    <p
      className="flex items-center gap-2 text-sm text-stone-600"
      // Announced politely: a reconnect is worth knowing about but must not
      // interrupt what a screen reader is currently reading.
      role="status"
      aria-live="polite"
    >
      <span className={cn("h-2 w-2 shrink-0 rounded-full", copy.dot)} aria-hidden="true" />
      <span className="font-medium text-stone-800">{copy.label}</span>
      <span className="sr-only sm:not-sr-only sm:text-stone-500">{copy.hint}</span>
    </p>
  );
}
