import { useState, type FormEvent } from "react";
import { Button } from "../../components/ui/Button";
import { TextAreaField, TextField } from "../../components/ui/Field";
import type { ResourceInput } from "../../api/resources";

type ResourceFormProps = {
  busy?: boolean;
  serverError?: string | null;
  onSubmit: (input: ResourceInput) => void;
};

/**
 * Mirrors the server's scheme allowlist so the common mistake ("example.edu"
 * with no scheme) is corrected in the field rather than bounced back as a 422.
 * The server still validates; this is convenience, not security.
 */
function urlProblem(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return "Add the link";
  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return "Include the full address, starting with https://";
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return "Links must start with http:// or https://";
  }
  return null;
}

export function ResourceForm({ busy = false, serverError, onSubmit }: ResourceFormProps) {
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [errors, setErrors] = useState<{ title?: string; url?: string }>({});

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found: { title?: string; url?: string } = {};
    if (!title.trim()) found.title = "Give the link a name";
    const urlError = urlProblem(url);
    if (urlError) found.url = urlError;

    setErrors(found);
    if (Object.keys(found).length > 0) return;

    onSubmit({
      title: title.trim(),
      url: url.trim(),
      description: description.trim() || null,
    });
    setTitle("");
    setUrl("");
    setDescription("");
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-lg border border-stone-200 bg-white p-4"
      aria-label="Share a resource"
      noValidate
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          label="Name"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          error={errors.title}
          maxLength={200}
          placeholder="Lecture slides"
          required
        />
        <TextField
          label="Link"
          type="url"
          inputMode="url"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          error={errors.url}
          placeholder="https://example.edu/slides.pdf"
          required
        />
      </div>
      <div className="mt-4">
        <TextAreaField
          label="Why it is useful"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          hint="Optional. A line of context saves everyone a click."
          maxLength={1000}
        />
      </div>
      {serverError ? (
        <p role="alert" className="mt-3 text-sm text-red-800">
          {serverError}
        </p>
      ) : null}
      <div className="mt-4 flex justify-end">
        <Button type="submit" loading={busy}>
          Share link
        </Button>
      </div>
    </form>
  );
}
