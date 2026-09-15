/** Sunrise, sunset, solar noon and twilight (NOAA iterative method on top of the Meeus solar position). */
import { MINUTES_PER_DAY } from '../time/julian.ts';
import { DEG, solarState, sunHorizontal } from './solar.ts';

/** Standard rise/set altitude: 34' refraction + 16' semidiameter. */
export const RISE_SET_ALT_DEG = -0.833;
export const CIVIL_TWILIGHT_ALT_DEG = -6;

/** @param jdDate0Ut Julian Day at 0h UT of the civil date (an X.5 value). */
export function solarNoon(jdDate0Ut: number, lonDeg: number): number {
  let noon = jdDate0Ut + 0.5 - lonDeg / 360;
  for (let i = 0; i < 2; i++) {
    const eot = solarState(noon).equationOfTimeMinutes;
    noon = jdDate0Ut + (720 - 4 * lonDeg - eot) / MINUTES_PER_DAY;
  }
  return noon;
}

function hourAngleDeg(latDeg: number, decDeg: number, altDeg: number): number | null {
  const phi = latDeg * DEG;
  const dec = decDeg * DEG;
  const h0 = altDeg * DEG;
  const cosH = (Math.sin(h0) - Math.sin(phi) * Math.sin(dec)) / (Math.cos(phi) * Math.cos(dec));
  if (cosH < -1 || cosH > 1) return null;
  return Math.acos(cosH) / DEG;
}

function sunEvent(
  jdDate0Ut: number,
  latDeg: number,
  lonDeg: number,
  rise: boolean,
  altDeg: number,
): number | null {
  let guess = solarNoon(jdDate0Ut, lonDeg);
  for (let i = 0; i < 3; i++) {
    const s = solarState(guess);
    const ha = hourAngleDeg(latDeg, s.declinationDeg, altDeg);
    if (ha === null) return null; // polar day/night
    const signed = rise ? ha : -ha;
    guess = jdDate0Ut + (720 - 4 * (lonDeg + signed) - s.equationOfTimeMinutes) / MINUTES_PER_DAY;
  }
  return guess;
}

export function sunrise(jdDate0Ut: number, latDeg: number, lonDeg: number): number | null {
  return sunEvent(jdDate0Ut, latDeg, lonDeg, true, RISE_SET_ALT_DEG);
}

export function sunset(jdDate0Ut: number, latDeg: number, lonDeg: number): number | null {
  return sunEvent(jdDate0Ut, latDeg, lonDeg, false, RISE_SET_ALT_DEG);
}

export function dawn(jdDate0Ut: number, latDeg: number, lonDeg: number): number | null {
  return sunEvent(jdDate0Ut, latDeg, lonDeg, true, CIVIL_TWILIGHT_ALT_DEG);
}

export function dusk(jdDate0Ut: number, latDeg: number, lonDeg: number): number | null {
  return sunEvent(jdDate0Ut, latDeg, lonDeg, false, CIVIL_TWILIGHT_ALT_DEG);
}

/** Day length in hours, 0 when the sun never rises. */
export function dayLengthHours(jdDate0Ut: number, latDeg: number, lonDeg: number): number {
  const r = sunrise(jdDate0Ut, latDeg, lonDeg);
  const s = sunset(jdDate0Ut, latDeg, lonDeg);
  if (r === null || s === null) {
    return sunHorizontal(solarNoon(jdDate0Ut, lonDeg), latDeg, lonDeg).altitudeDeg > 0 ? 24 : 0;
  }
  return (s - r) * 24;
}
