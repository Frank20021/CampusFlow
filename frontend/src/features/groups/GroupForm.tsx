import { useState, type FormEvent } from "react";
import { TextAreaField, TextField } from "../../components/ui/Field";
import { Button } from "../../components/ui/Button";
import type { GroupInput } from "../../api/groups";

type GroupFormProps = {
  initial?: GroupInput;
  submitLabel: string;
  onSubmit: (input: GroupInput) => Promise<void>;
  busy?: boolean;
  error?: string | null;
};

export function GroupForm({ initial, submitLabel, onSubmit, busy, error }: GroupFormProps) {
  const [name, setName] = useState(initial?.name ?? "");
  const [courseCode, setCourseCode] = useState(initial?.course_code ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [nameError, setNameError] = useState<string | undefined>();

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setNameError("Name is required");
      return;
    }
    setNameError(undefined);
    await onSubmit({
      name: name.trim(),
      course_code: courseCode.trim() || undefined,
      description: description.trim() || undefined,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
      {error ? (
        <p className="text-sm text-red-800" role="alert">
          {error}
        </p>
      ) : null}
      <TextField
        label="Group name"
        value={name}
        onChange={(event) => setName(event.target.value)}
        error={nameError}
        required
      />
      <TextField
        label="Course code"
        value={courseCode}
        onChange={(event) => setCourseCode(event.target.value)}
        hint="Optional. Example: CS201"
      />
      <TextAreaField
        label="Description"
        value={description}
        onChange={(event) => setDescription(event.target.value)}
      />
      <div>
        <Button type="submit" loading={busy}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
