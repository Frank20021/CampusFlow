import { Button } from "../../components/ui/Button";
import type { StudySession } from "../../types/api";
import {
  buildMonthGrid,
  groupByDay,
  monthLabel,
  startOfDay,
  weekdayLabels,
} from "../../utils/calendar";
import { cn, formatTime } from "../../utils/format";

type MonthCalendarProps = {
  month: Date;
  sessions: StudySession[];
  onMonthChange: (month: Date) => void;
  onSelect: (session: StudySession) => void;
};

/**
 * A real `<table>` rather than a grid of divs.
 *
 * A month is tabular data — weekday columns, week rows — so the semantics
 * are free and screen readers announce "Wednesday 12" when they land on a
 * cell. Sessions inside a day are buttons, which keeps them in the natural
 * tab order. Alternative: the full ARIA grid pattern with arrow-key roving
 * focus. Tradeoff: that is the right call for a date *picker*, but here the
 * agenda list is the primary view and the calendar is an overview, so the
 * extra keyboard machinery would add more to maintain than it gives back.
 */
export function MonthCalendar({ month, sessions, onMonthChange, onSelect }: MonthCalendarProps) {
  const weeks = buildMonthGrid(month);
  const byDay = groupByDay(sessions, (session) => session.start_time);
  const weekdays = weekdayLabels();

  return (
    <section aria-label="Session calendar">
      <div className="mb-3 flex items-center justify-between gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onMonthChange(new Date(month.getFullYear(), month.getMonth() - 1, 1))}
          aria-label="Previous month"
        >
          ←
        </Button>
        <h3 aria-live="polite" className="text-sm font-semibold text-stone-900">
          {monthLabel(month)}
        </h3>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onMonthChange(new Date(month.getFullYear(), month.getMonth() + 1, 1))}
          aria-label="Next month"
        >
          →
        </Button>
      </div>

      <table className="w-full table-fixed border-collapse">
        <caption className="sr-only">{`Study sessions in ${monthLabel(month)}`}</caption>
        <thead>
          <tr>
            {weekdays.map((day) => (
              <th
                key={day}
                scope="col"
                className="border border-stone-200 bg-stone-50 p-1 text-xs font-medium text-stone-600"
              >
                {day}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {weeks.map((week) => (
            <tr key={week[0].date.toISOString()}>
              {week.map((day) => {
                const daySessions = byDay.get(startOfDay(day.date).getTime()) ?? [];
                return (
                  <td
                    key={day.date.toISOString()}
                    className={cn(
                      "h-24 border border-stone-200 p-1 align-top",
                      !day.inCurrentMonth && "bg-stone-50 text-stone-400",
                    )}
                  >
                    <span
                      className={cn(
                        "inline-flex h-6 w-6 items-center justify-center rounded-full text-xs",
                        day.isToday && "bg-teal-800 font-semibold text-white",
                      )}
                    >
                      {day.isToday ? (
                        <span className="sr-only">Today, </span>
                      ) : null}
                      {day.date.getDate()}
                    </span>
                    <ul className="mt-1 space-y-1">
                      {daySessions.map((session) => (
                        <li key={session.id}>
                          <button
                            type="button"
                            onClick={() => onSelect(session)}
                            className={cn(
                              "block w-full truncate rounded bg-teal-50 px-1 py-0.5 text-left text-xs text-teal-900",
                              "hover:bg-teal-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-800",
                            )}
                            title={session.title}
                          >
                            <span className="font-medium">{formatTime(session.start_time)}</span>{" "}
                            {session.title}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
