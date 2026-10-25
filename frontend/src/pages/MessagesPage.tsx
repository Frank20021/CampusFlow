import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ApiError } from "../api/client";
import { getGroup } from "../api/groups";
import { deleteMessage, listMessages, postMessage } from "../api/messages";
import { useAuth } from "../features/auth/AuthContext";
import { ConnectionStatus } from "../features/messages/ConnectionStatus";
import { MessageComposer } from "../features/messages/MessageComposer";
import { MessageList } from "../features/messages/MessageList";
import { useMessageStream } from "../features/messages/useMessageStream";
import { Alert, EmptyState, Spinner } from "../components/ui/Feedback";
import { PageHeader } from "../components/ui/Overlay";
import type { Message } from "../types/api";

/**
 * The transcript lives in component state rather than the query cache.
 *
 * It is an append-only log fed by two sources at once — a paged history
 * request and a live stream — and both can deliver the same message. Keeping
 * one sorted, de-duplicated array makes that ordering explicit instead of
 * hiding it behind cache invalidation.
 */
function insertMessage(current: Message[], incoming: Message): Message[] {
  if (current.some((message) => message.id === incoming.id)) return current;
  const next = [...current, incoming];
  next.sort((a, b) => {
    const byTime = a.created_at.localeCompare(b.created_at);
    return byTime !== 0 ? byTime : a.id.localeCompare(b.id);
  });
  return next;
}

export function MessagesPage() {
  const { groupId = "" } = useParams();
  const { user } = useAuth();

  const [messages, setMessages] = useState<Message[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const groupQuery = useQuery({
    queryKey: ["group", groupId],
    queryFn: () => getGroup(groupId),
    enabled: Boolean(groupId),
  });

  const historyQuery = useQuery({
    queryKey: ["messages", groupId],
    queryFn: () => listMessages(groupId),
    enabled: Boolean(groupId),
  });

  useEffect(() => {
    const page = historyQuery.data;
    if (!page) return;
    setMessages((current) => page.items.reduce(insertMessage, current));
    setHasMore(page.has_more);
    setCursor(page.next_cursor);
  }, [historyQuery.data]);

  const handleStreamMessage = useCallback((message: Message) => {
    setMessages((current) => insertMessage(current, message));
  }, []);
  const handleStreamDelete = useCallback((messageId: string) => {
    setMessages((current) => current.filter((message) => message.id !== messageId));
  }, []);

  const connection = useMessageStream(groupId || undefined, {
    onMessage: handleStreamMessage,
    onDeleted: handleStreamDelete,
  });

  async function handleSend(content: string) {
    // The POST response is inserted directly rather than waiting for the
    // broadcast to loop back, so the sender never sees their own message lag.
    // `insertMessage` de-duplicates when the stream echo arrives.
    const created = await postMessage(groupId, content);
    setMessages((current) => insertMessage(current, created));
  }

  async function handleDelete(messageId: string) {
    setDeletingId(messageId);
    setActionError(null);
    try {
      await deleteMessage(messageId);
      setMessages((current) => current.filter((message) => message.id !== messageId));
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : "Unable to delete that message");
    } finally {
      setDeletingId(null);
    }
  }

  async function handleLoadOlder() {
    if (!cursor || loadingOlder) return;
    setLoadingOlder(true);
    setActionError(null);
    try {
      const page = await listMessages(groupId, { before: cursor });
      setMessages((current) => page.items.reduce(insertMessage, current));
      setHasMore(page.has_more);
      setCursor(page.next_cursor);
    } catch (error) {
      setActionError(
        error instanceof ApiError ? error.message : "Unable to load older messages",
      );
    } finally {
      setLoadingOlder(false);
    }
  }

  if (!groupId) return <Navigate to="/app/groups" replace />;
  if (groupQuery.isLoading) return <Spinner label="Loading conversation" />;

  const notAMember =
    (groupQuery.error instanceof ApiError && groupQuery.error.status === 403) ||
    (historyQuery.error instanceof ApiError && historyQuery.error.status === 403);

  if (notAMember) {
    return (
      <EmptyState
        title="Members only"
        body="Join this group to read and post messages."
        action={
          <Link
            to={`/app/groups/${groupId}`}
            className="text-sm font-medium text-teal-800 hover:underline"
          >
            Go to the group
          </Link>
        }
      />
    );
  }

  if (groupQuery.error instanceof ApiError && groupQuery.error.status === 404) {
    return <EmptyState title="Group not found" body="It may have been deleted." />;
  }
  if (!groupQuery.data) return <Alert>Unable to load this conversation.</Alert>;

  const group = groupQuery.data;
  const canModerate = group.my_role === "owner" || group.my_role === "admin";

  return (
    <div>
      <PageHeader
        title={`${group.name} chat`}
        description="Messages are visible to every member of this group."
        actions={
          <Link
            to={`/app/groups/${groupId}`}
            className="inline-flex h-10 items-center rounded-md border border-stone-300 bg-white px-4 text-sm font-medium hover:bg-stone-50"
          >
            Back to group
          </Link>
        }
      />

      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <ConnectionStatus state={connection} />
        {canModerate ? (
          <p className="text-xs text-stone-500">
            As {group.my_role}, you can remove any message.
          </p>
        ) : null}
      </div>

      {actionError ? <Alert>{actionError}</Alert> : null}
      {historyQuery.error && !notAMember ? (
        <Alert>Messages could not be loaded. Check your connection and reload.</Alert>
      ) : null}

      {historyQuery.isLoading ? (
        <Spinner label="Loading messages" />
      ) : (
        <MessageList
          messages={messages}
          currentUserId={user?.id ?? ""}
          canModerate={canModerate}
          hasMore={hasMore}
          loadingOlder={loadingOlder}
          onLoadOlder={handleLoadOlder}
          deletingId={deletingId}
          onDelete={handleDelete}
        />
      )}

      <MessageComposer onSend={handleSend} disabled={connection === "denied"} />
    </div>
  );
}
