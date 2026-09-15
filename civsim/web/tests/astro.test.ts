import { describe, expect, it } from 'vitest';
import {
  GREGORIAN_START_JD, J2000, dayOfYear, decimalYear, gregorianToJd, gregorianToJdTime,
  jdToGregorian, julianCalendarToJd,
} from '../src/core/time/julian.ts';
import { formatLocalTime, utcOffsetHours } from '../src/core/time/koreaTime.ts';
import { deltaTSeconds } from '../src/core/astro/deltaT.ts';
import { horizontalToVector, solarState, sunHorizontal } from '../src/core/astro/solar.ts';
import { dayLengthHours, solarNoon, sunrise, sunset } from '../src/core/astro/sunEvents.ts';
import { lunarState, moonHorizontal } from '../src/core/astro/lunar.ts';

const LAT = 37.5665;
const LON = 126.978;

function minutesOf(hhmm: string): number {
  return Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3, 5));
}

describe('Julian day', () => {
  it('places the J2000 epoch at noon on 2000-01-01', () => {
    expect(gregorianToJdTime(2000, 1, 1, 12)).toBeCloseTo(J2000, 6);
  });

  it('agrees with the Julian calendar at the Gregorian reform', () => {
    expect(gregorianToJd(1582, 10, 15)).toBeCloseTo(GREGORIAN_START_JD, 6);
    expect(julianCalendarToJd(1582, 10, 5)).toBeCloseTo(GREGORIAN_START_JD, 6);
  });

  it.each([
    [100, 3, 21], [475, 9, 1], [1394, 10, 25], [1592, 5, 23], [1950, 6, 25], [2026, 12, 22],
  ])('round-trips %i-%i-%i', (y, m, d) => {
    const back = jdToGregorian(gregorianToJdTime(y, m, d, 13, 37));
    expect([back.year, back.month, back.day]).toEqual([y, m, d]);
    expect(back.hour).toBe(13);
    expect(back.minute).toBe(37);
  });

  it('computes day of year', () => {
    expect(dayOfYear(gregorianToJd(2026, 1, 1))).toBe(1);
    expect(dayOfYear(gregorianToJd(2026, 12, 31))).toBe(365);
    expect(dayOfYear(gregorianToJd(2024, 12, 31))).toBe(366);
  });

  it('computes decimal year', () => {
    expect(decimalYear(gregorianToJd(2026, 7, 1))).toBeGreaterThan(2026.5);
    expect(decimalYear(gregorianToJd(2026, 7, 1))).toBeLessThan(2026.6);
  });
});

describe('Korean civil time', () => {
  it.each([
    [1394, 1, 1, 8.4652], [1910, 1, 1, 8.5], [1930, 1, 1, 9], [1958, 1, 1, 8.5], [2026, 1, 1, 9],
  ])('uses the right offset in %i', (y, m, d, expected) => {
    expect(utcOffsetHours(gregorianToJd(y, m, d))).toBeCloseTo(expected, 3);
  });

  it('formats the local wall clock', () => {
    expect(formatLocalTime(gregorianToJdTime(2026, 6, 21, 3, 34))).toBe('12:34');
  });
});

