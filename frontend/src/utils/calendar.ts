/**
 * Month-grid maths for the calendar view.
 *
 * Everything here works in the viewer's local time zone, which is the point:
 * the API stores and returns UTC instants, and a session at 23:30 UTC belongs
 * on a different calendar square depending on where you are reading it.
 */

const DAY_MS = 86_400_000;

export type CalendarDay = {
  date: Date;
  inCurrentMonth: boolean;
  isToday: boolean;
};

export function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

export function isSameDay(a: Date, b: Date): boolean {
  return startOfDay(a).getTime() === startOfDay(b).getTime();
}

export function addMonths(date: Date, delta: number): Date {
  // Day 1 avoids the classic overflow where adding a month to the 31st lands
  // you two months later.
  return new Date(date.getFullYear(), date.getMonth() + delta, 1);
}

export function monthLabel(date: Date): string {
  return new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" }).format(date);
}

export function weekdayLabels(): string[] {
  // Built from a known Sunday so the names follow the viewer's locale while
  // the column order stays fixed.
  const sunday = new Date(2024, 0, 7);
  const formatter = new Intl.DateTimeFormat(undefined, { weekday: "short" });
  return Array.from({ length: 7 }, (_, index) =>
    formatter.format(new Date(sunday.getTime() + index * DAY_MS)),
  );
}

/**
 * Whole weeks (Sunday-first) covering the month, so the grid is always
 * rectangular and never has ragged leading or trailing rows.
 */
export function buildMonthGrid(month: Date, today = new Date()): CalendarDay[][] {
  const firstOfMonth = new Date(month.getFullYear(), month.getMonth(), 1);
  const gridStart = new Date(firstOfMonth);
  gridStart.setDate(firstOfMonth.getDate() - firstOfMonth.getDay());

  const weeks: CalendarDay[][] = [];
  const cursor = new Date(gridStart);

  while (weeks.length < 6) {
    const week: CalendarDay[] = [];
    for (let index = 0; index < 7; index += 1) {
      const date = new Date(cursor);
      week.push({
        date,
        inCurrentMonth: date.getMonth() === month.getMonth(),
        isToday: isSameDay(date, today),
      });
      cursor.setDate(cursor.getDate() + 1);
    }
    weeks.push(week);

    // Six rows is the worst case; stop as soon as the month is covered so a
    // short month does not render a trailing week of greyed-out days.
    const nextDayIsPastMonth =
      cursor.getMonth() !== month.getMonth() && cursor > firstOfMonth;
    if (nextDayIsPastMonth) break;
  }

  return weeks;
}

/** Inclusive-exclusive ISO bounds covering the rendered grid, for the API. */
export function monthRange(month: Date): { startsAfter: string; startsBefore: string } {
  const weeks = buildMonthGrid(month);
  const first = weeks[0][0].date;
  const lastWeek = weeks[weeks.length - 1];
  const last = new Date(lastWeek[6].date);
  last.setDate(last.getDate() + 1);
  return { startsAfter: first.toISOString(), startsBefore: last.toISOString() };
}

export function groupByDay<T>(items: T[], getDate: (item: T) => string): Map<number, T[]> {
  const byDay = new Map<number, T[]>();
  for (const item of items) {
    const key = startOfDay(new Date(getDate(item))).getTime();
    const bucket = byDay.get(key);
    if (bucket) bucket.push(item);
    else byDay.set(key, [item]);
  }
  return byDay;
}
