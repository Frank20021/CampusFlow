export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

export function fullName(user: { first_name: string; last_name: string }): string {
  return `${user.first_name} ${user.last_name}`.trim();
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
  }).format(new Date(value));
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatDueDate(value: string): string {
  const due = new Date(value);
  const hasTime = due.getHours() !== 0 || due.getMinutes() !== 0;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    ...(hasTime ? { timeStyle: "short" as const } : {}),
  }).format(due);
}

export function isOverdue(value: string | null, status: string): boolean {
  if (!value || status === "DONE") return false;
  return new Date(value).getTime() < Date.now();
}

/** ISO string -> value accepted by <input type="datetime-local"> (local time). */
export function toDateTimeLocal(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

/** <input type="datetime-local"> value -> ISO string, or null when cleared. */
export function fromDateTimeLocal(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

export function statusLabel(status: string): string {
  if (status === "TODO") return "To do";
  if (status === "IN_PROGRESS") return "In progress";
  return "Done";
}

export function priorityLabel(priority: string): string {
  return priority.charAt(0) + priority.slice(1).toLowerCase();
}

export function formatTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, { timeStyle: "short" }).format(new Date(value));
}

/** "Today" / "Yesterday" / a date, for chat day separators. */
export function formatDayLabel(value: string): string {
  const date = new Date(value);
  const startOfDay = (input: Date) =>
    new Date(input.getFullYear(), input.getMonth(), input.getDate()).getTime();
  const dayDiff = Math.round((startOfDay(new Date()) - startOfDay(date)) / 86_400_000);
  if (dayDiff === 0) return "Today";
  if (dayDiff === 1) return "Yesterday";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
  }).format(date);
}

export function sameDay(a: string, b: string): boolean {
  const first = new Date(a);
  const second = new Date(b);
  return (
    first.getFullYear() === second.getFullYear() &&
    first.getMonth() === second.getMonth() &&
    first.getDate() === second.getDate()
  );
}

/** "Tue 3 Nov, 18:00 – 20:00", collapsing the date when both ends share it. */
export function formatSessionRange(start: string, end: string): string {
  const from = new Date(start);
  const to = new Date(end);
  const day = new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
  const time = new Intl.DateTimeFormat(undefined, { timeStyle: "short" });

  if (sameDay(start, end)) {
    return `${day.format(from)}, ${time.format(from)} – ${time.format(to)}`;
  }
  return `${day.format(from)} ${time.format(from)} – ${day.format(to)} ${time.format(to)}`;
}

export function rsvpLabel(status: string | null): string {
  if (status === "going") return "Going";
  if (status === "maybe") return "Maybe";
  if (status === "declined") return "Not going";
  return "No answer";
}

/** Shows the host where a link actually points before anyone clicks it. */
export function linkHost(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function roleLabel(role: string | null): string {
  if (!role) return "Not a member";
  if (role === "owner") return "Owner";
  if (role === "admin") return "Admin";
  return "Member";
}
