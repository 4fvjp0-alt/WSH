/**
 * Julian Day conversions (Meeus, *Astronomical Algorithms*, ch. 7).
 * The simulation stores time as a Julian Day in Universal Time; every calendar is a view on it.
 */

export const J2000 = 2451545.0;
export const SECONDS_PER_DAY = 86400;
export const MINUTES_PER_DAY = 1440;
/** JD of 1582-10-15, the first Gregorian day. */
export const GREGORIAN_START_JD = 2299160.5;

export interface CalendarDate {
  year: number;
  month: number;
  /** Integer day of month. */
  day: number;
  /** Fraction of the day elapsed since 0h. */
  dayFraction: number;
  hour: number;
  minute: number;
  second: number;
}

function floorDiv(a: number, b: number): number {
  return Math.floor(a / b);
}

/** Proleptic Gregorian date to JD. `day` may carry a fraction (0h UT = integer day). */
export function gregorianToJd(year: number, month: number, day: number): number {
  let y = year;
  let m = month;
  if (m <= 2) {
    y -= 1;
    m += 12;
  }
  const a = floorDiv(y, 100);
  const b = 2 - a + floorDiv(a, 4);
  return Math.floor(365.25 * (y + 4716)) + Math.floor(30.6001 * (m + 1)) + day + b - 1524.5;
}

export function gregorianToJdTime(
  year: number,
  month: number,
  day: number,
  hour = 0,
  minute = 0,
  second = 0,
): number {
  return gregorianToJd(year, month, day + (hour + (minute + second / 60) / 60) / 24);
}

/** Julian-calendar date to JD (used for display before 1582-10-15). */
export function julianCalendarToJd(year: number, month: number, day: number): number {
  let y = year;
  let m = month;
  if (m <= 2) {
    y -= 1;
    m += 12;
  }
  return Math.floor(365.25 * (y + 4716)) + Math.floor(30.6001 * (m + 1)) + day - 1524.5;
}

function decode(jdIn: number, gregorian: boolean): CalendarDate {
  // Decompose in integer milliseconds. A JD near 1.8e6 carries ~3.5e-5 s of double-precision slop,
  // so a plain floor would decode 13:37:00 as 13:36:59.99996. Staying integral avoids that entirely
  // (a JD of 2.5e6 is 2.2e14 ms, well inside the 2^53 exact-integer range).
  const MS_PER_DAY = 86400000;
  const totalMs = Math.round((jdIn + 0.5) * MS_PER_DAY);
  const z = Math.floor(totalMs / MS_PER_DAY);
  const msOfDay = totalMs - z * MS_PER_DAY;
  let a = z;
  if (gregorian) {
    const alpha = Math.floor((z - 1867216.25) / 36524.25);
    a = z + 1 + alpha - Math.floor(alpha / 4);
  }
  const b = a + 1524;
  const c = Math.floor((b - 122.1) / 365.25);
  const d = Math.floor(365.25 * c);
  const e = Math.floor((b - d) / 30.6001);
  const day = b - d - Math.floor(30.6001 * e);
  const month = e < 14 ? e - 1 : e - 13;
  const year = month > 2 ? c - 4716 : c - 4715;
  return {
    year,
    month,
    day,
    dayFraction: msOfDay / MS_PER_DAY,
    hour: Math.floor(msOfDay / 3600000),
    minute: Math.floor(msOfDay / 60000) % 60,
    second: (msOfDay % 60000) / 1000,
  };
}

export function jdToGregorian(jd: number): CalendarDate {
  return decode(jd, true);
}

export function jdToJulianCalendar(jd: number): CalendarDate {
  return decode(jd, false);
}

/** Year as a decimal, e.g. 2026.47. Used for Delta T. */
export function decimalYear(jd: number): number {
  const d = jdToGregorian(jd);
  return d.year + (d.month - 0.5) / 12;
}

/** Day of the week, 0 = Sunday. */
export function dayOfWeek(jd: number): number {
  return Math.floor(jd + 1.5) % 7;
}

/** Day of the year, 1-366. */
export function dayOfYear(jd: number): number {
  const d = jdToGregorian(jd);
  return Math.floor(jd + 0.5) - Math.floor(gregorianToJd(d.year, 1, 1) + 0.5) + 1;
}