describe('solar position for Seoul', () => {
  // Reference: 한국천문연구원 일출·일몰 표 (서울, KST). Tolerance 2 min / 0.3 deg.
  it.each([
    [2026, 3, 20, '06:36', '18:44', 52.3],
    [2026, 6, 21, '05:11', '19:57', 75.9],
    [2026, 9, 23, '06:20', '18:28', 52.4],
    [2026, 12, 22, '07:43', '17:17', 29.0],
  ])('matches published sunrise/sunset on %i-%i-%i', (y, m, d, rise, set, noonAlt) => {
    const jd0 = gregorianToJd(y, m, d);
    const r = sunrise(jd0, LAT, LON);
    const s = sunset(jd0, LAT, LON);
    expect(r).not.toBeNull();
    expect(s).not.toBeNull();
    expect(Math.abs(minutesOf(formatLocalTime(r!)) - minutesOf(rise))).toBeLessThanOrEqual(2);
    expect(Math.abs(minutesOf(formatLocalTime(s!)) - minutesOf(set))).toBeLessThanOrEqual(2);

    const noon = sunHorizontal(solarNoon(jd0, LON), LAT, LON);
    expect(noon.altitudeDeg).toBeCloseTo(noonAlt, 0);
    expect(Math.abs(noon.altitudeDeg - noonAlt)).toBeLessThan(0.3);
    expect(noon.azimuthDeg).toBeGreaterThan(179);
    expect(noon.azimuthDeg).toBeLessThan(181);
  });

  it('rises due east and sets due west at the equinox', () => {
    const jd0 = gregorianToJd(2026, 3, 20);
    const r = sunHorizontal(sunrise(jd0, LAT, LON)!, LAT, LON);
    const s = sunHorizontal(sunset(jd0, LAT, LON)!, LAT, LON);
    expect(r.azimuthDeg).toBeGreaterThan(88);
    expect(r.azimuthDeg).toBeLessThan(92);
    expect(s.azimuthDeg).toBeGreaterThan(268);
    expect(s.azimuthDeg).toBeLessThan(272);
  });

  it('reaches the obliquity at the solstices', () => {
    const summer = solarState(gregorianToJdTime(2026, 6, 21, 8, 24)).declinationDeg;
    const winter = solarState(gregorianToJdTime(2026, 12, 21, 15, 50)).declinationDeg;
    expect(summer).toBeGreaterThan(23.4);
    expect(summer).toBeLessThan(23.46);
    expect(winter).toBeLessThan(-23.4);
    expect(winter).toBeGreaterThan(-23.46);
  });

  it('shows a larger obliquity in antiquity', () => {
    const ancient = solarState(gregorianToJd(100, 6, 21)).obliquityDeg;
    const modern = solarState(gregorianToJd(2026, 6, 21)).obliquityDeg;
    expect(ancient).toBeGreaterThan(modern);
    expect(ancient).toBeGreaterThan(23.6);
    expect(ancient).toBeLessThan(23.75);
  });

  it('reproduces the equation of time extremes', () => {
    expect(solarState(gregorianToJd(2026, 11, 3)).equationOfTimeMinutes).toBeGreaterThan(15.5);
    expect(solarState(gregorianToJd(2026, 11, 3)).equationOfTimeMinutes).toBeLessThan(16.8);
    expect(solarState(gregorianToJd(2026, 2, 11)).equationOfTimeMinutes).toBeLessThan(-13.8);
    expect(solarState(gregorianToJd(2026, 2, 11)).equationOfTimeMinutes).toBeGreaterThan(-14.5);
  });

  it('keeps AD 100 midsummer sane', () => {
    const jd0 = gregorianToJd(100, 6, 21);
    const len = dayLengthHours(jd0, LAT, LON);
    expect(len).toBeGreaterThan(14.5);
    expect(len).toBeLessThan(15.1);
    const noon = sunHorizontal(solarNoon(jd0, LON), LAT, LON);
    expect(noon.altitudeDeg).toBeGreaterThan(75.5);
    expect(noon.altitudeDeg).toBeLessThan(76.5);
  });

  it('turns the earth: the sun crosses the whole sky in one day', () => {
    const jd0 = gregorianToJd(2026, 6, 21);
    const azimuths: number[] = [];
    for (let h = 0; h < 24; h++) azimuths.push(sunHorizontal(jd0 + h / 24, LAT, LON).azimuthDeg);
    // Azimuth must sweep monotonically (mod 360) — that is diurnal rotation, not a jitter.
    let wraps = 0;
    for (let i = 1; i < azimuths.length; i++) if (azimuths[i]! < azimuths[i - 1]!) wraps++;
    expect(wraps).toBe(1);
  });

  it('produces a unit vector pointing up at the zenith', () => {
    const v = horizontalToVector({ altitudeDeg: 90, azimuthDeg: 0 });
    expect(v.y).toBeCloseTo(1, 9);
    expect(v.x).toBeCloseTo(0, 9);
    expect(v.z).toBeCloseTo(0, 9);
    const e = horizontalToVector({ altitudeDeg: 0, azimuthDeg: 90 });
    expect(e.x).toBeCloseTo(1, 9);
    const n = horizontalToVector({ altitudeDeg: 0, azimuthDeg: 0 });
    expect(n.z).toBeCloseTo(1, 9);
  });
});

describe('delta T', () => {
  it.each([
    [2000, 63, 65], [1394.8, 300, 360], [100.5, 9400, 9800], [1600, 110, 125],
  ])('is in range at year %s', (y, lo, hi) => {
    expect(deltaTSeconds(y)).toBeGreaterThan(lo);
    expect(deltaTSeconds(y)).toBeLessThan(hi);
  });
});

describe('moon', () => {
  it('is full near a known full moon', () => {
    // 2026-01-03 10:03 UT is a full moon.
    const s = lunarState(gregorianToJdTime(2026, 1, 3, 10, 3));
    expect(s.illumination).toBeGreaterThan(0.98);
  });

  it('is new near a known new moon', () => {
    // 2026-01-18 19:52 UT is a new moon.
    const s = lunarState(gregorianToJdTime(2026, 1, 18, 19, 52));
    expect(s.illumination).toBeLessThan(0.02);
  });

  it('stays within the lunar declination envelope', () => {
    for (let d = 0; d < 30; d++) {
      const s = lunarState(gregorianToJd(2026, 1, 1) + d);
      expect(Math.abs(s.declinationDeg)).toBeLessThan(29);
      expect(s.distanceKm).toBeGreaterThan(355000);
      expect(s.distanceKm).toBeLessThan(407000);
    }
  });

  it('rises and sets like the sun does', () => {
    const above = [];
    for (let h = 0; h < 24; h++) above.push(moonHorizontal(gregorianToJd(2026, 6, 21) + h / 24, LAT, LON).altitudeDeg > 0);
    expect(above.some((v) => v)).toBe(true);
    expect(above.some((v) => !v)).toBe(true);
  });
});
