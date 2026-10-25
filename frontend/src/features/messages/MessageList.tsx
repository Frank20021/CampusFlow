import { useEffect, useLayoutEffect, useRef } from "react";
import { Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Feedback";
import type { Message } from "../../types/api";
import { cn, formatDayLabel, formatTime, fullName, sameDay } from "../../utils/format";

type MessageListProps = {
  messages: Message[];
  currentUserId: string;
  canModerate: boolean;
  hasMore: boolean;
  loadingOlder: boolean;
  onLoadOlder: () => void;
  deletingId: string | null;
  onDelete: (messageId: string) => void;
};

// Consecutive messages from one person inside this window are visually joined
// rather than repeating the name and time on every line.
const GROUPING_WINDOW_MS = 5 * 60 * 1000;
const NEAR_BOTTOM_PX = 120;

export function MessageList({
  messages,
  currentUserId,
  canModerate,
  hasMore,
  loadingOlder,
  onLoadOlder,
  deletingId,
  onDelete,
}: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const wasNearBottom = useRef(true);
  const previousHeight = useRef(0);
  const previousCount = useRef(0);

  // Record the position *before* React paints the new list, because after
  // paint the old scroll offset is already meaningless.
  useLayoutEffect(() => {
    const node = scrollRef.current;
    if (!node) return;
    const distanceFromBottom = node.scrollHeight - node.scrollTop - node.clientHeight;
    wasNearBottom.current = distanceFromBottom <= NEAR_BOTTOM_PX;
    previousHeight.current = node.scrollHeight;
  });

  useEffect(() => {
    const node = scrollRef.current;
    if (!node) return;

    const grewAtTop = messages.length > previousCount.current && !wasNearBottom.current;
    previousCount.current = messages.length;

    if (grewAtTop) {
      // Older messages were prepended. Keeping the viewport pinned to the
      // same message stops the page from jumping under someone mid-read.
      node.scrollTop += node.scrollHeight - previousHeight.current;
      return;
    }
    if (wasNearBottom.current) {
      node.scrollTop = node.scrollHeight;
    }
  }, [messages]);

  return (
    <div
      ref={scrollRef}
      className="h-[26rem] overflow-y-auto rounded-lg border border-stone-200 bg-white p-4 sm:h-[32rem]"
      tabIndex={0}
      // `log` tells assistive tech this region gains entries over time, and
      // polite announcements avoid cutting off whatever is being read.
      role="log"
      aria-live="polite"
      aria-relevant="additions"
      aria-label="Group messages"
    >
      {hasMore ? (
        <div className="mb-4 flex justify-center">
          <Button variant="secondary" size="sm" onClick={onLoadOlder} loading={loadingOlder}>
            Load older messages
          </Button>
        </div>
      ) : null}
      {loadingOlder && !hasMore ? <Spinner label="Loading messages" /> : null}

      {messages.length === 0 ? (
        <p className="py-12 text-center text-sm text-stone-500">
          No messages yet. Say hello to get the conversation started.
        </p>
      ) : (
        <ol className="space-y-1">
          {messages.map((message, index) => {
            const previous = index > 0 ? messages[index - 1] : null;
            const startsNewDay = !previous || !sameDay(previous.created_at, message.created_at);
            const continues =
              !startsNewDay &&
              previous?.user_id === message.user_id &&
              new Date(message.created_at).getTime() -
                new Date(previous.created_at).getTime() <
                GROUPING_WINDOW_MS;
            const mine = message.user_id === currentUserId;
            const author = message.author ? fullName(message.author) : "Former member";

            return (
              <li key={message.id}>
                {startsNewDay ? (
                  <div className="my-4 flex items-center gap-3">
                    <span className="h-px flex-1 bg-stone-200" />
                    <span className="text-xs font-medium uppercase tracking-wide text-stone-500">
                      {formatDayLabel(message.created_at)}
                    </span>
                    <span className="h-px flex-1 bg-stone-200" />
                  </div>
                ) : null}

                <div className={cn("group flex", mine ? "justify-end" : "justify-start")}>
                  <div className={cn("max-w-[85%] sm:max-w-[70%]", continues ? "mt-0.5" : "mt-3")}>
                    {!continues ? (
                      <p
                        className={cn(
                          "mb-1 flex items-baseline gap-2 text-xs",
                          mine ? "justify-end" : "justify-start",
                        )}
                      >
                        <span className="font-medium text-stone-700">
                          {mine ? "You" : author}
                        </span>
                        <time dateTime={message.created_at} className="text-stone-500">
                          {formatTime(message.created_at)}
                        </time>
                      </p>
                    ) : null}
                    <div className={cn("flex items-center gap-2", mine ? "flex-row-reverse" : "")}>
                      <p
                        className={cn(
                          "whitespace-pre-wrap break-words rounded-lg px-3 py-2 text-sm leading-6",
                          mine
                            ? "bg-teal-800 text-white"
                            : "bg-stone-100 text-stone-900",
                        )}
                      >
                        {message.content}
                      </p>
                      {mine || canModerate ? (
                        <button
                          type="button"
                          onClick={() => onDelete(message.id)}
                          disabled={deletingId === message.id}
                          // Hidden until hover for pointer users, but always
                          // reachable by keyboard via focus-within.
                          className={cn(
                            "rounded p-1 text-xs text-stone-500 opacity-0 transition-opacity",
                            "hover:bg-stone-100 hover:text-red-700 focus-visible:opacity-100",
                            "focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-800",
                            "group-hover:opacity-100 disabled:opacity-50",
                          )}
                          aria-label={`Delete message from ${mine ? "you" : author}`}
                        >
                          Delete
                        </button>
                      ) : null}
                    </div>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
