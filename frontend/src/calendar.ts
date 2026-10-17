/** Format a local calendar date without shifting it through UTC. */
export function localDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/** Advance local days, including across daylight-saving changes. */
export function addDays(day: string, count: number): string {
  const date = new Date(`${day}T12:00:00`);
  date.setDate(date.getDate() + count);
  return localDate(date);
}

/** Return complete Monday-to-Sunday rows covering the given YYYY-MM month. */
export function monthRange(month: string): { start: string; end: string; days: number } {
  const first = new Date(`${month}-01T12:00:00`);
  const last = new Date(first);
  last.setMonth(last.getMonth() + 1, 0);
  const offset = (first.getDay() + 6) % 7;
  const days = Math.ceil((offset + last.getDate()) / 7) * 7;
  const start = addDays(localDate(first), -offset);
  return { start, end: addDays(start, days - 1), days };
}

/** Navigate from the first of a month so short months never get skipped. */
export function shiftMonth(month: string, offset: number): string {
  const date = new Date(`${month}-01T12:00:00`);
  date.setMonth(date.getMonth() + offset);
  return localDate(date).slice(0, 7);
}
