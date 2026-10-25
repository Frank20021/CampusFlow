import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Button } from "../../components/ui/Button";

const MAX_LENGTH = 2000;
const COUNTER_THRESHOLD = 1800;

type MessageComposerProps = {
  onSend: (content: string) => Promise<void>;
  disabled?: boolean;
};

export function MessageComposer({ onSend, disabled = false }: MessageComposerProps) {
  const [value, setValue] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const trimmed = value.trim();
  const tooLong = value.length > MAX_LENGTH;
  const canSend = trimmed.length > 0 && !tooLong && !sending && !disabled;

  async function submit() {
    if (!canSend) return;
    setSending(true);
    setError(null);
    try {
      await onSend(trimmed);
      setValue("");
      // Keep focus in the box so a conversation can be typed without
      // reaching for the mouse between messages.
      textareaRef.current?.focus();
    } catch (sendError) {
      setError(sendError instanceof Error ? sendError.message : "Message could not be sent");
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter makes a new line — the convention every chat
    // app has trained people to expect.
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4">
      <label htmlFor="message-input" className="block text-sm font-medium text-stone-700">
        Message
      </label>
      <div className="mt-1 flex items-end gap-2">
        <textarea
          id="message-input"
          ref={textareaRef}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={2}
          disabled={disabled}
          aria-describedby="message-help message-error"
          aria-invalid={tooLong || Boolean(error) || undefined}
          placeholder="Write a message…"
          className="block w-full resize-y rounded-md border border-stone-300 px-3 py-2 text-sm focus:border-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-800/30 disabled:bg-stone-100"
        />
        <Button type="submit" disabled={!canSend} loading={sending} className="shrink-0">
          Send
        </Button>
      </div>
      <div className="mt-1 flex items-center justify-between gap-4">
        <p id="message-help" className="text-xs text-stone-500">
          Press Enter to send, Shift + Enter for a new line.
        </p>
        {value.length >= COUNTER_THRESHOLD ? (
          <p className={tooLong ? "text-xs font-medium text-red-700" : "text-xs text-stone-500"}>
            {value.length} / {MAX_LENGTH}
          </p>
        ) : null}
      </div>
      <p id="message-error" role="alert" className="mt-1 text-sm text-red-700">
        {tooLong ? `Messages are limited to ${MAX_LENGTH} characters.` : error}
      </p>
    </form>
  );
}
