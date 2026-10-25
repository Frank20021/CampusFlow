import { useMemo, useRef, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../api/client";
import { getGroup } from "../api/groups";
import {
  clearRsvp,
  createSession,
  deleteSession,
  listSessions,
  setRsvp,
  updateSession,
  type SessionInput,
} from "../api/sessions";
import { MonthCalendar } from "../features/sessions/MonthCalendar";
import { SessionCard } from "../features/sessions/SessionCard";
import { SessionFormDialog } from "../features/sessions/SessionFormDialog";
import { Alert, EmptyState, Spinner } from "../components/ui/Feedback";
import { Button } from "../components/ui/Button";
import { ConfirmDialog, PageHeader } from "../components/ui/Overlay";
import { monthRange } from "../utils/calendar";
import { cn, rsvpLabel } from "../utils/format";
import type { RsvpStatus, StudySession } from "../types/api";

type View = "agenda" | "calendar";

export function SessionsPage() {
  const { groupId = "" } = useParams();
  const queryClient = useQueryClient();

  const [view, setView] = useState<View>("agenda");
  const [month, setMonth] = useState(() => new Date());
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogSession, setDialogSession] = useState<StudySession | null>(null);
  const [pendingDelete, setPendingDelete] = useState<StudySession | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [rsvpBusyId, setRsvpBusyId] = useState<string | null>(null);
  const agendaRef = useRef<HTMLDivElement>(null);

  // The agenda wants only what is still to come; the calendar needs the whole
  // rendered grid, including days already past in the current month.
  const range = useMemo(() => monthRange(month), [month]);
  const queryKey =
    view === "agenda"
      ? (["sessions", groupId, "upcoming"] as const)
      : (["sessions", groupId, "month", range.startsAfter] as const);

  const groupQuery = useQuery({
    queryKey: ["group", groupId],
    queryFn: () => getGroup(groupId),
    enabled: Boolean(groupId),
  });

  const sessionsQuery = useQuery({
    queryKey,
    queryFn: () =>
      view === "agenda"
        ? listSessions(groupId, { upcoming: true })
        : listSessions(groupId, {
            startsAfter: range.startsAfter,
            startsBefore: range.startsBefore,
          }),
    enabled: Boolean(groupId),
  });

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ["sessions", groupId] });
    await queryClient.invalidateQueries({ queryKey: ["my-sessions"] });
  }

  function describeError(error: unknown, fallback: string): string {
    return error instanceof ApiError ? error.message : fallback;
  }

  const saveMutation = useMutation({
    mutationFn: (input: SessionInput) =>
      dialogSession
        ? updateSession(dialogSession.id, input)
        : createSession(groupId, input),
    onSuccess: async (saved) => {
      setDialogOpen(false);
      setDialogSession(null);
      setFormError(null);
      setAnnouncement(`${saved.title} saved.`);
      await refresh();
    },
    onError: (error) => setFormError(describeError(error, "Unable to save that session")),
  });

  const deleteMutation = useMutation({
    mutationFn: (session: StudySession) => deleteSession(session.id),
    onSuccess: async () => {
      setAnnouncement(`${pendingDelete?.title ?? "Session"} deleted.`);
      setPendingDelete(null);
      await refresh();
    },
    onError: (error) => {
      setPendingDelete(null);
      setActionError(describeError(error, "Unable to delete that session"));
    },
  });

  async function handleRsvp(session: StudySession, status: RsvpStatus | null) {
    setRsvpBusyId(session.id);
    setActionError(null);
    try {
      const updated = status === null ? await clearRsvp(session.id) : await setRsvp(session.id, status);
      setAnnouncement(`${session.title}: ${rsvpLabel(updated.my_rsvp)}.`);
      await refresh();
    } catch (error) {
      setActionError(describeError(error, "Unable to save your response"));
    } finally {
      setRsvpBusyId(null);
    }
  }

  function openCreate() {
    setDialogSession(null);
    setFormError(null);
    setDialogOpen(true);
  }

  function openEdit(session: StudySession) {
    setDialogSession(session);
    setFormError(null);
    setDialogOpen(true);
  }

  if (!groupId) return <Navigate to="/app/groups" replace />;
  if (groupQuery.isLoading) return <Spinner label="Loading sessions" />;

  const notAMember =
    (groupQuery.error instanceof ApiError && groupQuery.error.status === 403) ||
    (sessionsQuery.error instanceof ApiError && sessionsQuery.error.status === 403);

  if (notAMember) {
    return (
      <EmptyState
        title="Members only"
        body="Join this group to see and schedule study sessions."
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
  if (!groupQuery.data) return <Alert>Unable to load this group.</Alert>;

  const group = groupQuery.data;
  const sessions = sessionsQuery.data?.items ?? [];

  return (
    <div>
      <PageHeader
        title={`${group.name} sessions`}
        description="Scheduled in your local time zone."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link
              to={`/app/groups/${groupId}`}
              className="inline-flex h-10 items-center rounded-md border border-stone-300 bg-white px-4 text-sm font-medium hover:bg-stone-50"
            >
              Back to group
            </Link>
            <Button onClick={openCreate}>Schedule session</Button>
          </div>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="inline-flex rounded-md border border-stone-300 bg-white p-0.5" role="group" aria-label="View">
          {(["agenda", "calendar"] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setView(option)}
              aria-pressed={view === option}
              className={cn(
                "rounded px-3 py-1.5 text-sm font-medium capitalize transition-colors",
                "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-800",
                view === option ? "bg-teal-800 text-white" : "text-stone-700 hover:bg-stone-50",
              )}
            >
              {option === "agenda" ? "Upcoming" : "Calendar"}
            </button>
          ))}
        </div>
      </div>

      <p aria-live="polite" className="sr-only">
        {announcement}
      </p>
      {actionError ? <Alert>{actionError}</Alert> : null}
      {sessionsQuery.error && !notAMember ? (
        <Alert>Sessions could not be loaded. Check your connection and reload.</Alert>
      ) : null}

      {sessionsQuery.isLoading ? (
        <Spinner label="Loading sessions" />
      ) : view === "calendar" ? (
        <MonthCalendar
          month={month}
          sessions={sessions}
          onMonthChange={setMonth}
          onSelect={(session) => {
            // Jump to the agenda entry rather than opening yet another dialog.
            setView("agenda");
            setAnnouncement(`Showing ${session.title} in the upcoming list.`);
            window.setTimeout(() => agendaRef.current?.focus(), 0);
          }}
        />
      ) : sessions.length === 0 ? (
        <EmptyState
          title="Nothing scheduled yet"
          body="Pick a time that works and your group will see it here."
          action={<Button onClick={openCreate}>Schedule the first session</Button>}
        />
      ) : (
        <div ref={agendaRef} tabIndex={-1} className="flex flex-col gap-3 outline-none">
          {sessions.map((session) => (
            <SessionCard
              key={session.id}
              session={session}
              busy={rsvpBusyId === session.id}
              onRsvp={handleRsvp}
              onEdit={openEdit}
              onDelete={setPendingDelete}
            />
          ))}
        </div>
      )}

      <SessionFormDialog
        open={dialogOpen}
        session={dialogSession}
        busy={saveMutation.isPending}
        serverError={formError}
        onClose={() => {
          setDialogOpen(false);
          setDialogSession(null);
        }}
        onSubmit={(input) => saveMutation.mutate(input)}
      />

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete this session?"
        body={`"${pendingDelete?.title ?? ""}" will be removed for everyone in the group.`}
        confirmLabel="Delete session"
        danger
        busy={deleteMutation.isPending}
        onClose={() => setPendingDelete(null)}
        onConfirm={() => pendingDelete && deleteMutation.mutate(pendingDelete)}
      />
    </div>
  );
}
