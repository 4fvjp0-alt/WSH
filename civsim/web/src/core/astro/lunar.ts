/**
 * Moon position and phase, Meeus ch. 47 truncated to the largest periodic terms
 * (≈0.3° in longitude — ample for a sky sprite and for a lunisolar calendar indicator).
 */
import { J2000, SECONDS_PER_DAY, decimalYear } from '../time/julian.ts';
import { deltaTSeconds } from './deltaT.ts';
import { DEG, norm360, equatorialToHorizontal, solarState, type HorizontalCoords } from './solar.ts';

export interface LunarState {
  rightAscensionDeg: number;
  declinationDeg: number;
  eclipticLongitudeDeg: number;
  distanceKm: number;
  /** 0 = new, 0.5 = full, approaching 1 = waning crescent. */
  phase: number;
  /** Lit fraction of the disc, 0..1. */
  illumination: number;
}

export function lunarState(jdUt: number): LunarState {
  const jde = jdUt + deltaTSeconds(decimalYear(jdUt)) / SECONDS_PER_DAY;
  const t = (jde - J2000) / 36525;

  const lp = norm360(218.3164477 + 481267.88123421 * t - 0.0015786 * t * t); // mean longitude
  const d = norm360(297.8501921 + 445267.1114034 * t - 0.0018819 * t * t); // mean elongation
  const m = norm360(357.5291092 + 35999.0502909 * t); // sun mean anomaly
  const mp = norm360(134.9633964 + 477198.8675055 * t + 0.0087414 * t * t); // moon mean anomaly
  const f = norm360(93.272095 + 483202.0175233 * t - 0.0036539 * t * t); // argument of latitude

  const dr = d * DEG;
  const mr = m * DEG;
  const mpr = mp * DEG;
  const fr = f * DEG;

  // Largest terms of Meeus table 47.A / 47.B, in degrees and km.
  const lon =
    lp +
    6.288774 * Math.sin(mpr) +
    1.274027 * Math.sin(2 * dr - mpr) +
    0.658314 * Math.sin(2 * dr) +
    0.213618 * Math.sin(2 * mpr) -
    0.185116 * Math.sin(mr) -
    0.114332 * Math.sin(2 * fr) +
    0.058793 * Math.sin(2 * dr - 2 * mpr) +
    0.057066 * Math.sin(2 * dr - mr - mpr) +
    0.053322 * Math.sin(2 * dr + mpr) +
    0.045758 * Math.sin(2 * dr - mr);

  const lat =
    5.128122 * Math.sin(fr) +
    0.280602 * Math.sin(mpr + fr) +
    0.277693 * Math.sin(mpr - fr) +
    0.173237 * Math.sin(2 * dr - fr) +
    0.055413 * Math.sin(2 * dr - mpr + fr) +
    0.046271 * Math.sin(2 * dr - mpr - fr);

  const distance =
    385000.56 -
    20905.355 * Math.cos(mpr) -
    3699.111 * Math.cos(2 * dr - mpr) -
    2955.968 * Math.cos(2 * dr) -
    569.925 * Math.cos(2 * mpr);

  const eps = solarState(jdUt).obliquityDeg * DEG;
  const lr = lon * DEG;
  const br = lat * DEG;
  const ra = norm360(
    Math.atan2(Math.sin(lr) * Math.cos(eps) - Math.tan(br) * Math.sin(eps), Math.cos(lr)) / DEG,
  );
  const dec = Math.asin(Math.sin(br) * Math.cos(eps) + Math.cos(br) * Math.sin(eps) * Math.sin(lr)) / DEG;

  // Phase angle from elongation (Meeus 48.4, simplified).
  const elong = norm360(lon - solarState(jdUt).apparentLongitudeDeg);
  const phase = elong / 360;
  const illumination = (1 - Math.cos(elong * DEG)) / 2;

  return {
    rightAscensionDeg: ra,
    declinationDeg: dec,
    eclipticLongitudeDeg: norm360(lon),
    distanceKm: distance,
    phase,
    illumination,
  };
}

export function moonHorizontal(jdUt: number, latDeg: number, lonDeg: number): HorizontalCoords {
  const s = lunarState(jdUt);
  return equatorialToHorizontal(s.rightAscensionDeg, s.declinationDeg, jdUt, latDeg, lonDeg);
}

/** Korean traditional lunar month day (1-30), approximated from the elongation. Used for the calendar display. */
export function lunarDayOfMonth(jdUt: number): number {
  const phase = lunarState(jdUt).phase;
  return Math.floor(phase * 29.53058867) + 1;
}
