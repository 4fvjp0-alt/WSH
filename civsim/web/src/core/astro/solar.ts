/**
 * Low-accuracy solar position, Meeus *Astronomical Algorithms* ch. 25
 * (≈0.01° near J2000, well under 1° across AD 100–2100).
 * Verified against tools/astro_reference.py and Korean sunrise/sunset tables.
 */
import { J2000, SECONDS_PER_DAY, decimalYear } from '../time/julian.ts';
import { deltaTSeconds } from './deltaT.ts';

export const DEG = Math.PI / 180;

export function norm360(x: number): number {
  const r = x % 360;
  return r < 0 ? r + 360 : r;
}

export interface SolarState {
  rightAscensionDeg: number;
  declinationDeg: number;
  apparentLongitudeDeg: number;
  equationOfTimeMinutes: number;
  distanceAu: number;
  /** True obliquity of the ecliptic, degrees. Drifts from 23.68° (AD 100) to 23.44° (today). */
  obliquityDeg: number;
}

export function solarState(jdUt: number, applyDeltaT = true): SolarState {
  const jde = jdUt + (applyDeltaT ? deltaTSeconds(decimalYear(jdUt)) / SECONDS_PER_DAY : 0);
  const t = (jde - J2000) / 36525;
  const l0 = norm360(280.46646 + 36000.76983 * t + 0.0003032 * t * t);
  const m = norm360(357.52911 + 35999.05029 * t - 0.0001537 * t * t);
  const e = 0.016708634 - 0.000042037 * t - 0.0000001267 * t * t;
  const mr = m * DEG;
  const c =
    (1.914602 - 0.004817 * t - 0.000014 * t * t) * Math.sin(mr) +
    (0.019993 - 0.000101 * t) * Math.sin(2 * mr) +
    0.000289 * Math.sin(3 * mr);
  const trueLon = l0 + c;
  const nu = m + c;
  const r = (1.000001018 * (1 - e * e)) / (1 + e * Math.cos(nu * DEG));
  const omega = 125.04 - 1934.136 * t;
  const lambda = trueLon - 0.00569 - 0.00478 * Math.sin(omega * DEG);
  const eps0 = 23 + (26 + (21.448 - 46.815 * t - 0.00059 * t * t + 0.001813 * t ** 3) / 60) / 60;
  const eps = eps0 + 0.00256 * Math.cos(omega * DEG);
  const lr = lambda * DEG;
  const er = eps * DEG;
  const ra = norm360(Math.atan2(Math.cos(er) * Math.sin(lr), Math.cos(lr)) / DEG);
  const dec = Math.asin(Math.sin(er) * Math.sin(lr)) / DEG;

  let y = Math.tan(er / 2);
  y *= y;
  const l0r = l0 * DEG;
  const eot =
    y * Math.sin(2 * l0r) -
    2 * e * Math.sin(mr) +
    4 * e * y * Math.sin(mr) * Math.cos(2 * l0r) -
    0.5 * y * y * Math.sin(4 * l0r) -
    1.25 * e * e * Math.sin(2 * mr);

  return {
    rightAscensionDeg: ra,
    declinationDeg: dec,
    apparentLongitudeDeg: norm360(lambda),
    equationOfTimeMinutes: (eot / DEG) * 4,
    distanceAu: r,
    obliquityDeg: eps,
  };
}

/** Greenwich mean sidereal time in degrees (Meeus 12.4). This is Earth's rotation. */
export function greenwichMeanSiderealDeg(jdUt: number): number {
  const t = (jdUt - J2000) / 36525;
  return norm360(
    280.46061837 + 360.98564736629 * (jdUt - J2000) + 0.000387933 * t * t - (t * t * t) / 38710000,
  );
}

export interface HorizontalCoords {
  /** Geometric altitude, degrees (no refraction). */
  altitudeDeg: number;
  /** Azimuth in degrees clockwise from north. */
  azimuthDeg: number;
}

/** Unit vector toward the body in the world frame: +X east, +Y up, +Z north. */
export function horizontalToVector(h: HorizontalCoords): { x: number; y: number; z: number } {
  const alt = h.altitudeDeg * DEG;
  const az = h.azimuthDeg * DEG;
  const horiz = Math.cos(alt);
  return { x: horiz * Math.sin(az), y: Math.sin(alt), z: horiz * Math.cos(az) };
}

function equatorialToHorizontal(
  raDeg: number,
  decDeg: number,
  jdUt: number,
  latDeg: number,
  lonDeg: number,
): HorizontalCoords {
  const h = (greenwichMeanSiderealDeg(jdUt) + lonDeg - raDeg) * DEG;
  const phi = latDeg * DEG;
  const dec = decDeg * DEG;
  const alt = Math.asin(Math.sin(phi) * Math.sin(dec) + Math.cos(phi) * Math.cos(dec) * Math.cos(h));
  const azSouth = Math.atan2(Math.sin(h), Math.cos(h) * Math.sin(phi) - Math.tan(dec) * Math.cos(phi));
  return { altitudeDeg: alt / DEG, azimuthDeg: norm360(azSouth / DEG + 180) };
}

/** Sun altitude/azimuth for an observer. East longitude positive. */
export function sunHorizontal(jdUt: number, latDeg: number, lonDeg: number): HorizontalCoords {
  const s = solarState(jdUt);
  return equatorialToHorizontal(s.rightAscensionDeg, s.declinationDeg, jdUt, latDeg, lonDeg);
}

export { equatorialToHorizontal };
