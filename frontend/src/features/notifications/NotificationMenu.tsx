import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getUnreadCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "../../api/notifications";
import type { Notification, Paginated } from "../../types/api";
import { cn, formatDateTime } from "../../utils/format";
import { useNotificationStream } from "./useNotificationStream";

const LIST_KEY = ["notifications"] as const;
const UNREAD_KEY = ["notifications-unread"] as const;

function prependNotification(
  current: Paginated<Notification> | undefined,
  incoming: Notification,
): Paginated<Notification> {
  if (!current) {
    return { items: [incoming], total: 1, limit: 20, offset: 0 };
  }
  if (current.items.some((item) => item.id === incoming.id)) return current;
  return {
    ...current,
    items: [incoming, ...current.items],
    total: current.total + 1,
  };
}

export function NotificationMenu({ enabled }: { enabled: boolean }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const panelId = useId();

  const listQuery = useQuery({
    queryKey: LIST_KEY,
    queryFn: () => listNotifications({ limit: 20 }),
    enabled,
  });
  const unreadQuery = useQuery({
    queryKey: UNREAD_KEY,
    queryFn: getUnreadCount,
    enabled,
  });

  const handleLive = useCallback(
    (incoming: Notification) => {
      queryClient.setQueryData(LIST_KEY, (current: Paginated<Notification> | undefined) =>
        prependNotification(current, incoming),
      );
      if (incoming.read_at === null) {
        queryClient.setQueryData(UNREAD_KEY, (current: { unread: number } | undefined) => ({
          unread: (current?.unread ?? 0) + 1,
        }));
      }
    },
    [queryClient],
  );

  useNotificationStream(enabled, { onNotification: handleLive });

  const markOne = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: (updated) => {
      queryClient.setQueryData(LIST_KEY, (current: Paginated<Notification> | undefined) => {
        if (!current) return current;
        return {
          ...current,
          items: current.items.map((item) => (item.id === updated.id ? updated : item)),
        };
      });
      void queryClient.invalidateQueries({ queryKey: UNREAD_KEY });
    },
  });

  const markAll = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: LIST_KEY });
      await queryClient.invalidateQueries({ queryKey: UNREAD_KEY });
    },
  });

  useEffect(() => {
    if (!open) return;

    function onDocumentClick(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    // `click`, not `mousedown`: a mousedown-outside listener can unmount the
    // panel before the inner button's click fires (jsdom and some browsers).
    document.addEventListener("click", onDocumentClick);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("click", onDocumentClick);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const unread = unreadQuery.data?.unread ?? 0;
  const items = listQuery.data?.items ?? [];
  const badge = unread > 99 ? "99+" : String(unread);

  function openItem(item: Notification) {
    if (item.read_at == null) {
      markOne.mutate(item.id);
    }
    setOpen(false);
    void navigate(item.href);
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        className={cn(
          "relative inline-flex h-10 items-center rounded-md px-3 text-sm font-medium",
          "text-stone-700 hover:bg-stone-100",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-800",
        )}
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        Notifications
        {unread > 0 ? (
          <span className="ml-2 inline-flex min-w-5 items-center justify-center rounded-full bg-teal-800 px-1.5 text-xs font-semibold text-white">
            <span className="sr-only">{unread} unread</span>
            <span aria-hidden="true">{badge}</span>
          </span>
        ) : null}
      </button>

      {open ? (
        <div
          id={panelId}
          role="dialog"
          aria-label="Notifications"
          className="absolute right-0 z-20 mt-2 w-[min(24rem,calc(100vw-2rem))] rounded-lg border border-stone-200 bg-white p-3 shadow-lg"
        >
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-sm font-semibold text-stone-900">Notifications</p>
            {unread > 0 ? (
              <button
                type="button"
                className="text-xs font-medium text-teal-800 hover:underline"
                onClick={() => markAll.mutate()}
                disabled={markAll.isPending}
              >
                Mark all as read
              </button>
            ) : null}
          </div>

          {listQuery.isLoading ? (
            <p className="py-6 text-center text-sm text-stone-500">Loading notifications</p>
          ) : items.length === 0 ? (
            <p className="py-6 text-center text-sm text-stone-500">
              Nothing yet. Assignments, sessions, and shared links will show up here.
            </p>
          ) : (
            <ul className="max-h-80 overflow-y-auto" aria-live="polite">
              {items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => openItem(item)}
                    className={cn(
                      "w-full rounded-md px-2 py-2 text-left text-sm hover:bg-stone-50",
                      "focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-800",
                      item.read_at ? "text-stone-600" : "bg-teal-50/60 text-stone-900",
                    )}
                  >
                    <span className="flex items-baseline justify-between gap-2">
                      <span className="font-medium">{item.title}</span>
                      <time dateTime={item.created_at} className="shrink-0 text-xs text-stone-500">
                        {formatDateTime(item.created_at)}
                      </time>
                    </span>
                    <span className="mt-0.5 block text-xs leading-5">{item.body}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
