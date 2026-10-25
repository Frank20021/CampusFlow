import {
  useId,
  type InputHTMLAttributes,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { cn } from "../../utils/format";

type FieldProps = {
  label: string;
  error?: string;
  hint?: string;
};

type InputProps = FieldProps & InputHTMLAttributes<HTMLInputElement>;
type TextAreaProps = FieldProps & TextareaHTMLAttributes<HTMLTextAreaElement>;
type SelectProps = FieldProps & SelectHTMLAttributes<HTMLSelectElement>;

export function SelectField({ label, error, hint, id, className, children, ...props }: SelectProps) {
  const generated = useId();
  const field = id ?? generated;
  const errorId = `${field}-error`;
  const hintId = `${field}-hint`;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={field} className="text-sm font-medium text-stone-800">
        {label}
      </label>
      <select
        id={field}
        className={cn(
          "h-10 rounded-md border bg-white px-3 text-sm text-stone-900",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-800",
          error ? "border-red-700" : "border-stone-300",
          className,
        )}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        {...props}
      >
        {children}
      </select>
      {hint && !error ? (
        <p id={hintId} className="text-xs text-stone-500">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-xs text-red-800" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function TextField({ label, error, hint, id, className, ...props }: InputProps) {
  const generated = useId();
  const field = id ?? generated;
  const errorId = `${field}-error`;
  const hintId = `${field}-hint`;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={field} className="text-sm font-medium text-stone-800">
        {label}
      </label>
      <input
        id={field}
        className={cn(
          "h-10 rounded-md border bg-white px-3 text-sm text-stone-900",
          "placeholder:text-stone-400",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-800",
          error ? "border-red-700" : "border-stone-300",
          className,
        )}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        {...props}
      />
      {hint && !error ? (
        <p id={hintId} className="text-xs text-stone-500">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-xs text-red-800" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function TextAreaField({ label, error, hint, id, className, ...props }: TextAreaProps) {
  const generated = useId();
  const field = id ?? generated;
  const errorId = `${field}-error`;
  const hintId = `${field}-hint`;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={field} className="text-sm font-medium text-stone-800">
        {label}
      </label>
      <textarea
        id={field}
        className={cn(
          "min-h-24 rounded-md border bg-white px-3 py-2 text-sm text-stone-900",
          "placeholder:text-stone-400",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-800",
          error ? "border-red-700" : "border-stone-300",
          className,
        )}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        {...props}
      />
      {hint && !error ? (
        <p id={hintId} className="text-xs text-stone-500">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-xs text-red-800" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
