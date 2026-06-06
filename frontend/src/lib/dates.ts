/** YYYY-MM-DD in local terms, suitable for the backend's date query params. */
export const isoDay = (d: Date): string => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};

/** A [from, to] ISO-day window ending today and spanning `days` back. */
export function rangeFrom(days: number): { from: string; to: string } {
  const to = new Date();
  const from = new Date();
  from.setDate(to.getDate() - days);
  return { from: isoDay(from), to: isoDay(to) };
}

/** Parse a backend YYYY-MM-DD string into a local Date (no TZ shift). */
export const parseDay = (s: string): Date => new Date(s + 'T00:00:00');
