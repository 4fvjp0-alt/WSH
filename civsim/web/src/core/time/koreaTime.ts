/**
 * The civil clock people in Seoul actually lived by.
 * Before 1908 there was no statutory zone, so local mean solar time of the observer's longitude is used.
 */
import { gregorianToJd, jdToGregorian, MINUTES_PER_DAY, type CalendarDate } from './julian.ts';

export const SEOUL_LON = 126.978;
export const SEOUL_LAT = 37.5665;

const JD_1908_04_01 = gregorianToJd(1908, 4, 1);
const JD_1912_01_01 = gregorianToJd(1912, 1, 1);
const JD_1954_03_21 = gregorianToJd(1954, 3, 21);
const JD_1961_08_10 = gregorianToJd(1961, 8, 10);

export function utcOffsetHours(jdUt: number, longitudeDeg = SEOUL_LON): number {
  if (jdUt < JD_1908_04_01) return longitudeDeg / 15; // local mean time
  if (jdUt < JD_1912_01_01) return 8.5; // 대한제국 표준시
  if (jdUt < JD_1954_03_21) return 9.0; // 일본 표준시
  if (jdUt < JD_1961_08_10) return 8.5; // UTC+8:30 재채택
  return 9.0; // KST
}

export function toLocalJd(jdUt: number, longitudeDeg = SEOUL_LON): number {
  return jdUt + utcOffsetHours(jdUt, longitudeDeg) / 24;
}

export function toLocalDate(jdUt: number, longitudeDeg = SEOUL_LON): CalendarDate {
  return jdToGregorian(toLocalJd(jdUt, longitudeDeg));
}

/** "HH:mm" of the local wall clock, rounded to the nearest minute. */
export function formatLocalTime(jdUt: number, longitudeDeg = SEOUL_LON): string {
  let frac = toLocalJd(jdUt, longitudeDeg) + 0.5;
  frac -= Math.floor(frac);
  const minutes = Math.round(frac * MINUTES_PER_DAY) % MINUTES_PER_DAY;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

/** JD (UT) of 0h local time on the given local civil date. */
export function localMidnightUt(year: number, month: number, day: number, longitudeDeg = SEOUL_LON): number {
  const jd0 = gregorianToJd(year, month, day);
  return jd0 - utcOffsetHours(jd0, longitudeDeg) / 24;
}

/** Label for the timekeeping regime in force, for the UI. */
export function timeRegimeLabel(jdUt: number): string {
  if (jdUt < JD_1908_04_01) return '지방 평균시';
  if (jdUt < JD_1912_01_01) return '대한제국 표준시';
  if (jdUt < JD_1954_03_21) return '표준시 UTC+9';
  if (jdUt < JD_1961_08_10) return '표준시 UTC+8:30';
  return '한국 표준시';
}
