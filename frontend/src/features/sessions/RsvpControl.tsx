import { cn } from "../../utils/format";
import type { RsvpStatus } from "../../types/api";

const CHOICES: Array<{ value: RsvpStatus; label: string }> = [
  { value: "going", label: "Going" },
  { value: "maybe", label: "Maybe" },
  { value: "declined", label: "Can't go" },
];

type RsvpControlProps = {
  sessionTitle: string;
  value: RsvpStatus | null;
  busy?: boolean;
  onChange: (status: RsvpStatus | null) => void;
};

/**
 * A radio group rather than three independent buttons: the answers are
 * mutually exclusive, and radios give arrow-key navigation and a single tab
 * stop for free. Re-picking the current answer withdraws it.
 */
export function RsvpControl({ sessionTitle, value, busy = false, onChange }: RsvpControlProps) {
  return (
    <fieldset disabled={busy} className="min-w-0">
      <legend className="sr-only">{`Your response to ${sessionTitle}`}</legend>
      <div className="flex flex-wrap gap-1" role="radiogroup" aria-label={`Your response to ${sessionTitle}`}>
        {CHOICES.map((choice) => {
          const selected = value === choice.value;
          return (
            <button
              key={choice.value}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChange(selected ? null : choice.value)}
              className={cn(
                "rounded-md border px-3 py-1 text-sm font-medium transition-colors",
                "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-800",
                "disabled:cursor-not-allowed disabled:opacity-60",
                selected
                  ? "border-teal-800 bg-teal-800 text-white"
                  : "border-stone-300 bg-white text-stone-700 hover:bg-stone-50",
              )}
            >
              {choice.label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
