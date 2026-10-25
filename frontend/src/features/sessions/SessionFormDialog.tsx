import { useEffect, useState, type FormEvent } from "react";
import { Button } from "../../components/ui/Button";
import { TextAreaField, TextField } from "../../components/ui/Field";
import { Modal } from "../../components/ui/Overlay";
import type { SessionInput } from "../../api/sessions";
import type { StudySession } from "../../types/api";
import { fromDateTimeLocal, toDateTimeLocal } from "../../utils/format";

type SessionFormDialogProps = {
  open: boolean;
  session: StudySession | null;
  busy?: boolean;
  serverError?: string | null;
  onClose: () => void;
  onSubmit: (input: SessionInput) => void;
};

type Errors = Partial<Record<"title" | "start_time" | "end_time", string>>;

const MAX_HOURS = 24;

/** Defaults to the next whole hour, which is what people usually want. */
function defaultStart(): string {
  const start = new Date();
  start.setMinutes(0, 0, 0);
  start.setHours(start.getHours() + 1);
  return toDateTimeLocal(start.toISOString());
}

function addHours(localValue: string, hours: number): string {
  const iso = fromDateTimeLocal(localValue);
  if (!iso) return "";
  const end = new Date(iso);
  end.setHours(end.getHours() + hours);
  return toDateTimeLocal(end.toISOString());
}

export function SessionFormDialog({
  open,
  session,
  busy = false,
  serverError,
  onClose,
  onSubmit,
}: SessionFormDialogProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [location, setLocation] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [errors, setErrors] = useState<Errors>({});

  useEffect(() => {
    if (!open) return;
    setErrors({});
    if (session) {
      setTitle(session.title);
      setDescription(session.description ?? "");
      setLocation(session.location ?? "");
      setStartTime(toDateTimeLocal(session.start_time));
      setEndTime(toDateTimeLocal(session.end_time));
    } else {
      const start = defaultStart();
      setTitle("");
      setDescription("");
      setLocation("");
      setStartTime(start);
      setEndTime(addHours(start, 1));
    }
  }, [open, session]);

  function handleStartChange(value: string) {
    setStartTime(value);
    // Drag the end along with the start so the window stays valid while
    // someone is still typing, instead of flashing an error at them.
    if (!endTime || fromDateTimeLocal(endTime)! <= fromDateTimeLocal(value)!) {
      setEndTime(addHours(value, 1));
    }
  }

  function validate(): Errors {
    const found: Errors = {};
    if (!title.trim()) found.title = "Give the session a title";
    const start = fromDateTimeLocal(startTime);
    const end = fromDateTimeLocal(endTime);
    if (!start) found.start_time = "Choose when it starts";
    if (!end) found.end_time = "Choose when it ends";
    if (start && end) {
      const span = new Date(end).getTime() - new Date(start).getTime();
      if (span <= 0) found.end_time = "The end time must be after the start time";
      else if (span > MAX_HOURS * 3_600_000) {
        found.end_time = `A session cannot run longer than ${MAX_HOURS} hours`;
      }
    }
    return found;
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    onSubmit({
      title: title.trim(),
      description: description.trim() || null,
      location: location.trim() || null,
      start_time: fromDateTimeLocal(startTime)!,
      end_time: fromDateTimeLocal(endTime)!,
    });
  }

  return (
    <Modal
      open={open}
      title={session ? "Edit study session" : "Schedule a study session"}
      description="Times are shown in your own time zone."
      onClose={onClose}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        <TextField
          label="Title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          error={errors.title}
          maxLength={200}
          autoFocus
          required
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Starts"
            type="datetime-local"
            value={startTime}
            onChange={(event) => handleStartChange(event.target.value)}
            error={errors.start_time}
            required
          />
          <TextField
            label="Ends"
            type="datetime-local"
            value={endTime}
            onChange={(event) => setEndTime(event.target.value)}
            error={errors.end_time}
            required
          />
        </div>
        <TextField
          label="Location"
          value={location}
          onChange={(event) => setLocation(event.target.value)}
          hint="A room, a building, or a meeting link."
          maxLength={200}
        />
        <TextAreaField
          label="Details"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          hint="What should people bring or prepare?"
          maxLength={2000}
        />
        {serverError ? (
          <p role="alert" className="text-sm text-red-800">
            {serverError}
          </p>
        ) : null}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            {session ? "Save changes" : "Schedule session"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
