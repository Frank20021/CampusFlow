import { describe, expect, it } from "vitest";
import { addMonths, buildMonthGrid, groupByDay, isSameDay, monthRange } from "./calendar";

describe("buildMonthGrid", () => {
  it("returns whole Sunday-first weeks", () => {
    const weeks = buildMonthGrid(new Date(2026, 10, 1));

    for (const week of weeks) {
      expect(week).toHaveLength(7);
      expect(week[0].date.getDay()).toBe(0);
      expect(week[6].date.getDay()).toBe(6);
    }
  });

  it("covers every day of the month exactly once", () => {
    const weeks = buildMonthGrid(new Date(2026, 1, 1)); // February 2026
    const daysInMonth = weeks
      .flat()
      .filter((day) => day.inCurrentMonth)
      .map((day) => day.date.getDate());

    expect(daysInMonth).toEqual(Array.from({ length: 28 }, (_, index) => index + 1));
  });

  it("pads with neighbouring days rather than leaving holes", () => {
    const weeks = buildMonthGrid(new Date(2026, 10, 1));
    const first = weeks[0];

    // November 2026 starts on a Sunday, so the first row is all in-month.
    expect(first[0].inCurrentMonth).toBe(true);
    const last = weeks[weeks.length - 1];
    expect(last.some((day) => !day.inCurrentMonth)).toBe(true);
  });

  it("handles a month that starts on a Saturday without a ragged row", () => {
    const weeks = buildMonthGrid(new Date(2026, 7, 1)); // August 2026 starts Saturday
    expect(weeks[0].filter((day) => day.inCurrentMonth)).toHaveLength(1);
    expect(weeks[0]).toHaveLength(7);
  });

  it("marks today", () => {
    const today = new Date(2026, 10, 12);
    const weeks = buildMonthGrid(new Date(2026, 10, 1), today);
    const flagged = weeks.flat().filter((day) => day.isToday);

    expect(flagged).toHaveLength(1);
    expect(flagged[0].date.getDate()).toBe(12);
  });

  it("flags no day as today when viewing another month", () => {
    const weeks = buildMonthGrid(new Date(2026, 2, 1), new Date(2026, 10, 12));
    expect(weeks.flat().some((day) => day.isToday)).toBe(false);
  });
});

describe("addMonths", () => {
  it("does not overflow when the current day has no counterpart", () => {
    // Naively adding a month to 31 January lands in March.
    expect(addMonths(new Date(2026, 0, 31), 1).getMonth()).toBe(1);
  });

  it("crosses year boundaries in both directions", () => {
    expect(addMonths(new Date(2026, 11, 1), 1).getFullYear()).toBe(2027);
    expect(addMonths(new Date(2026, 0, 1), -1).getFullYear()).toBe(2025);
  });
});

describe("monthRange", () => {
  it("spans the whole rendered grid, not just the calendar month", () => {
    const month = new Date(2026, 7, 1); // starts on a Saturday
    const { startsAfter, startsBefore } = monthRange(month);

    // The grid shows late July, so the query has to start before August.
    expect(new Date(startsAfter).getMonth()).toBe(6);
    expect(new Date(startsBefore).getTime()).toBeGreaterThan(new Date(startsAfter).getTime());
  });
});

describe("groupByDay", () => {
  it("buckets items that fall on the same local day", () => {
    const items = [
      { id: "a", at: new Date(2026, 10, 12, 9, 0).toISOString() },
      { id: "b", at: new Date(2026, 10, 12, 18, 30).toISOString() },
      { id: "c", at: new Date(2026, 10, 13, 9, 0).toISOString() },
    ];

    const byDay = groupByDay(items, (item) => item.at);
    expect(byDay.size).toBe(2);
    expect([...byDay.values()][0].map((item) => item.id)).toEqual(["a", "b"]);
  });
});

describe("isSameDay", () => {
  it("ignores the time of day", () => {
    expect(isSameDay(new Date(2026, 10, 12, 1), new Date(2026, 10, 12, 23))).toBe(true);
    expect(isSameDay(new Date(2026, 10, 12), new Date(2026, 10, 13))).toBe(false);
  });
});
