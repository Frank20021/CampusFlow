import { Button } from "../../components/ui/Button";
import { RsvpControl } from "./RsvpControl";
import type { RsvpStatus, StudySession } from "../../types/api";
import { cn, formatSessionRange, fullName } from "../../utils/format";

type SessionCardProps = {
  session: StudySession;
  busy?: boolean;
  onRsvp: (session: StudySession, status: RsvpStatus | null) => void;
  onEdit: (session: StudySession) => void;
  onDelete: (session: StudySession) => void;
};

export function SessionCard({ session, busy, onRsvp, onEdit, onDelete }: SessionCardProps) {
  const hasEnded = new Date(session.end_time).getTime() < Date.now();
  const counts = session.rsvp_counts;

  return (
    <article
      className={cn(
        "rounded-lg border border-stone-200 bg-white p-4",
        hasEnded && "opacity-70",
      )}
      aria-labelledby={`session-${session.id}-title`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 id={`session-${session.id}-title`} className="font-medium text-stone-900">
            {session.title}
          </h3>
          <p className="mt-1 text-sm text-stone-700">
            <time dateTime={session.start_time}>
              {formatSessionRange(session.start_time, session.end_time)}
            </time>
            {hasEnded ? <span className="ml-2 text-stone-500">(ended)</span> : null}
          </p>
          {session.location ? (
            <p className="mt-1 text-sm text-stone-600">{session.location}</p>
          ) : null}
        </div>
        {session.can_manage ? (
          <div className="flex shrink-0 gap-2">
            <Button variant="secondary" size="sm" onClick={() => onEdit(session)}>
              Edit
            </Button>
            <Button variant="ghost" size="sm" onClick={() => onDelete(session)}>
              Delete
            </Button>
          </div>
        ) : null}
      </div>

      {session.description ? (
        <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-stone-700">
          {session.description}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-stone-100 pt-3">
        {hasEnded ? (
          <p className="text-sm text-stone-500">This session has finished.</p>
        ) : (
          <RsvpControl
            sessionTitle={session.title}
            value={session.my_rsvp}
            busy={busy}
            onChange={(status) => onRsvp(session, status)}
          />
        )}
        <p className="text-sm text-stone-600">
          <span className="font-medium text-stone-800">{counts.going} going</span>
          {counts.maybe > 0 ? `, ${counts.maybe} maybe` : ""}
          {session.creator ? (
            <span className="ml-2 text-stone-500">· organised by {fullName(session.creator)}</span>
          ) : null}
        </p>
      </div>
    </article>
  );
}
